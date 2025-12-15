import numpy as np
import pandas as pd
import time
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, r2_score, mean_absolute_error, mean_squared_error
from sklearn.calibration import calibration_curve

# Import models
from sklearn.linear_model import LogisticRegression, Ridge, LinearRegression
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor, ExtraTreesClassifier, ExtraTreesRegressor, GradientBoostingClassifier, GradientBoostingRegressor, AdaBoostClassifier, AdaBoostRegressor
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
from sklearn.svm import SVR

# Safe import for SMOTE
try:
    from imblearn.over_sampling import SMOTE
    HAS_SMOTE = True
except ImportError:
    HAS_SMOTE = False

class AutoMLShapModule:
    """
    AutoML training suite and SHAP explainer module.
    Handles concurrent model fitting, class balancing, curve diagnostics,
    Cook's distance outlier searches, and surrogate SHAP approximations.
    """
    def __init__(self):
        pass

    def run_automl_training(
        self,
        df: pd.DataFrame,
        target_column: str,
        split_ratio: float = 0.3,
        balancing: str = "None"
    ) -> Dict[str, Any]:
        """
        Trains 8 models concurrently and returns metrics and test evaluations.
        """
        # Keep rows where target is not null
        df_valid = df.dropna(subset=[target_column]).copy()
        if len(df_valid) < 15:
            return {"status": "error", "message": "Dataset requires at least 15 rows for AutoML training."}

        X_raw = df_valid.drop(columns=[target_column])
        y_raw = df_valid[target_column]

        is_classification = not pd.api.types.is_numeric_dtype(y_raw) or y_raw.nunique() < 15

        # Preprocess features (standardize numeric, label encode categorical)
        X = pd.DataFrame()
        categorical_mask = []
        feature_cols = []
        for col in X_raw.columns:
            if X_raw[col].isnull().all() or X_raw[col].nunique() <= 1:
                continue
            feature_cols.append(col)
            if pd.api.types.is_numeric_dtype(X_raw[col]):
                X[col] = X_raw[col].fillna(X_raw[col].median()).astype(float)
                categorical_mask.append(False)
            else:
                le = LabelEncoder()
                X[col] = le.fit_transform(X_raw[col].astype(str).fillna("Missing")).astype(float)
                categorical_mask.append(True)

        if len(feature_cols) == 0:
            return {"status": "error", "message": "No valid predictive features found."}

        # Encode target
        if is_classification:
            le_target = LabelEncoder()
            y = le_target.fit_transform(y_raw.astype(str))
            target_classes = [str(c) for c in le_target.classes_]
        else:
            y = y_raw.values.astype(float)
            target_classes = []

        # Split data
        stratify = y if is_classification else None
        try:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=split_ratio, random_state=42, stratify=stratify
            )
        except Exception:
            # Fall back to unstratified split if class counts are too small
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=split_ratio, random_state=42
            )

        # Apply target class balancing to training split
        if is_classification and balancing != "None":
            if balancing == "SMOTE":
                if HAS_SMOTE:
                    try:
                        smote = SMOTE(random_state=42)
                        X_train, y_train = smote.fit_resample(X_train, y_train)
                    except Exception:
                        X_train, y_train = self._random_oversample(X_train, y_train)
                else:
                    X_train, y_train = self._random_oversample(X_train, y_train)
            elif balancing == "Random Over-sampler":
                X_train, y_train = self._random_oversample(X_train, y_train)
            elif balancing == "Random Under-sampler":
                X_train, y_train = self._random_undersample(X_train, y_train)

        # Train models concurrently using thread pool
        results = []
        estimators = self._get_estimators(is_classification, balancing)

        # Add scaling inside models or fit on scaled data
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)

        def fit_and_evaluate(name, model):
            t0 = time.time()
            try:
                model.fit(X_train_scaled, y_train)
                fit_time = time.time() - t0
                
                # Predict
                preds = model.predict(X_test_scaled)
                
                if is_classification:
                    acc = accuracy_score(y_test, preds)
                    prec = precision_score(y_test, preds, average="macro", zero_division=0)
                    rec = recall_score(y_test, preds, average="macro", zero_division=0)
                    f1 = f1_score(y_test, preds, average="macro", zero_division=0)
                    
                    # AUC calculation
                    try:
                        if hasattr(model, "predict_proba"):
                            probs = model.predict_proba(X_test_scaled)
                            if len(target_classes) == 2:
                                auc = roc_auc_score(y_test, probs[:, 1])
                            else:
                                auc = roc_auc_score(y_test, probs, multi_class="ovr", average="macro")
                        else:
                            auc = acc # fallback
                    except Exception:
                        auc = acc
                    
                    return {
                        "name": name,
                        "fit_time": fit_time,
                        "accuracy": float(acc),
                        "precision": float(prec),
                        "recall": float(rec),
                        "f1": float(f1),
                        "auc": float(auc),
                        "status": "success",
                        "model_obj": model
                    }
                else:
                    r2 = r2_score(y_test, preds)
                    mae = mean_absolute_error(y_test, preds)
                    mse = mean_squared_error(y_test, preds)
                    rmse = np.sqrt(mse)
                    
                    # Adjusted R2
                    n, p = X_test.shape
                    adj_r2 = 1 - (1 - r2) * (n - 1) / (n - p - 1) if (n - p - 1) > 0 else r2
                    
                    return {
                        "name": name,
                        "fit_time": fit_time,
                        "r2": float(r2),
                        "mae": float(mae),
                        "mse": float(mse),
                        "rmse": float(rmse),
                        "adjusted_r2": float(adj_r2),
                        "status": "success",
                        "model_obj": model
                    }
            except Exception as e:
                return {
                    "name": name,
                    "status": "error",
                    "message": str(e)
                }

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [
                executor.submit(fit_and_evaluate, name, model)
                for name, model in estimators.items()
            ]
            results = [f.result() for f in futures]

        # Filter out errors
        successful_results = [r for r in results if r["status"] == "success"]
        if not successful_results:
            return {"status": "error", "message": "All models failed to train."}

        # Find best model
        if is_classification:
            successful_results = sorted(successful_results, key=lambda x: x["f1"], reverse=True)
            best_model_name = successful_results[0]["name"]
        else:
            successful_results = sorted(successful_results, key=lambda x: x["r2"], reverse=True)
            best_model_name = successful_results[0]["name"]

        # Cache best model for SHAP/Attributions query
        best_model_dict = next(r for r in successful_results if r["name"] == best_model_name)
        best_model = best_model_dict["model_obj"]

        # Compile final diagnostics payload
        diagnostics = {}
        if is_classification:
            # Get test probabilities of the best model
            probs = None
            if hasattr(best_model, "predict_proba"):
                probs = best_model.predict_proba(X_test_scaled)
                # Platt calibration curve
                try:
                    prob_true, prob_pred = calibration_curve(y_test, probs[:, 1] if len(target_classes) == 2 else probs[:, 0], n_bins=10)
                    diagnostics["calibration"] = {
                        "true_probs": [float(p) for p in prob_true],
                        "pred_probs": [float(p) for p in prob_pred]
                    }
                except Exception:
                    pass

            diagnostics["classification"] = {
                "y_true": [int(val) for val in y_test],
                "y_pred": [int(val) for val in best_model.predict(X_test_scaled)],
                "probs": [[float(p) for p in row] for row in probs] if probs is not None else []
            }
        else:
            # Cook's distance outliers and residuals plot
            preds = best_model.predict(X_test_scaled)
            residuals = y_test - preds
            diagnostics["regression"] = {
                "fitted_values": [float(v) for v in preds],
                "residuals": [float(v) for v in residuals]
            }
            # Cook's distance on training set (exact analytical calculation using linear surrogate)
            try:
                cooks = self._calculate_cooks_distance(X_train_scaled, y_train)
                diagnostics["cooks_distance"] = [float(c) for c in cooks]
            except Exception as e:
                diagnostics["cooks_distance_error"] = str(e)

        # Remove model objects before JSON serialization
        leaderboard = []
        for r in successful_results:
            row = {k: v for k, v in r.items() if k != "model_obj"}
            leaderboard.append(row)

        return {
            "status": "success",
            "is_classification": is_classification,
            "best_model_name": best_model_name,
            "leaderboard": leaderboard,
            "target_classes": target_classes,
            "diagnostics": diagnostics,
            # Return preprocessed columns and data for SHAP computation
            "preprocessed_features": X.columns.tolist(),
            "X_train_mean": [float(v) for v in X_train.mean().values],
            "best_model_coef": self._approximate_coefficients(best_model, X_train_scaled, y_train, is_classification)
        }

    def _get_estimators(self, is_classification: bool, balancing: str) -> Dict[str, Any]:
        use_balanced = (balancing == "Class Weights")
        cw = "balanced" if use_balanced else None

        if is_classification:
            return {
                "Logistic Regression": LogisticRegression(max_iter=300, class_weight=cw, random_state=42),
                "Random Forest": RandomForestClassifier(n_estimators=50, max_depth=5, class_weight=cw, random_state=42),
                "Extra Trees": ExtraTreesClassifier(n_estimators=50, max_depth=5, class_weight=cw, random_state=42),
                "Gradient Boosting": GradientBoostingClassifier(n_estimators=40, max_depth=3, random_state=42),
                "AdaBoost": AdaBoostClassifier(n_estimators=40, random_state=42),
                "Decision Tree": DecisionTreeClassifier(max_depth=5, class_weight=cw, random_state=42),
                "Gaussian Naive Bayes": GaussianNB(),
                "K-Nearest Neighbors": KNeighborsClassifier(n_neighbors=5)
            }
        else:
            return {
                "Ridge Regression": Ridge(random_state=42),
                "Random Forest": RandomForestRegressor(n_estimators=50, max_depth=5, random_state=42),
                "Extra Trees": ExtraTreesRegressor(n_estimators=50, max_depth=5, random_state=42),
                "Gradient Boosting": GradientBoostingRegressor(n_estimators=40, max_depth=3, random_state=42),
                "AdaBoost": AdaBoostRegressor(n_estimators=40, random_state=42),
                "Decision Tree": DecisionTreeRegressor(max_depth=5, random_state=42),
                "K-Nearest Neighbors": KNeighborsRegressor(n_neighbors=5),
                "Support Vector Regressor (SVR)": SVR(C=1.0, epsilon=0.1)
            }

    def _random_oversample(self, X: pd.DataFrame, y: np.ndarray):
        from collections import Counter
        counter = Counter(y)
        max_class_count = max(counter.values())
        X_res_list, y_res_list = [], []
        for cls in counter.keys():
            cls_indices = np.where(y == cls)[0]
            choices = np.random.choice(cls_indices, max_class_count, replace=True)
            X_res_list.append(X.iloc[choices])
            y_res_list.append(y[choices])
        return pd.concat(X_res_list, axis=0), np.concatenate(y_res_list)

    def _random_undersample(self, X: pd.DataFrame, y: np.ndarray):
        from collections import Counter
        counter = Counter(y)
        min_class_count = min(counter.values())
        X_res_list, y_res_list = [], []
        for cls in counter.keys():
            cls_indices = np.where(y == cls)[0]
            choices = np.random.choice(cls_indices, min_class_count, replace=False)
            X_res_list.append(X.iloc[choices])
            y_res_list.append(y[choices])
        return pd.concat(X_res_list, axis=0), np.concatenate(y_res_list)

    def _calculate_cooks_distance(self, X: np.ndarray, y: np.ndarray) -> np.ndarray:
        # Add intercept column
        N, P = X.shape
        X_design = np.hstack([np.ones((N, 1)), X])
        
        # Fit OLS
        # Beta = (X^T X)^-1 X^T y
        try:
            XtX = X_design.T @ X_design
            # Add small ridge penalty to ensure invertibility
            XtX_inv = np.linalg.inv(XtX + np.eye(X_design.shape[1]) * 1e-5)
            beta = XtX_inv @ X_design.T @ y
            preds = X_design @ beta
            residuals = y - preds
            
            # Hat matrix diagonal
            # h_ii = x_i (X^T X)^-1 x_i^T
            # Leverage is the diagonal of X (X^T X)^-1 X^T
            leverage = np.sum((X_design @ XtX_inv) * X_design, axis=1)
            
            # MSE
            mse = np.sum(residuals ** 2) / (N - P - 1) if (N - P - 1) > 0 else np.sum(residuals ** 2) / N
            mse = max(mse, 1e-5)
            
            # Cook's distance
            # D_i = (e_i^2 / (p * mse)) * (h_ii / (1 - h_ii)^2)
            cooks = (residuals ** 2 / ((P + 1) * mse)) * (leverage / ((1.0 - leverage).clip(min=1e-5) ** 2))
            return cooks
        except Exception:
            return np.zeros(N)

    def _approximate_coefficients(self, model, X: np.ndarray, y: np.ndarray, is_classification: bool) -> List[float]:
        """
        Obtains linear feature attributions of the model.
        Fits regularized linear surrogate model to approximate model decisions.
        """
        try:
            # Predict train values
            preds = model.predict(X)
            
            # Fit Ridge Regression surrogate model on X to predict model predictions
            ridge = Ridge(alpha=1.0)
            ridge.fit(X, preds)
            
            return [float(c) for c in ridge.coef_]
        except Exception:
            return [0.0] * X.shape[1]


