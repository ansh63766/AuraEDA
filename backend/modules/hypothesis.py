import pandas as pd
import numpy as np
import scipy.stats as stats
from typing import Dict, Any, List, Optional
from backend.analyzer_base import BaseAnalyzerModule

class HypothesisModule(BaseAnalyzerModule):
    @property
    def name(self) -> str:
        return "hypothesis"

    @property
    def display_name(self) -> str:
        return "Hypothesis Test Center"

    def run(self, df: pd.DataFrame, target_column: str = None) -> Dict[str, Any]:
        # During full run, return quick metadata about which tests are compatible
        numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and df[c].nunique() > 1]
        categorical_cols = [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c]) and df[c].nunique() > 1]
        
        # Binary cols
        binary_cols = [c for c in categorical_cols if df[c].nunique() == 2]
        
        return {
            "numeric_columns": numeric_cols,
            "categorical_columns": categorical_cols,
            "binary_columns": binary_cols
        }

    def run_test(
        self, 
        df: pd.DataFrame, 
        test_type: str, 
        col1: str, 
        col2: Optional[str] = None, 
        pop_mean: float = 0.0, 
        alpha: float = 0.05
    ) -> Dict[str, Any]:
        """
        Executes a specific hypothesis test on the dataframe columns.
        """
        if col1 not in df.columns:
            return {"status": "error", "message": f"Column '{col1}' not found."}
        if col2 and col2 not in df.columns:
            return {"status": "error", "message": f"Column '{col2}' not found."}

        # 1. One-Sample t-Test
        if test_type == "t_test_1sample":
            series = df[col1].dropna()
            if len(series) < 3:
                return {"status": "error", "message": "Insufficient data (need at least 3 non-null records)."}
            
            mean_val = float(series.mean())
            std_val = float(series.std())
            n = len(series)
            
            t_stat, p_val = stats.ttest_1samp(series.values, pop_mean)
            t_stat, p_val = float(t_stat), float(p_val)
            
            cohens_d = (mean_val - pop_mean) / std_val if std_val > 0 else 0.0
            
            # Achieved power approximation
            # Cohen's d: small=0.2, medium=0.5, large=0.8
            # Sample size for power=0.80 at alpha
            req_n = int(np.ceil((stats.norm.ppf(0.80) + stats.norm.ppf(1 - alpha/2))**2 / (cohens_d**2))) if abs(cohens_d) > 0.001 else "Infinite"
            
            decision = "Reject Null Hypothesis" if p_val < alpha else "Fail to Reject Null Hypothesis"
            interpretation = (
                f"Since p-value ({p_val:.4e} if p < 0.001 else f'{p_val:.4f}') is {'less' if p_val < alpha else 'greater'} than alpha ({alpha}), "
                f"we {'reject' if p_val < alpha else 'fail to reject'} the null hypothesis (H0: μ = {pop_mean}). "
                f"The sample mean ({mean_val:.4f}) is {'statistically significantly' if p_val < alpha else 'not statistically significantly'} "
                f"different from the hypothesized population mean ({pop_mean})."
            )
            
            # Return data for plotting distributions (max 1000 points)
            plot_sample = series.sample(min(1000, len(series)), random_state=42).tolist()
            
            return {
                "status": "success",
                "test_name": "One-Sample t-Test",
                "statistic_name": "t-statistic",
                "statistic": t_stat,
                "p_value": p_val,
                "decision": decision,
                "interpretation": interpretation,
                "effect_size": {
                    "name": "Cohen's d",
                    "value": float(cohens_d),
                    "interpretation": "Large" if abs(cohens_d) >= 0.8 else ("Medium" if abs(cohens_d) >= 0.5 else ("Small" if abs(cohens_d) >= 0.2 else "Negligible"))
                },
                "power_recommendation": f"To achieve 80% statistical power with the computed effect size of {abs(cohens_d):.3f}, a sample size of {req_n} observations is required.",
                "plot_data": {
                    "type": "distribution_vs_line",
                    "values": plot_sample,
                    "line_val": pop_mean,
                    "mean_val": mean_val
                }
            }

        # 2. Two-Sample Independent t-Test
        elif test_type == "t_test_ind":
            if not col2:
                return {"status": "error", "message": "Grouping categorical column (Col B) is required."}
            
            clean_df = df[[col1, col2]].dropna()
            categories = clean_df[col2].unique()
            if len(categories) != 2:
                return {"status": "error", "message": f"Grouping column '{col2}' must contain exactly 2 unique classes. Found: {list(categories)}"}
            
            cat1, cat2 = categories[0], categories[1]
            group1 = clean_df[clean_df[col2] == cat1][col1].values
            group2 = clean_df[clean_df[col2] == cat2][col1].values
            
            if len(group1) < 3 or len(group2) < 3:
                return {"status": "error", "message": "Insufficient data in one or both groups (need at least 3 records per group)."}
            
            t_stat, p_val = stats.ttest_ind(group1, group2, equal_var=False)
            t_stat, p_val = float(t_stat), float(p_val)
            
            # Cohen's d for 2 independent groups
            m1, m2 = float(group1.mean()), float(group2.mean())
            s1, s2 = float(group1.std()), float(group2.std())
            n1, n2 = len(group1), len(group2)
            
            # Pooled SD
            s_pooled = np.sqrt(((n1 - 1) * s1**2 + (n2 - 1) * s2**2) / (n1 + n2 - 2))
            cohens_d = (m1 - m2) / s_pooled if s_pooled > 0 else 0.0
            
            req_n = int(np.ceil(2 * (stats.norm.ppf(0.80) + stats.norm.ppf(1 - alpha/2))**2 / (cohens_d**2))) if abs(cohens_d) > 0.001 else "Infinite"
            
            decision = "Reject Null Hypothesis" if p_val < alpha else "Fail to Reject Null Hypothesis"
            interpretation = (
                f"Since p-value ({p_val:.4e} if p_val < 0.001 else f'{p_val:.4f}') is {'less' if p_val < alpha else 'greater'} than alpha ({alpha}), "
                f"we {'reject' if p_val < alpha else 'fail to reject'} the null hypothesis (H0: μ₁ = μ₂). "
                f"The difference in means between group '{cat1}' ({m1:.4f}) and group '{cat2}' ({m2:.4f}) "
                f"is {'statistically significant' if p_val < alpha else 'not statistically significant'}."
            )
            
            return {
                "status": "success",
                "test_name": "Two-Sample Independent t-Test",
                "statistic_name": "t-statistic",
                "statistic": t_stat,
                "p_value": p_val,
                "decision": decision,
                "interpretation": interpretation,
                "effect_size": {
                    "name": "Cohen's d",
                    "value": float(cohens_d),
                    "interpretation": "Large" if abs(cohens_d) >= 0.8 else ("Medium" if abs(cohens_d) >= 0.5 else ("Small" if abs(cohens_d) >= 0.2 else "Negligible"))
                },
                "power_recommendation": f"To achieve 80% statistical power with the computed effect size of {abs(cohens_d):.3f}, a sample size of {req_n} observations per group is required.",
                "plot_data": {
                    "type": "grouped_box",
                    "group1_name": str(cat1),
                    "group1_values": group1[:1000].tolist(),
                    "group2_name": str(cat2),
                    "group2_values": group2[:1000].tolist()
                }
            }

        # 3. Paired t-Test
        elif test_type == "t_test_paired":
            if not col2:
                return {"status": "error", "message": "Second numeric column (Col B) is required."}
            
            clean_df = df[[col1, col2]].dropna()
            if len(clean_df) < 5:
                return {"status": "error", "message": "Insufficient paired data (need at least 5 paired non-null records)."}
            
            g1, g2 = clean_df[col1].values, clean_df[col2].values
            t_stat, p_val = stats.ttest_rel(g1, g2)
            t_stat, p_val = float(t_stat), float(p_val)
            
            diff = g1 - g2
            mean_diff = float(diff.mean())
            std_diff = float(diff.std())
            
            cohens_d = mean_diff / std_diff if std_diff > 0 else 0.0
            
            req_n = int(np.ceil((stats.norm.ppf(0.80) + stats.norm.ppf(1 - alpha/2))**2 / (cohens_d**2))) if abs(cohens_d) > 0.001 else "Infinite"
            
            decision = "Reject Null Hypothesis" if p_val < alpha else "Fail to Reject Null Hypothesis"
            interpretation = (
                f"Since p-value ({p_val:.4e} if p_val < 0.001 else f'{p_val:.4f}') is {'less' if p_val < alpha else 'greater'} than alpha ({alpha}), "
                f"we {'reject' if p_val < alpha else 'fail to reject'} the null hypothesis (H0: Mean difference is 0). "
                f"The difference between '{col1}' (Mean: {g1.mean():.4f}) and '{col2}' (Mean: {g2.mean():.4f}) "
                f"is {'statistically significant' if p_val < alpha else 'not statistically significant'}."
            )
            
            return {
                "status": "success",
                "test_name": "Paired t-Test",
                "statistic_name": "t-statistic",
                "statistic": t_stat,
                "p_value": p_val,
                "decision": decision,
                "interpretation": interpretation,
                "effect_size": {
                    "name": "Cohen's d",
                    "value": float(cohens_d),
                    "interpretation": "Large" if abs(cohens_d) >= 0.8 else ("Medium" if abs(cohens_d) >= 0.5 else ("Small" if abs(cohens_d) >= 0.2 else "Negligible"))
                },
                "power_recommendation": f"To achieve 80% statistical power with the computed effect size of {abs(cohens_d):.3f}, a sample size of {req_n} pairs is required.",
                "plot_data": {
                    "type": "paired_scatter",
                    "x": g1[:1000].tolist(),
                    "y": g2[:1000].tolist(),
                    "labels": [col1, col2]
                }
            }

        # 4. One-Way ANOVA
        elif test_type == "anova":
            if not col2:
                return {"status": "error", "message": "Grouping categorical column (Col B) is required."}
            
            clean_df = df[[col1, col2]].dropna()
            groups = clean_df[col2].unique()
            if len(groups) < 2:
                return {"status": "error", "message": "Grouping column must contain at least 2 unique classes."}
            
            group_arrays = [clean_df[clean_df[col2] == g][col1].values for g in groups]
            
            # Check group sizes
            for g_name, g_arr in zip(groups, group_arrays):
                if len(g_arr) < 3:
                    return {"status": "error", "message": f"Group '{g_name}' has insufficient data (only {len(g_arr)} records). Need >= 3 per group."}
            
            f_stat, p_val = stats.f_oneway(*group_arrays)
            f_stat, p_val = float(f_stat), float(p_val)
            
            # Eta squared (effect size)
            # SS_between / SS_total
            grand_mean = clean_df[col1].mean()
            ss_total = np.sum((clean_df[col1].values - grand_mean) ** 2)
            ss_between = np.sum([len(arr) * (arr.mean() - grand_mean)**2 for arr in group_arrays])
            eta_sq = ss_between / ss_total if ss_total > 0 else 0.0
            
            decision = "Reject Null Hypothesis" if p_val < alpha else "Fail to Reject Null Hypothesis"
            interpretation = (
                f"Since p-value ({p_val:.4e} if p_val < 0.001 else f'{p_val:.4f}') is {'less' if p_val < alpha else 'greater'} than alpha ({alpha}), "
                f"we {'reject' if p_val < alpha else 'fail to reject'} the null hypothesis (H0: All group means are equal). "
                f"There {'is' if p_val < alpha else 'is no'} statistically significant difference in means of '{col1}' "
                f"across the different groups of '{col2}'."
            )
            
            # Plotly expects category labels and a flat array of values
            plot_groups = []
            for g_name, g_arr in zip(groups, group_arrays):
                plot_groups.append({
                    "name": str(g_name),
                    "values": g_arr[:500].tolist()
                })
                
            return {
                "status": "success",
                "test_name": "One-way ANOVA",
                "statistic_name": "F-statistic",
                "statistic": f_stat,
                "p_value": p_val,
                "decision": decision,
                "interpretation": interpretation,
                "effect_size": {
                    "name": "Eta-squared (η²)",
                    "value": float(eta_sq),
                    "interpretation": "Large" if eta_sq >= 0.14 else ("Medium" if eta_sq >= 0.06 else ("Small" if eta_sq >= 0.01 else "Negligible"))
                },
                "power_recommendation": f"The calculated Eta-squared is {eta_sq:.4f}. A value of η² > 0.06 indicates a medium-to-large grouping difference, suggesting appropriate sample size and group allocation.",
                "plot_data": {
                    "type": "multi_group_box",
                    "groups": plot_groups
                }
            }

        # 5. Kruskal-Wallis H-Test
        elif test_type == "kruskal":
            if not col2:
                return {"status": "error", "message": "Grouping categorical column (Col B) is required."}
            
            clean_df = df[[col1, col2]].dropna()
            groups = clean_df[col2].unique()
            if len(groups) < 2:
                return {"status": "error", "message": "Grouping column must contain at least 2 unique classes."}
            
            group_arrays = [clean_df[clean_df[col2] == g][col1].values for g in groups]
            
            # Check group sizes
            for g_name, g_arr in zip(groups, group_arrays):
                if len(g_arr) < 3:
                    return {"status": "error", "message": f"Group '{g_name}' has insufficient data (only {len(g_arr)} records). Need >= 3 per group."}
            
            h_stat, p_val = stats.kruskal(*group_arrays)
            h_stat, p_val = float(h_stat), float(p_val)
            
            # Epsilon squared
            n_total = len(clean_df)
            epsilon_sq = (h_stat - len(groups) + 1) / (n_total - len(groups)) if n_total > len(groups) else 0.0
            
            decision = "Reject Null Hypothesis" if p_val < alpha else "Fail to Reject Null Hypothesis"
            interpretation = (
                f"Since p-value ({p_val:.4e} if p_val < 0.001 else f'{p_val:.4f}') is {'less' if p_val < alpha else 'greater'} than alpha ({alpha}), "
                f"we {'reject' if p_val < alpha else 'fail to reject'} the null hypothesis (H0: Group populations are identical). "
                f"There {'is' if p_val < alpha else 'is no'} statistically significant difference in median distribution of '{col1}' "
                f"across groups of '{col2}'."
            )
            
            plot_groups = []
            for g_name, g_arr in zip(groups, group_arrays):
                plot_groups.append({
                    "name": str(g_name),
                    "values": g_arr[:500].tolist()
                })
                
            return {
                "status": "success",
                "test_name": "Kruskal-Wallis H-Test",
                "statistic_name": "H-statistic",
                "statistic": h_stat,
                "p_value": p_val,
                "decision": decision,
                "interpretation": interpretation,
                "effect_size": {
                    "name": "Epsilon-squared (ε²)",
                    "value": float(epsilon_sq),
                    "interpretation": "Large" if epsilon_sq >= 0.14 else ("Medium" if epsilon_sq >= 0.06 else ("Small" if epsilon_sq >= 0.01 else "Negligible"))
                },
                "power_recommendation": f"Epsilon-squared is {epsilon_sq:.4f}. An effect size of ε² > 0.06 suggests grouping separations are moderate to high.",
                "plot_data": {
                    "type": "multi_group_box",
                    "groups": plot_groups
                }
            }

        # 6. Shapiro-Wilk Normality Test
        elif test_type == "shapiro":
            series = df[col1].dropna()
            if len(series) < 3:
                return {"status": "error", "message": "Insufficient data (need at least 3 non-null records)."}
            
            # Shapiro-Wilk test in scipy has a strict limit of 5000 samples
            test_series = series.values
            if len(test_series) > 5000:
                np.random.seed(42)
                test_series = np.random.choice(test_series, size=5000, replace=False)
                
            w_stat, p_val = stats.shapiro(test_series)
            w_stat, p_val = float(w_stat), float(p_val)
            
            decision = "Reject Null Hypothesis" if p_val < alpha else "Fail to Reject Null Hypothesis"
            interpretation = (
                f"Since p-value ({p_val:.4e} if p_val < 0.001 else f'{p_val:.4f}') is {'less' if p_val < alpha else 'greater'} than alpha ({alpha}), "
                f"we {'reject' if p_val < alpha else 'fail to reject'} the null hypothesis (H0: Data is normally distributed). "
                f"The distribution of '{col1}' is {'statistically significantly different' if p_val < alpha else 'not statistically significantly different'} "
                f"from a normal distribution (meaning it is {'non-normal' if p_val < alpha else 'normal'})."
            )
            
            # Q-Q plot calculations
            sorted_sample = np.sort(series.sample(min(1000, len(series)), random_state=42).values)
            n_qq = len(sorted_sample)
            q_vals = (np.arange(1, n_qq + 1) - 0.5) / n_qq
            theoretical_quantiles = stats.norm.ppf(q_vals).tolist()
            
            return {
                "status": "success",
                "test_name": "Shapiro-Wilk Normality Test",
                "statistic_name": "W-statistic",
                "statistic": w_stat,
                "p_value": p_val,
                "decision": decision,
                "interpretation": interpretation,
                "effect_size": {
                    "name": "Skewness",
                    "value": float(series.skew()),
                    "interpretation": "Highly Skewed" if abs(series.skew()) > 1.0 else ("Moderately Skewed" if abs(series.skew()) > 0.5 else "Symmetric")
                },
                "power_recommendation": f"Normality testing confirms the suitability of parametric tests. If non-normal, consider using non-parametric alternatives (e.g., Kruskal-Wallis instead of ANOVA).",
                "plot_data": {
                    "type": "qq_plot",
                    "x": theoretical_quantiles,
                    "y": sorted_sample.tolist(),
                    "labels": ["Theoretical Quantiles", "Sample Quantiles"]
                }
            }

        # 7. Chi-Square Test of Independence
        elif test_type == "chisq":
            if not col2:
                return {"status": "error", "message": "Second categorical column (Col B) is required."}
            
            clean_df = df[[col1, col2]].dropna()
            contingency_tab = pd.crosstab(clean_df[col1], clean_df[col2])
            if contingency_tab.size == 0 or contingency_tab.shape[0] <= 1 or contingency_tab.shape[1] <= 1:
                return {"status": "error", "message": "Cross-tabulation contains empty or 1x1 cells. Insufficient categorical variance."}
            
            chi2, p_val, dof, expected = stats.chi2_contingency(contingency_tab)
            chi2, p_val, dof = float(chi2), float(p_val), int(dof)
            
            # Cramér's V
            n = contingency_tab.sum().sum()
            r, c = contingency_tab.shape
            v = np.sqrt(chi2 / (n * min(r - 1, c - 1))) if n > 0 and min(r - 1, c - 1) > 0 else 0.0
            
            decision = "Reject Null Hypothesis" if p_val < alpha else "Fail to Reject Null Hypothesis"
            interpretation = (
                f"Since p-value ({p_val:.4e} if p_val < 0.001 else f'{p_val:.4f}') is {'less' if p_val < alpha else 'greater'} than alpha ({alpha}), "
                f"we {'reject' if p_val < alpha else 'fail to reject'} the null hypothesis (H0: Variables are independent). "
                f"There {'is' if p_val < alpha else 'is no'} a statistically significant association between '{col1}' and '{col2}'."
            )
            
            return {
                "status": "success",
                "test_name": "Chi-Square Test of Independence",
                "statistic_name": "Chi-Square statistic",
                "statistic": chi2,
                "p_value": p_val,
                "decision": decision,
                "interpretation": interpretation,
                "effect_size": {
                    "name": "Cramér's V",
                    "value": float(v),
                    "interpretation": "Strong association" if v > 0.5 else ("Moderate association" if v > 0.3 else ("Weak association" if v > 0.1 else "Negligible"))
                },
                "power_recommendation": f"Chi-Square test degree of freedom is {dof}. With a Cramér's V association metric of {v:.3f}, the relationship shows a {'noticeable' if v > 0.1 else 'negligible'} dependency.",
                "plot_data": {
                    "type": "contingency_heatmap",
                    "x": contingency_tab.columns.tolist(),
                    "y": contingency_tab.index.tolist(),
                    "z": contingency_tab.values.tolist()
                }
            }

        else:
            return {"status": "error", "message": f"Unsupported test type '{test_type}'."}
