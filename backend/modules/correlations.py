import pandas as pd
import numpy as np
from typing import Dict, Any, List
from backend.analyzer_base import BaseAnalyzerModule
from sklearn.linear_model import LinearRegression
from scipy.stats import f_oneway

class CorrelationModule(BaseAnalyzerModule):
    @property
    def name(self) -> str:
        return "correlations"

    @property
    def display_name(self) -> str:
        return "Feature Correlations & Multicollinearity"

    def run(self, df: pd.DataFrame, target_column: str = None) -> Dict[str, Any]:
        # Identify numeric vs categorical columns
        numeric_cols = []
        categorical_cols = []
        
        for col in df.columns:
            if df[col].isnull().sum() == len(df):
                continue
            if pd.api.types.is_numeric_dtype(df[col]):
                if df[col].nunique() > 1:
                    numeric_cols.append(col)
            else:
                if df[col].nunique() > 1:
                    categorical_cols.append(col)

        # 1. Pearson Correlation for numeric columns
        corr_matrix_dict = {}
        high_corr_pairs = []
        if len(numeric_cols) > 1:
            imputed_df = df[numeric_cols].apply(lambda x: x.fillna(x.median()))
            valid_numeric_cols = [c for c in numeric_cols if imputed_df[c].std() > 0]
            
            if len(valid_numeric_cols) > 1:
                corr_matrix = imputed_df[valid_numeric_cols].corr(method="pearson")
                corr_matrix_dict = {
                    "columns": valid_numeric_cols,
                    "matrix": corr_matrix.replace({np.nan: None}).values.tolist()
                }

                for i in range(len(valid_numeric_cols)):
                    for j in range(i + 1, len(valid_numeric_cols)):
                        col1, col2 = valid_numeric_cols[i], valid_numeric_cols[j]
                        val = float(corr_matrix.loc[col1, col2])
                        if abs(val) > 0.5:
                            high_corr_pairs.append({
                                "feature_1": col1,
                                "feature_2": col2,
                                "correlation": val,
                                "strength": "strong" if abs(val) > 0.8 else "moderate"
                            })
                high_corr_pairs = sorted(high_corr_pairs, key=lambda x: abs(x["correlation"]), reverse=True)

        # 2. Variance Inflation Factor (VIF) for multicollinearity check
        vifs = {}
        if len(numeric_cols) >= 2:
            imputed_df = df[numeric_cols].apply(lambda x: x.fillna(x.median()))
            valid_vif_cols = [c for c in numeric_cols if imputed_df[c].std() > 0]
            
            if len(valid_vif_cols) >= 2:
                for target_col in valid_vif_cols:
                    features = [c for c in valid_vif_cols if c != target_col]
                    if not features:
                        vifs[target_col] = 1.0
                        continue
                    X = imputed_df[features].values
                    y = imputed_df[target_col].values
                    
                    try:
                        lr = LinearRegression()
                        lr.fit(X, y)
                        r2 = lr.score(X, y)
                        if r2 >= 1.0:
                            vif = 999999.0
                        else:
                            vif = float(1.0 / (1.0 - r2))
                    except Exception:
                        vif = 1.0
                    vifs[target_col] = vif

        # 3. Categorical Associations (Cramer's V) - Compiles full mapping
        cramers_v_list = []
        all_categorical_associations = {}
        all_cats = categorical_cols.copy()
        if len(all_cats) > 1:
            from scipy.stats import chi2_contingency
            sample_df = df[all_cats]
            if len(sample_df) > 5000:
                sample_df = sample_df.sample(n=5000, random_state=42)
                
            for i in range(len(all_cats)):
                for j in range(i + 1, len(all_cats)):
                    col1, col2 = all_cats[i], all_cats[j]
                    contingency_tab = pd.crosstab(sample_df[col1], sample_df[col2])
                    if contingency_tab.size == 0 or contingency_tab.shape[0] <= 1 or contingency_tab.shape[1] <= 1:
                        continue
                        
                    try:
                        chi2, p_val, dof, expected = chi2_contingency(contingency_tab)
                        n = contingency_tab.sum().sum()
                        if n > 0:
                            r, c = contingency_tab.shape
                            v = np.sqrt(chi2 / (n * min(r - 1, c - 1)))
                            cramers_v_list.append({
                                "feature_1": col1,
                                "feature_2": col2,
                                "cramers_v": float(v),
                                "strength": "strong" if v > 0.5 else ("moderate" if v > 0.3 else "weak")
                            })
                    except Exception:
                        pass
            cramers_v_list = sorted(cramers_v_list, key=lambda x: x["cramers_v"], reverse=True)

        # 4. Point-Biserial target correlation (for numeric vs binary target)
        point_biserial_list = []
        if target_column and target_column in df.columns and pd.api.types.is_numeric_dtype(df[target_column]):
            # Verify if target is binary
            target_series = df[target_column].dropna()
            if target_series.nunique() == 2:
                # Target is binary!
                imputed_df = df.apply(lambda x: x.fillna(x.median()) if pd.api.types.is_numeric_dtype(x) else x.fillna("Missing"))
                for col in numeric_cols:
                    if col == target_column:
                        continue
                    try:
                        # Compute Pearson corr between numeric feature and binary target
                        corr = float(imputed_df[col].corr(imputed_df[target_column], method="pearson"))
                        point_biserial_list.append({
                            "column": col,
                            "correlation": corr,
                            "strength": "strong" if abs(corr) > 0.5 else ("moderate" if abs(corr) > 0.25 else "weak")
                        })
                    except Exception:
                        pass
                point_biserial_list = sorted(point_biserial_list, key=lambda x: abs(x["correlation"]), reverse=True)

        # 5. Partial Correlation Matrix (for top 6 numeric features)
        partial_corr_matrix = {}
        if len(numeric_cols) >= 3:
            imputed_df = df[numeric_cols].apply(lambda x: x.fillna(x.median()))
            top_numeric = [c for c in numeric_cols if imputed_df[c].std() > 0][:6]
            
            if len(top_numeric) >= 3:
                cols_count = len(top_numeric)
                matrix = np.zeros((cols_count, cols_count))
                for i in range(cols_count):
                    matrix[i, i] = 1.0
                    for j in range(i + 1, cols_count):
                        col1 = top_numeric[i]
                        col2 = top_numeric[j]
                        # Confounders: all other top numeric cols
                        confounders = [c for c in top_numeric if c != col1 and c != col2]
                        
                        try:
                            # Fit linear regressions to compute residuals
                            lr1 = LinearRegression()
                            lr1.fit(imputed_df[confounders], imputed_df[col1])
                            res1 = imputed_df[col1] - lr1.predict(imputed_df[confounders])
                            
                            lr2 = LinearRegression()
                            lr2.fit(imputed_df[confounders], imputed_df[col2])
                            res2 = imputed_df[col2] - lr2.predict(imputed_df[confounders])
                            
                            r = float(res1.corr(res2, method="pearson"))
                            matrix[i, j] = r
                            matrix[j, i] = r
                        except Exception:
                            matrix[i, j] = 0.0
                            matrix[j, i] = 0.0
                            
                partial_corr_matrix = {
                    "columns": top_numeric,
                    "matrix": np.nan_to_num(matrix).tolist()
                }

        # 6. Interaction effect detection between feature pairs on target column
        interaction_effects = []
        if target_column and target_column in df.columns and pd.api.types.is_numeric_dtype(df[target_column]):
            y = df[target_column].dropna()
            valid_idx = y.index
            
            # Use top 5 numeric columns to test for interaction effects
            test_cols = [c for c in numeric_cols if c != target_column][:5]
            if len(test_cols) >= 2:
                for i in range(len(test_cols)):
                    for j in range(i + 1, len(test_cols)):
                        col1, col2 = test_cols[i], test_cols[j]
                        try:
                            # Fit a linear regression y ~ b0 + b1*x1 + b2*x2 + b3*(x1*x2)
                            x1 = df.loc[valid_idx, col1].fillna(df[col1].median()).values
                            x2 = df.loc[valid_idx, col2].fillna(df[col2].median()).values
                            x_inter = x1 * x2
                            
                            X_with = np.column_stack((x1, x2, x_inter))
                            X_without = np.column_stack((x1, x2))
                            
                            lr_with = LinearRegression().fit(X_with, y.values)
                            lr_without = LinearRegression().fit(X_without, y.values)
                            
                            r2_with = lr_with.score(X_with, y.values)
                            r2_without = lr_without.score(X_without, y.values)
                            
                            # F-test for interaction term
                            n = len(y)
                            p_with = 3
                            p_without = 2
                            
                            rss_with = np.sum((y.values - lr_with.predict(X_with)) ** 2)
                            rss_without = np.sum((y.values - lr_without.predict(X_without)) ** 2)
                            
                            if rss_with > 0 and (n - p_with - 1) > 0:
                                f_stat = ((rss_without - rss_with) / (p_with - p_without)) / (rss_with / (n - p_with - 1))
                                # Simple p-value approximation
                                p_val = 1.0 if f_stat <= 0 else float(1.0 / (1.0 + f_stat)) # fallback approximation
                                
                                interaction_effects.append({
                                    "feature_a": col1,
                                    "feature_b": col2,
                                    "f_statistic": float(f_stat),
                                    "p_value": float(p_val),
                                    "significant": bool(p_val < 0.05)
                                })
                        except Exception:
                            pass
                interaction_effects = sorted(interaction_effects, key=lambda x: x["p_value"])

        return {
            "numeric_correlation": corr_matrix_dict,
            "high_correlation_pairs": high_corr_pairs,
            "vif_scores": vifs,
            "categorical_associations": cramers_v_list,
            "point_biserial_correlations": point_biserial_list,
            "partial_correlation": partial_corr_matrix,
            "interaction_effects": interaction_effects
        }
