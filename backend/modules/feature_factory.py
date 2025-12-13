import pandas as pd
import numpy as np
from typing import Dict, Any, List
from backend.analyzer_base import BaseAnalyzerModule
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.feature_selection import mutual_info_classif, mutual_info_regression, RFE
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

class FeatureFactoryModule(BaseAnalyzerModule):
    @property
    def name(self) -> str:
        return "feature_factory"

    @property
    def display_name(self) -> str:
        return "Feature Factory & Recommendations"

    def run(self, df: pd.DataFrame, target_column: str = None) -> Dict[str, Any]:
        # 1. Feature Recommendations (Log skewness, ratio pairs)
        recommendations = []
        numeric_cols = [col for col in df.columns if pd.api.types.is_numeric_dtype(df[col]) and col != target_column]
        
        # Log skew recommendations
        for col in numeric_cols:
            non_null = df[col].dropna()
            if len(non_null) >= 10:
                skew_val = float(non_null.skew())
                if abs(skew_val) > 1.0:
                    # Recommend log skew
                    # Check if negative values exist
                    has_neg = (non_null < 0).any()
                    rec_strat = "log"
                    msg = f"Feature '{col}' has high skewness ({skew_val:.2f}). We recommend a log transform."
                    if has_neg:
                        msg += " (Negative values detected; we will automatically apply a positive shift)."
                    recommendations.append({
                        "type": "skew",
                        "column": col,
                        "skew": skew_val,
                        "action": "transform",
                        "strategy": "log",
                        "message": msg
                    })

        # Ratio pairs recommendations
        # Calculate pairwise correlation to find meaningful ratios (moderate correlation, e.g. 0.1 to 0.7)
        if len(numeric_cols) >= 2:
            corr_matrix = df[numeric_cols].corr().abs()
            pairs_checked = set()
            for col1 in numeric_cols:
                for col2 in numeric_cols:
                    if col1 == col2 or (col2, col1) in pairs_checked:
                        continue
                    pairs_checked.add((col1, col2))
                    
                    r_val = corr_matrix.loc[col1, col2]
                    # We look for moderate correlation to avoid perfect collinearity or completely independent noise
                    if 0.15 <= r_val <= 0.75:
                        # Ensure no zero division by adding a small epsilon in calculations
                        non_null_df = df[[col1, col2]].dropna()
                        if len(non_null_df) >= 10:
                            # Let's suggest a ratio feature
                            recommendations.append({
                                "type": "ratio",
                                "column1": col1,
                                "column2": col2,
                                "action": "custom_formula",
                                "strategy": f"{col1} / ({col2} + 1e-5)",
                                "message": f"Features '{col1}' and '{col2}' are moderately correlated ({r_val:.2f}). Consider creating a ratio interaction."
                            })
                            # Limit to top 5 ratio recommendations to avoid UI clutter
                            if len([r for r in recommendations if r["type"] == "ratio"]) >= 5:
                                break
                if len([r for r in recommendations if r["type"] == "ratio"]) >= 5:
                    break

        # 2. Feature Rankings (Variance, correlation filters, MI, and RFE selectors)
        rankings = []
        if not target_column or target_column not in df.columns:
            return {
                "status": "success",
                "recommendations": recommendations,
                "rankings": [],
                "message": "Select a target variable to see feature rankings."
            }

        # Keep rows where target is not null
        df_valid = df.dropna(subset=[target_column]).copy()
        if len(df_valid) < 15:
            return {
                "status": "success",
                "recommendations": recommendations,
                "rankings": [],
                "message": "Dataset requires at least 15 non-null target rows for feature ranking."
            }

        # Subsample if dataset is too large
        if len(df_valid) > 2000:
            df_valid = df_valid.sample(n=2000, random_state=42)

        X_raw = df_valid.drop(columns=[target_column])
        y_raw = df_valid[target_column]

        # Target Type
        is_classification = not pd.api.types.is_numeric_dtype(y_raw) or y_raw.nunique() < 15

        # Preprocess features (standardize numeric, label encode categorical)
        X = pd.DataFrame()
        feature_cols = []
        for col in X_raw.columns:
            if X_raw[col].isnull().all() or X_raw[col].nunique() <= 1:
                continue
            feature_cols.append(col)
            if pd.api.types.is_numeric_dtype(X_raw[col]):
                X[col] = X_raw[col].fillna(X_raw[col].median()).astype(float)
            else:
                le = LabelEncoder()
                X[col] = le.fit_transform(X_raw[col].astype(str).fillna("Missing")).astype(float)

        if len(feature_cols) == 0:
            return {
                "status": "success",
                "recommendations": recommendations,
                "rankings": [],
                "message": "No valid features for ranking."
            }

        # Encode target
        if is_classification:
            le_target = LabelEncoder()
            y = le_target.fit_transform(y_raw.astype(str))
        else:
            y = y_raw.values.astype(float)

        try:
            # 1. Variance score (on standardized features)
            scaler = StandardScaler()
            X_scaled = pd.DataFrame(scaler.fit_transform(X), columns=X.columns)
            variance_scores = X_scaled.var().fillna(0.0).to_dict()

            # 2. Correlation with target
            correlation_scores = {}
            for col in X.columns:
                corr_val = float(np.abs(np.corrcoef(X[col], y)[0, 1]))
                correlation_scores[col] = 0.0 if np.isnan(corr_val) else corr_val

            # 3. Mutual Information (MI)
            if is_classification:
                mi_vals = mutual_info_classif(X, y, random_state=42)
            else:
                mi_vals = mutual_info_regression(X, y, random_state=42)
            mi_scores = {col: float(val) for col, val in zip(X.columns, mi_vals)}

            # 4. RFE Rank (using simple DecisionTree model)
            if is_classification:
                dt = DecisionTreeClassifier(max_depth=4, random_state=42)
            else:
                dt = DecisionTreeRegressor(max_depth=4, random_state=42)
            
            rfe = RFE(estimator=dt, n_features_to_select=1, step=1)
            rfe.fit(X, y)
            rfe_ranks = {col: int(rank) for col, rank in zip(X.columns, rfe.ranking_)}

            # Compute ranks for each metric and ensemble average rank
            # Rank Variance (descending)
            var_sorted = sorted(variance_scores.keys(), key=lambda k: variance_scores[k], reverse=True)
            var_ranks = {col: idx + 1 for idx, col in enumerate(var_sorted)}

            # Rank Correlation (descending)
            corr_sorted = sorted(correlation_scores.keys(), key=lambda k: correlation_scores[k], reverse=True)
            corr_ranks = {col: idx + 1 for idx, col in enumerate(corr_sorted)}

            # Rank MI (descending)
            mi_sorted = sorted(mi_scores.keys(), key=lambda k: mi_scores[k], reverse=True)
            mi_ranks = {col: idx + 1 for idx, col in enumerate(mi_sorted)}

            # RFE ranks (RFE already gives rank where 1 is best)
            # Compile results
            for col in feature_cols:
                vr = var_ranks.get(col, len(feature_cols))
                cr = corr_ranks.get(col, len(feature_cols))
                mr = mi_ranks.get(col, len(feature_cols))
                rr = rfe_ranks.get(col, len(feature_cols))
                
                avg_rank = (vr + cr + mr + rr) / 4.0
                
                rankings.append({
                    "column": col,
                    "variance_score": float(variance_scores.get(col, 0.0)),
                    "correlation_score": float(correlation_scores.get(col, 0.0)),
                    "mi_score": float(mi_scores.get(col, 0.0)),
                    "rfe_rank": int(rfe_ranks.get(col, len(feature_cols))),
                    "ensemble_rank": float(avg_rank)
                })

            # Sort by ensemble rank ascending (lower average rank is better!)
            rankings = sorted(rankings, key=lambda x: x["ensemble_rank"])

            # Add human readable rank numbers
            for idx, r in enumerate(rankings):
                r["rank"] = idx + 1

            return {
                "status": "success",
                "recommendations": recommendations,
                "rankings": rankings
            }

        except Exception as e:
            return {
                "status": "error",
                "recommendations": recommendations,
                "rankings": [],
                "message": f"Feature ranking execution failed: {str(e)}"
            }
