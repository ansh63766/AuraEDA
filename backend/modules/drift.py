import pandas as pd
import numpy as np
from typing import Dict, Any, List
from backend.analyzer_base import BaseAnalyzerModule
from sklearn.model_selection import train_test_split
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.preprocessing import LabelEncoder

class DriftSensitivityModule(BaseAnalyzerModule):
    @property
    def name(self) -> str:
        return "drift"

    @property
    def display_name(self) -> str:
        return "Feature Drift & Model Sensitivity Simulation"

    def run(self, df: pd.DataFrame, target_column: str = None) -> Dict[str, Any]:
        if not target_column or target_column not in df.columns:
            return {
                "status": "waiting",
                "message": "Please select a target variable in the dashboard to execute Drift Sensitivity Simulation."
            }

        # Validate target
        target = df[target_column]
        if target.isnull().all():
            return {
                "status": "error",
                "message": f"Target column '{target_column}' is entirely missing."
            }

        # Keep rows where target is not null
        valid_idx = target.notnull()
        df_valid = df[valid_idx].copy()
        
        n_rows = len(df_valid)
        if n_rows < 30:
            return {
                "status": "error",
                "message": "Dataset requires at least 30 non-null rows to train a surrogate model."
            }

        # Subsample to keep execution fast and prevent timeouts
        if n_rows > 5000:
            df_valid = df_valid.sample(n=5000, random_state=42)
            n_rows = 5000

        # Features separation
        X = df_valid.drop(columns=[target_column])
        y_series = df_valid[target_column]

        # Target Type
        target_unique = y_series.nunique()
        is_classification = False
        if not pd.api.types.is_numeric_dtype(y_series) or target_unique < 15:
            is_classification = True

        # Preprocess features (HistGradientBoosting accepts numerical with NaN, label encode categoricals)
        X_encoded = pd.DataFrame()
        categorical_features_mask = []
        col_index = 0
        
        for col in X.columns:
            # Skip if column is all missing
            if X[col].isnull().all():
                continue
            
            # Skip if zero variance
            if X[col].nunique() <= 1:
                continue

            if pd.api.types.is_numeric_dtype(X[col]):
                X_encoded[col] = X[col].astype(float)
                categorical_features_mask.append(False)
            else:
                # Fill missing with string indicator, then label encode
                filled = X[col].astype(str).fillna("Missing")
                le = LabelEncoder()
                X_encoded[col] = le.fit_transform(filled)
                categorical_features_mask.append(True)
            col_index += 1

        if len(X_encoded.columns) == 0:
            return {
                "status": "error",
                "message": "No valid predictive features found in the dataset."
            }

        # Encode target
        if is_classification:
            le_target = LabelEncoder()
            y = le_target.fit_transform(y_series.astype(str))
            n_classes = len(np.unique(y))
        else:
            y = y_series.values.astype(float)

        # Split train/val
        try:
            X_train, X_val, y_train, y_val = train_test_split(
                X_encoded, y, test_size=0.25, random_state=42
            )
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to partition data for training: {str(e)}"
            }

        # Fit model
        try:
            if is_classification:
                # Use HistGradientBoostingClassifier
                model = HistGradientBoostingClassifier(
                    max_depth=4, max_iter=50, random_state=42,
                    categorical_features=categorical_features_mask
                )
                model.fit(X_train, y_train)
                # Compute baseline metric (ROC-AUC if binary, accuracy otherwise)
                if n_classes == 2:
                    baseline_score = model.score(X_val, y_val) # accuracy
                    # Let's get roc_auc for evaluation metric
                    from sklearn.metrics import roc_auc_score
                    probs = model.predict_proba(X_val)[:, 1]
                    baseline_score = float(roc_auc_score(y_val, probs))
                    metric_name = "ROC-AUC"
                else:
                    baseline_score = float(model.score(X_val, y_val))
                    metric_name = "Accuracy"
            else:
                # Use HistGradientBoostingRegressor
                model = HistGradientBoostingRegressor(
                    max_depth=4, max_iter=50, random_state=42,
                    categorical_features=categorical_features_mask
                )
                model.fit(X_train, y_train)
                baseline_score = float(model.score(X_val, y_val)) # R2 score
                metric_name = "R²"
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to train baseline model: {str(e)}"
            }

        # Perturbation and sensitivity evaluation
        drift_results = []
        
        for col in X_encoded.columns:
            # Clone validation set
            X_val_perturbed = X_val.copy()
            col_std = X_encoded[col].std()
            
            # If standard deviation is 0 (should be filtered, but double check)
            if col_std == 0:
                continue

            # Perturb column values by 10%
            is_categorical = categorical_features_mask[X_encoded.columns.get_loc(col)]
            if not is_categorical:
                # Numerical perturbation: Shift validation values by 0.1 * std (mimicking a drift shift)
                X_val_perturbed[col] = X_val_perturbed[col] + 0.1 * col_std
            else:
                # Categorical perturbation: Shuffling 10% of category values randomly to simulate category noise
                n_perturbed = max(1, int(0.10 * len(X_val_perturbed)))
                perturbed_indices = np.random.choice(X_val_perturbed.index, size=n_perturbed, replace=False)
                original_values = X_val_perturbed.loc[perturbed_indices, col].values
                shuffled_values = np.random.permutation(original_values)
                X_val_perturbed.loc[perturbed_indices, col] = shuffled_values

            # Evaluate model performance on perturbed data
            try:
                if is_classification and metric_name == "ROC-AUC":
                    from sklearn.metrics import roc_auc_score
                    probs = model.predict_proba(X_val_perturbed)[:, 1]
                    perturbed_score = float(roc_auc_score(y_val, probs))
                else:
                    perturbed_score = float(model.score(X_val_perturbed, y_val))
                
                score_drop = baseline_score - perturbed_score
            except Exception:
                score_drop = 0.0
                perturbed_score = baseline_score

            # Classify sensitivity
            # We scale sensitivity based on score drop. If ROC-AUC drops by >0.02, it is significant.
            # If R2 drops by >0.05, it is significant.
            sensitivity = "low"
            if metric_name == "ROC-AUC":
                if score_drop > 0.03:
                    sensitivity = "high"
                elif score_drop > 0.005:
                    sensitivity = "medium"
            else: # R2 or Accuracy
                if score_drop > 0.05:
                    sensitivity = "high"
                elif score_drop > 0.01:
                    sensitivity = "medium"

            drift_results.append({
                "column": col,
                "baseline_score": baseline_score,
                "perturbed_score": perturbed_score,
                "score_drop": score_drop,
                "sensitivity": sensitivity,
                "metric_name": metric_name
            })

        # Sort features by sensitivity (score drop) descending
        drift_results = sorted(drift_results, key=lambda x: x["score_drop"], reverse=True)

        return {
            "status": "success",
            "baseline_score": baseline_score,
            "metric_name": metric_name,
            "drift_features": drift_results
        }
