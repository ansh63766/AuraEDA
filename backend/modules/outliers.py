import pandas as pd
import numpy as np
from typing import Dict, Any, List
from backend.analyzer_base import BaseAnalyzerModule
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

class OutlierModule(BaseAnalyzerModule):
    @property
    def name(self) -> str:
        return "outliers"

    @property
    def display_name(self) -> str:
        return "Multivariate Outlier Diagnostics"

    def run(self, df: pd.DataFrame, target_column: str = None) -> Dict[str, Any]:
        # Filter numerical features
        numeric_cols = []
        for col in df.columns:
            if col == target_column:
                continue
            if pd.api.types.is_numeric_dtype(df[col]) and df[col].nunique() > 1:
                numeric_cols.append(col)

        if len(numeric_cols) < 2:
            return {
                "status": "bypassed",
                "message": "Multivariate outlier detection requires at least 2 numerical features."
            }

        # Impute and standardize
        X = df[numeric_cols].apply(lambda x: x.fillna(x.median()))
        
        # Remove zero variance
        valid_cols = [c for c in numeric_cols if X[c].std() > 0]
        if len(valid_cols) < 2:
            return {
                "status": "bypassed",
                "message": "Multivariate outlier detection requires at least 2 numerical features with non-zero variance."
            }

        X = X[valid_cols]

        try:
            n_rows = len(df)
            
            # 1. IQR Flags (Row-wise: flagged if any feature is IQR outlier)
            iqr_flagged_rows = np.zeros(n_rows, dtype=bool)
            for col in valid_cols:
                q25 = df[col].quantile(0.25)
                q75 = df[col].quantile(0.75)
                iqr = q75 - q25
                if iqr > 0:
                    lower = q25 - 1.5 * iqr
                    upper = q75 + 1.5 * iqr
                    col_outliers = (df[col] < lower) | (df[col] > upper)
                    iqr_flagged_rows = iqr_flagged_rows | col_outliers.fillna(False).values

            # 2. Z-Score Flags (Row-wise: flagged if absolute Z-score of any feature > 3)
            z_flagged_rows = np.zeros(n_rows, dtype=bool)
            for col in valid_cols:
                mean = df[col].mean()
                std = df[col].std()
                if std > 0:
                    z_scores = (df[col] - mean) / std
                    col_outliers = z_scores.abs() > 3
                    z_flagged_rows = z_flagged_rows | col_outliers.fillna(False).values

            # 3. Isolation Forest Flags
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)
            clf = IsolationForest(contamination=0.05, random_state=42)
            iforest_preds = clf.fit_predict(X_scaled)
            iforest_flagged_rows = (iforest_preds == -1)
            scores = clf.decision_function(X_scaled)

            # Intersection and counts
            flagged_all_three = iqr_flagged_rows & z_flagged_rows & iforest_flagged_rows
            flagged_any_two = (
                (iqr_flagged_rows & z_flagged_rows) | 
                (iqr_flagged_rows & iforest_flagged_rows) | 
                (z_flagged_rows & iforest_flagged_rows)
            )
            # Remove all three from any two
            flagged_any_two = flagged_any_two & ~flagged_all_three
            
            flagged_exactly_one = (iqr_flagged_rows.astype(int) + z_flagged_rows.astype(int) + iforest_flagged_rows.astype(int)) == 1

            # Retrieve top 25 outlier rows with method tags for UI comparison
            anomalies = []
            outlier_indices = []
            for idx in range(n_rows):
                if iqr_flagged_rows[idx] or z_flagged_rows[idx] or iforest_flagged_rows[idx]:
                    priority = 0
                    if flagged_all_three[idx]:
                        priority = 3
                    elif flagged_any_two[idx]:
                        priority = 2
                    elif flagged_exactly_one[idx]:
                        priority = 1
                    outlier_indices.append((idx, priority, float(scores[idx])))
            
            # Sort by priority desc, then anomaly score asc (more negative means more anomalous)
            outlier_indices.sort(key=lambda x: (-x[1], x[2]))

            for idx, priority, score in outlier_indices[:25]:
                row_data = df.iloc[idx].to_dict()
                cleaned_row = {k: (str(v) if pd.isnull(v) else v) for k, v in row_data.items()}
                
                anomalies.append({
                    "row_index": int(idx),
                    "anomaly_score": float(score),
                    "iqr": bool(iqr_flagged_rows[idx]),
                    "zscore": bool(z_flagged_rows[idx]),
                    "iforest": bool(iforest_flagged_rows[idx]),
                    "flag_count": int(priority),
                    "values": cleaned_row
                })

            return {
                "status": "success",
                "columns_audited": valid_cols,
                "counts": {
                    "total_rows": n_rows,
                    "iqr_only": int(iqr_flagged_rows.sum()),
                    "zscore_only": int(z_flagged_rows.sum()),
                    "iforest_only": int(iforest_flagged_rows.sum()),
                    "all_three": int(flagged_all_three.sum()),
                    "any_two": int(flagged_any_two.sum()),
                    "exactly_one": int(flagged_exactly_one.sum()),
                    "total_flagged": int((iqr_flagged_rows | z_flagged_rows | iforest_flagged_rows).sum())
                },
                "anomalies": anomalies
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Multivariate outlier detection failed: {str(e)}"
            }