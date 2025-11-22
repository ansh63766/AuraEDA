import pandas as pd
import numpy as np
from typing import Dict, Any, List
from backend.analyzer_base import BaseAnalyzerModule
from sklearn.model_selection import train_test_split
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.preprocessing import LabelEncoder

class ImportanceModule(BaseAnalyzerModule):
    @property
    def name(self) -> str:
        return "importance"

    @property
    def display_name(self) -> str:
        return "Surrogate Feature Importance"

    def run(self, df: pd.DataFrame, target_column: str = None) -> Dict[str, Any]:
        if not target_column or target_column not in df.columns:
            return {
                "status": "waiting",
                "message": "Please select a target variable in the dashboard to execute Feature Importance analysis."
            }

        # Keep rows where target is not null
        valid_idx = df[target_column].notnull()
        df_valid = df[valid_idx].copy()
        
        n_rows = len(df_valid)
        if n_rows < 15:
            return {
                "status": "error",
                "message": "Dataset requires at least 15 non-null rows to train a surrogate model."
            }

        # Subsample to keep execution fast
        if n_rows > 3000:
            df_valid = df_valid.sample(n=3000, random_state=42)

        # Features separation
        X = df_valid.drop(columns=[target_column])
        y_series = df_valid[target_column]

        # Target Type
        target_unique = y_series.nunique()
        is_classification = False
        if not pd.api.types.is_numeric_dtype(y_series) or target_unique < 15:
            is_classification = True

        # Preprocess features (label encode categoricals)
        X_encoded = pd.DataFrame()
        categorical_features_mask = []
        
        for col in X.columns:
            if X[col].isnull().all() or X[col].nunique() <= 1:
                continue

            if pd.api.types.is_numeric_dtype(X[col]):
                X_encoded[col] = X[col].astype(float)
                categorical_features_mask.append(False)
            else:
                filled = X[col].astype(str).fillna("Missing")
                le = LabelEncoder()
                X_encoded[col] = le.fit_transform(filled)
                categorical_features_mask.append(True)

        if len(X_encoded.columns) == 0:
            return {
                "status": "error",
                "message": "No valid predictive features found in the dataset."
            }

        # Encode target
        if is_classification:
            le_target = LabelEncoder()
            y = le_target.fit_transform(y_series.astype(str))
        else:
            y = y_series.values.astype(float)

        try:
            # Fit baseline model
            if is_classification:
                model = HistGradientBoostingClassifier(
                    max_depth=4, max_iter=40, random_state=42,
                    categorical_features=categorical_features_mask
                )
            else:
                model = HistGradientBoostingRegressor(
                    max_depth=4, max_iter=40, random_state=42,
                    categorical_features=categorical_features_mask
                )

            X_train, X_val, y_train, y_val = train_test_split(
                X_encoded, y, test_size=0.3, random_state=42
            )
            model.fit(X_train, y_train)

            # Compute permutation importance on validation set
            importances = permutation_importance(
                model, X_val, y_val, n_repeats=5, random_state=42
            )

            # Gather results
            feature_scores = []
            for i, col in enumerate(X_encoded.columns):
                mean_score = float(importances.importances_mean[i])
                std_score = float(importances.importances_std[i])
                feature_scores.append({
                    "column": col,
                    "importance_mean": max(0.0, mean_score), # threshold negative importances to 0
                    "importance_std": std_score
                })

            # Sort descending
            feature_scores = sorted(feature_scores, key=lambda x: x["importance_mean"], reverse=True)

            return {
                "status": "success",
                "feature_importance": feature_scores
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Feature Importance calculation failed: {str(e)}"
            }