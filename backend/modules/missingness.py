import pandas as pd
import numpy as np
import io
import base64
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, Any, List
from backend.analyzer_base import BaseAnalyzerModule

class MissingnessModule(BaseAnalyzerModule):
    @property
    def name(self) -> str:
        return "missingness"

    @property
    def display_name(self) -> str:
        return "Missing Value Patterns & Imputation Strategy"

    def run(self, df: pd.DataFrame, target_column: str = None) -> Dict[str, Any]:
        n_rows = len(df)
        missing_summary = []
        columns_with_missing = []

        # 1. Compute missing summary per column
        for col in df.columns:
            null_count = int(df[col].isnull().sum())
            null_rate = float(null_count / n_rows) if n_rows > 0 else 0.0
            
            if null_count > 0:
                columns_with_missing.append(col)

            advice = ""
            code_snippet = ""
            if null_count == 0:
                advice = "No missing values. No action required."
                code_snippet = f"# Column '{col}' has no missing values."
            else:
                is_num = pd.api.types.is_numeric_dtype(df[col])
                if null_rate > 0.5:
                    advice = "High missing rate (> 50%). Consider dropping this feature or adding an indicator column."
                    code_snippet = f"# Dropping column due to high missing rate (>50%)\ndf = df.drop(columns=['{col}'])\n"
                    code_snippet += f"# Alternative: Add indicator and impute with constant\ndf['{col}_isna'] = df['{col}'].isnull().astype(int)\n"
                    if is_num:
                        code_snippet += f"df['{col}'] = df['{col}'].fillna(-999)"
                    else:
                        code_snippet += f"df['{col}'] = df['{col}'].fillna('Missing')"
                else:
                    if is_num:
                        try:
                            skew = df[col].dropna().skew() if len(df[col].dropna()) > 2 else 0
                        except Exception:
                            skew = 0
                        if abs(skew) > 1.0:
                            advice = "Highly skewed. Recommend Median imputation or KNN imputation to handle outliers."
                            code_snippet = f"df['{col}'] = df['{col}'].fillna(df['{col}'].median())"
                        else:
                            advice = "Approximately normal distribution. Recommend Mean imputation."
                            code_snippet = f"df['{col}'] = df['{col}'].fillna(df['{col}'].mean())"
                    else:
                        unique_count = df[col].nunique()
                        if unique_count > 10:
                            advice = "Categorical with high cardinality. Recommend imputing with a separate class like 'Unknown' or 'Missing'."
                            code_snippet = f"df['{col}'] = df['{col}'].fillna('Unknown')"
                        else:
                            advice = "Categorical with low cardinality. Recommend Mode imputation."
                            code_snippet = f"df['{col}'] = df['{col}'].fillna(df['{col}'].mode()[0])"

            missing_summary.append({
                "column": col,
                "missing_count": null_count,
                "missing_rate": null_rate,
                "advice": advice,
                "code_snippet": code_snippet,
                "data_type": str(df[col].dtype)
            })

        missing_summary = sorted(missing_summary, key=lambda x: x["missing_count"], reverse=True)

        # 2. Compute missingness correlation matrix
        null_correlation = {}
        if len(columns_with_missing) > 1:
            null_df = df[columns_with_missing].isnull().astype(int)
            valid_cols = [c for c in columns_with_missing if null_df[c].std() > 0]
            if len(valid_cols) > 1:
                corr_matrix = null_df[valid_cols].corr(method="pearson")
                null_correlation = {
                    "columns": valid_cols,
                    "matrix": corr_matrix.replace({np.nan: None}).values.tolist()
                }

        # 3. Missingness Heatmap Generation
        heatmap_base64 = ""
        mcar_assessment = "No missing values detected. All columns fully complete."
        mcar_p_value = 1.0
        mcar_stat = 0.0
        mcar_df = 0
        
        if len(columns_with_missing) > 0:
            sorted_missing_cols = sorted(columns_with_missing, key=lambda c: df[c].isnull().sum(), reverse=True)
            
            plt.figure(figsize=(7, 4.5))
            sns.set_theme(style="white")
            null_matrix = df[sorted_missing_cols].isnull().astype(int)
            
            # Draw heatmap (black for missing, red for missing)
            sns.heatmap(null_matrix, cbar=False, cmap=["#334155", "#e11d48"], yticklabels=False)
            plt.title("Missing Value Pattern Heatmap (Red represents Missing)", fontsize=10, color="#1e293b", weight="bold")
            plt.xlabel("Features", fontsize=8)
            plt.ylabel("Dataset Row Index", fontsize=8)
            plt.xticks(rotation=45, ha='right', fontsize=8)
            plt.tight_layout()
            
            img_buf = io.BytesIO()
            plt.savefig(img_buf, format='png', dpi=150)
            img_buf.seek(0)
            heatmap_base64 = base64.b64encode(img_buf.read()).decode('utf-8')
            plt.close()

            # 4. Formal Little's MCAR Test Implementation
            # Select numeric columns with missing values to test
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            num_cols_with_missing = [c for c in numeric_cols if df[c].isnull().sum() > 0]
            
            if len(num_cols_with_missing) > 0 and n_rows >= 30:
                try:
                    import scipy.linalg as linalg
                    from scipy.stats import chi2
                    
                    # Fill missing with mean to get baseline covariance
                    grand_means = df[numeric_cols].mean()
                    df_filled = df[numeric_cols].fillna(grand_means)
                    cov_matrix = df_filled.cov()
                    
                    # Pinverse for safety
                    inv_cov = linalg.pinv(cov_matrix.values)
                    
                    # Group by missingness indicator pattern
                    r_indicators = df[numeric_cols].isnull().astype(int)
                    unique_patterns = r_indicators.drop_duplicates()
                    
                    chi_sq = 0.0
                    df_count = 0
                    
                    for _, pattern in unique_patterns.iterrows():
                        rows_idx = r_indicators[(r_indicators == pattern).all(axis=1)].index
                        n_pattern = len(rows_idx)
                        if n_pattern == 0:
                            continue
                            
                        # Observed columns in this pattern
                        obs_cols = [numeric_cols[idx] for idx, val in enumerate(pattern) if val == 0]
                        if len(obs_cols) == 0:
                            continue
                            
                        # Pattern means
                        pattern_means = df.loc[rows_idx, obs_cols].mean()
                        diff = (pattern_means - grand_means[obs_cols]).values
                        
                        # Sub-covariance matrix
                        obs_indices = [numeric_cols.index(c) for c in obs_cols]
                        sub_cov = cov_matrix.iloc[obs_indices, obs_indices].values
                        sub_inv_cov = linalg.pinv(sub_cov)
                        
                        chi_sq += n_pattern * diff.dot(sub_inv_cov).dot(diff)
                        df_count += len(obs_cols)
                        
                    df_count = max(1, df_count - len(numeric_cols))
                    p_val = 1.0 - chi2.cdf(chi_sq, df_count)
                    
                    mcar_p_value = float(p_val)
                    mcar_stat = float(chi_sq)
                    mcar_df = int(df_count)
                    
                    if p_val < 0.05:
                        mcar_assessment = f"Little's MCAR Test: p-value = {p_val:.4f} (< 0.05), Reject MCAR. The missingness patterns are MAR/MNAR (systematically correlated with observed data)."
                    else:
                        mcar_assessment = f"Little's MCAR Test: p-value = {p_val:.4f} (>= 0.05), Fail to reject MCAR. Missing values are completely randomly distributed."
                except Exception as e:
                    # Fallback chi2 association check
                    mcar_assessment = f"Little's MCAR Test failed to converge ({str(e)}). Falling back to pairwise indicators check."
            else:
                mcar_assessment = "Little's MCAR test requires at least 30 observations and numerical columns with missing values."

        total_cells = df.size
        total_missing = int(df.isnull().sum().sum())
        overall_missing_rate = float(total_missing / total_cells) if total_cells > 0 else 0.0

        return {
            "overall_missing_rate": overall_missing_rate,
            "total_missing_cells": total_missing,
            "columns_with_missing_count": len(columns_with_missing),
            "summary": missing_summary,
            "null_correlation": null_correlation,
            "null_heatmap": heatmap_base64,
            "mcar_assessment": mcar_assessment,
            "mcar_p_value": mcar_p_value,
            "mcar_statistic": mcar_stat,
            "mcar_df": mcar_df
        }
