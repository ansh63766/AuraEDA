import numpy as np
import pandas as pd
from typing import Dict, Any, List

class WhatIfBiasModule:
    """
    Handles What-If feature predictions and demographic fairness audits.
    """
    def __init__(self):
        pass

    def run_whatif_prediction(self, state: Dict[str, Any], features_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes model prediction on a single user-specified features row.
        """
        model = state.get("best_model_obj")
        scaler = state.get("scaler_obj")
        meta = state.get("preprocessing_meta")
        automl_res = state.get("automl_results")

        if not model or not scaler or not meta or not automl_res:
            return {"status": "error", "message": "No active model trained. Please run AutoML training first."}

        preprocessed_cols = automl_res["preprocessed_features"]
        is_classification = automl_res["is_classification"]
        target_classes = automl_res.get("target_classes", [])

        # Process input row
        row_data = []
        for col in preprocessed_cols:
            col_meta = meta.get(col)
            val = features_dict.get(col)

            if col_meta["type"] == "numeric":
                if val is None or val == "":
                    val = col_meta["median"]
                else:
                    try:
                        val = float(val)
                    except ValueError:
                        val = col_meta["median"]
                row_data.append(val)
            else:
                # Categorical
                val_str = str(val).strip() if val is not None else "Missing"
                le = col_meta["encoder"]
                # Safe transform: fallback to "Missing" or first category if unseen
                if val_str in le.classes_:
                    encoded_val = float(le.transform([val_str])[0])
                elif "Missing" in le.classes_:
                    encoded_val = float(le.transform(["Missing"])[0])
                else:
                    encoded_val = 0.0
                row_data.append(encoded_val)

        # Scale and predict
        row_arr = np.array(row_data).reshape(1, -1)
        row_scaled = scaler.transform(row_arr)

        pred_val = model.predict(row_scaled)[0]
        
        result = {
            "status": "success",
            "prediction": float(pred_val) if not is_classification else int(pred_val)
        }

        # Include probabilities if classification and supported
        if is_classification:
            if hasattr(model, "predict_proba"):
                probs = model.predict_proba(row_scaled)[0]
                result["probabilities"] = [float(p) for p in probs]
                if len(target_classes) > 0:
                    result["predicted_class_label"] = str(target_classes[int(pred_val)])
                    result["class_probabilities"] = {
                        str(target_classes[idx]): float(probs[idx])
                        for idx in range(len(target_classes))
                    }
            else:
                result["predicted_class_label"] = str(target_classes[int(pred_val)]) if len(target_classes) > int(pred_val) else str(pred_val)

        return result

    def run_fairness_audit(
        self,
        df: pd.DataFrame,
        target_column: str,
        protected_attribute: str,
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Runs demographic parity and equalized odds fairness audits on a protected attribute.
        """
        model = state.get("best_model_obj")
        scaler = state.get("scaler_obj")
        meta = state.get("preprocessing_meta")
        automl_res = state.get("automl_results")

        if not model or not scaler or not meta or not automl_res:
            return {"status": "error", "message": "No trained model found. Train AutoML before auditing."}

        if protected_attribute not in df.columns:
            return {"status": "error", "message": f"Protected attribute '{protected_attribute}' not in dataset."}

        preprocessed_cols = automl_res["preprocessed_features"]
        is_classification = automl_res["is_classification"]
        target_classes = automl_res.get("target_classes", [])

        # Clean null values in target or protected attribute
        df_valid = df.dropna(subset=[target_column, protected_attribute]).copy()
        if len(df_valid) < 10:
            return {"status": "error", "message": "Not enough rows to perform fairness audit (minimum 10 rows required)."}

        # Extract features
        X_raw = df_valid[preprocessed_cols]
        y_true = df_valid[target_column]

        # Preprocess features identically
        X_processed = pd.DataFrame()
        for col in preprocessed_cols:
            col_meta = meta.get(col)
            if col_meta["type"] == "numeric":
                X_processed[col] = X_raw[col].fillna(col_meta["median"]).astype(float)
            else:
                le = col_meta["encoder"]
                X_processed[col] = X_raw[col].astype(str).fillna("Missing").map(
                    lambda val: le.transform([val])[0] if val in le.classes_ else (
                        le.transform(["Missing"])[0] if "Missing" in le.classes_ else 0
                    )
                ).astype(float)

        X_scaled = scaler.transform(X_processed)
        y_pred = model.predict(X_scaled)

        # For regression, binarize targets and predictions using their median values to make rate comparisons possible
        if not is_classification:
            median_true = y_true.median()
            y_true_bin = (y_true > median_true).astype(int).values
            y_pred_bin = (y_pred > median_true).astype(int)
        else:
            # Map target labels to binary
            from sklearn.preprocessing import LabelEncoder
            le_target = LabelEncoder()
            y_true_bin = le_target.fit_transform(y_true.astype(str))
            # Assume 1 is positive class
            y_pred_bin = y_pred

        # Group metrics calculation
        groups = df_valid[protected_attribute].unique()
        group_metrics = {}
        
        for g in groups:
            indices = np.where(df_valid[protected_attribute] == g)[0]
            g_total = len(indices)
            if g_total == 0:
                continue

            g_pred = y_pred_bin[indices]
            g_true = y_true_bin[indices]
            
            pos_preds = int(np.sum(g_pred == 1))
            selection_rate = pos_preds / g_total
            
            # Confusion matrix metrics for Equalized Odds (TPR, FPR)
            tp = int(np.sum((g_pred == 1) & (g_true == 1)))
            fp = int(np.sum((g_pred == 1) & (g_true == 0)))
            fn = int(np.sum((g_pred == 0) & (g_true == 1)))
            tn = int(np.sum((g_pred == 0) & (g_true == 0)))
            
            tpr = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
            
            group_metrics[str(g)] = {
                "total": g_total,
                "positive_predictions": pos_preds,
                "selection_rate": selection_rate,
                "tpr": tpr,
                "fpr": fpr
            }

        # Define privileged group (group with the maximum selection rate)
        if not group_metrics:
            return {"status": "error", "message": "No groups evaluated."}
            
        privileged_group = max(group_metrics, key=lambda k: group_metrics[k]["selection_rate"])
        priv_rate = group_metrics[privileged_group]["selection_rate"]
        priv_tpr = group_metrics[privileged_group]["tpr"]
        priv_fpr = group_metrics[privileged_group]["fpr"]

        audit_results = []
        for g, m in group_metrics.items():
            sel_rate = m["selection_rate"]
            
            # Disparate Impact Ratio: Group Selection Rate / Privileged Selection Rate
            dir_val = sel_rate / priv_rate if priv_rate > 0 else 1.0
            # Clip dir to avoid float overflow
            dir_val = min(dir_val, 10.0)
            
            # Demographic Parity Difference
            dp_diff = priv_rate - sel_rate
            
            # Equalized Odds Differences
            tpr_diff = abs(priv_tpr - m["tpr"])
            fpr_diff = abs(priv_fpr - m["fpr"])
            
            # Traffic-light status (DIR >= 0.8 is PASS, 0.5 <= DIR < 0.8 is WARNING, DIR < 0.5 is FAIL)
            if dir_val >= 0.8:
                status = "PASS"
                color = "green"
            elif dir_val >= 0.5:
                status = "WARNING"
                color = "orange"
            else:
                status = "FAIL"
                color = "red"

            audit_results.append({
                "group": g,
                "size": m["total"],
                "selection_rate": float(sel_rate),
                "disparate_impact_ratio": float(dir_val),
                "demographic_parity_diff": float(dp_diff),
                "equalized_odds_tpr_diff": float(tpr_diff),
                "equalized_odds_fpr_diff": float(fpr_diff),
                "status": status,
                "color": color,
                "is_privileged": (g == privileged_group)
            })

        return {
            "status": "success",
            "protected_attribute": protected_attribute,
            "privileged_group": privileged_group,
            "privileged_selection_rate": float(priv_rate),
            "audit": audit_results
        }