def compute_surrogate_shap(
    df: pd.DataFrame,
    target_column: str,
    preprocessed_columns: List[str],
    coefficients: List[float],
    row_index: Optional[int] = None
) -> Dict[str, Any]:
    """
    Computes surrogate SHAP values for the entire dataset.
    Formula: SHAP_ij = (X_ij - Mean_j) * beta_j
    """
    X_raw = df.drop(columns=[target_column], errors="ignore")
    
    # Preprocess identically to ensure shape alignment
    X = pd.DataFrame()
    for col in preprocessed_columns:
        if col in X_raw.columns:
            if pd.api.types.is_numeric_dtype(X_raw[col]):
                X[col] = X_raw[col].fillna(X_raw[col].median()).astype(float)
            else:
                le = LabelEncoder()
                X[col] = le.fit_transform(X_raw[col].astype(str).fillna("Missing")).astype(float)
        else:
            X[col] = 0.0 # fallback

    X_scaled = StandardScaler().fit_transform(X)
    
    # Calculate SHAP values
    shap_vals = np.zeros_like(X_scaled)
    for j, coef in enumerate(coefficients):
        # Scale values: SHAP = X_scaled * coef
        shap_vals[:, j] = X_scaled[:, j] * coef

    # 1. Global Beeswarm plot data
    # Attributions: list of {"feature": col, "shap_values": [], "feature_values": []}
    attributions = []
    for j, col in enumerate(preprocessed_columns):
        # Scale feature values between 0 and 1 for legend color coding
        vals = X_scaled[:, j]
        v_min, v_max = vals.min(), vals.max()
        val_range = (v_max - v_min) if (v_max - v_min) > 0 else 1.0
        normalized_vals = (vals - v_min) / val_range
        
        # Downsample to top 200 points to keep beeswarm rendering quick
        indices = np.arange(len(vals))
        if len(vals) > 200:
            np.random.seed(42)
            indices = np.random.choice(len(vals), 200, replace=False)
            
        attributions.append({
            "feature": col,
            "shap_values": [float(shap_vals[idx, j]) for idx in indices],
            "feature_values": [float(normalized_vals[idx]) for idx in indices]
        })

    # Sort attributions by mean absolute SHAP value descending
    mean_abs_shaps = [float(np.mean(np.abs(shap_vals[:, j]))) for j in range(len(preprocessed_columns))]
    sorted_indices = np.argsort(mean_abs_shaps)[::-1]
    
    attributions = [attributions[idx] for idx in sorted_indices]

    # 2. Local Waterfall data
    waterfall = None
    if row_index is not None and 0 <= row_index < len(X):
        # Calculate local attributions
        local_attributions = []
        base_value = float(np.mean(shap_vals))
        
        for j, col in enumerate(preprocessed_columns):
            local_attributions.append({
                "feature": col,
                "shap_val": float(shap_vals[row_index, j]),
                "raw_val": str(df.iloc[row_index].get(col, ""))
            })
            
        # Sort local attributions by magnitude
        local_attributions = sorted(local_attributions, key=lambda x: abs(x["shap_val"]), reverse=True)
        
        waterfall = {
            "row_index": row_index,
            "base_value": base_value,
            "prediction": float(base_value + np.sum(shap_vals[row_index])),
            "features": local_attributions
        }

    # 3. Feature Interaction (for dependence plot)
    # Find the feature that correlates most with the selected feature's SHAP values
    interaction_mapping = {}
    for j, col in enumerate(preprocessed_columns):
        # Compare SHAP values correlation with other features
        corr_coefs = []
        for k in range(len(preprocessed_columns)):
            if j == k:
                continue
            r = np.corrcoef(shap_vals[:, j], X_scaled[:, k])[0, 1]
            corr_coefs.append((k, abs(r) if not np.isnan(r) else 0.0))
            
        # Sort and get highest correlated feature
        if corr_coefs:
            best_interact_idx = sorted(corr_coefs, key=lambda x: x[1], reverse=True)[0][0]
            interaction_mapping[col] = preprocessed_columns[best_interact_idx]
        else:
            interaction_mapping[col] = col

    return {
        "status": "success",
        "attributions": attributions,
        "waterfall": waterfall,
        "interaction_mapping": interaction_mapping,
        "raw_features_data": {
            col: [float(v) for v in X[col].values]
            for col in preprocessed_columns
        },
        "shap_values_data": {
            col: [float(v) for v in shap_vals[:, idx]]
            for idx, col in enumerate(preprocessed_columns)
        }
    }
