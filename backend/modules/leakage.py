import pandas as pd
import numpy as np
from typing import Dict, Any, List
from backend.analyzer_base import BaseAnalyzerModule
from sklearn.feature_selection import mutual_info_classif, mutual_info_regression
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import LabelEncoder

class LeakageModule(BaseAnalyzerModule):
    @property
    def name(self) -> str:
        return "leakage"

    @property
    def display_name(self) -> str:
        return "Target Leakage Detection"

    def run(self, df: pd.DataFrame, target_column: str = None) -> Dict[str, Any]:
        if not target_column or target_column not in df.columns:
            return {
                "status": "waiting",
                "message": "Please select a target variable in the dashboard to execute Target Leakage Analysis."
            }

        # Setup target
        target = df[target_column]
        if target.isnull().all():
            return {
                "status": "error",
                "message": f"Target column '{target_column}' is entirely missing."
            }

        # Keep non-null target rows
        valid_idx = target.notnull()
        target = target[valid_idx]
        df_valid = df[valid_idx].copy()

        n_rows = len(df_valid)
        if n_rows < 10:
            return {
                "status": "error",
                "message": "Too few rows to perform reliable leakage analysis (minimum 10 rows)."
            }

        # Subsample if dataset is too large (speed and memory safety)
        if n_rows > 5000:
            df_valid = df_valid.sample(n=5000, random_state=42)
            target = df_valid[target_column]
            n_rows = 5000

        # Determine target type
        target_unique = target.nunique()
        is_classification = False
        if not pd.api.types.is_numeric_dtype(target) or target_unique < 15:
            is_classification = True

        # Preprocess target
        if is_classification:
            le = LabelEncoder()
            y = le.fit_transform(target.astype(str))
            n_classes = len(np.unique(y))
        else:
            y = target.values.astype(float)

        leakage_results = []
        
        # Prepare feature dataframes
        for col in df_valid.columns:
            if col == target_column:
                continue

            col_series = df_valid[col]
            # Skip columns that are entirely missing
            if col_series.isnull().all():
                continue

            # Skip columns with zero variance
            if col_series.nunique() <= 1:
                continue

            # Fill missing values for ML modeling
            is_num = pd.api.types.is_numeric_dtype(col_series)
            if is_num:
                col_filled = col_series.fillna(col_series.median())
                X_feat = col_filled.values.reshape(-1, 1)
            else:
                col_filled = col_series.astype(str).fillna("Missing")
                # Label encode categorical column
                le_feat = LabelEncoder()
                X_feat = le_feat.fit_transform(col_filled).reshape(-1, 1)

            # 1. Compute Mutual Information
            try:
                if is_classification:
                    mi = float(mutual_info_classif(X_feat, y, random_state=42)[0])
                else:
                    mi = float(mutual_info_regression(X_feat, y, random_state=42)[0])
            except Exception:
                mi = 0.0

            # 2. Compute Single-Feature Model performance (cross-validated AUC or R2)
            cv_score = 0.0
            metric_name = "Accuracy"
            
            try:
                if is_classification:
                    model = DecisionTreeClassifier(max_depth=3, random_state=42)
                    if n_classes == 2:
                        # ROC-AUC is standard for binary classification
                        scores = cross_val_score(model, X_feat, y, cv=3, scoring="roc_auc")
                        cv_score = float(np.mean(scores))
                        metric_name = "ROC-AUC"
                    else:
                        # Multi-class accuracy
                        scores = cross_val_score(model, X_feat, y, cv=3, scoring="accuracy")
                        cv_score = float(np.mean(scores))
                        metric_name = "Accuracy"
                else:
                    model = DecisionTreeRegressor(max_depth=3, random_state=42)
                    scores = cross_val_score(model, X_feat, y, cv=3, scoring="r2")
                    cv_score = float(np.mean(scores))
                    metric_name = "R²"
            except Exception:
                cv_score = 0.0

            # 3. Simple Correlation
            corr_val = 0.0
            if is_num and pd.api.types.is_numeric_dtype(target):
                try:
                    corr_val = float(col_series.corr(target, method="pearson"))
                except Exception:
                    pass

            # Classify Leakage Risk
            # If cross-validation metric is extremely high, flag it as leakage risk
            risk = "low"
            reason = "Feature shows normal predictive power."

            if is_classification:
                if metric_name == "ROC-AUC" and cv_score >= 1.0:
                    risk = "high"
                    reason = f"Confirmed Target Leakage! Perfect ROC-AUC of {cv_score:.2f} using only this feature."
                elif metric_name == "ROC-AUC" and cv_score > 0.95:
                    risk = "medium"
                    reason = f"Suspected Target Leakage. High ROC-AUC of {cv_score:.2f} using only this feature."
                elif metric_name == "Accuracy" and cv_score >= 1.0 and n_classes > 2:
                    risk = "high"
                    reason = f"Confirmed Target Leakage! Perfect Accuracy of {cv_score:.2f} using only this feature."
                elif metric_name == "Accuracy" and cv_score > 0.95 and n_classes > 2:
                    risk = "medium"
                    reason = f"Suspected Target Leakage. High Accuracy of {cv_score:.2f} using only this feature."
                elif mi > 1.2:
                    risk = "high"
                    reason = f"Mutual Information is extremely high ({mi:.3f}), indicating shared info."
                elif (metric_name == "ROC-AUC" and cv_score > 0.85) or mi > 0.6:
                    risk = "medium"
                    reason = f"High correlation/association (ROC-AUC: {cv_score:.2f}, MI: {mi:.3f})."
            else:
                if cv_score >= 1.0 or abs(corr_val) >= 1.0:
                    risk = "high"
                    reason = f"Confirmed Target Leakage! R² is {cv_score:.2f} or Pearson Correlation is {corr_val:.2f}, indicating duplicate target."
                elif cv_score > 0.95 or abs(corr_val) > 0.95:
                    risk = "medium"
                    reason = f"Suspected Target Leakage. R² is {cv_score:.2f} or Pearson Correlation is {corr_val:.2f}."
                elif cv_score > 0.70 or abs(corr_val) > 0.75:
                    risk = "medium"
                    reason = f"High correlation with target (R²: {cv_score:.2f}, Pearson Corr: {corr_val:.2f})."

            leakage_results.append({
                "column": col,
                "mutual_info": mi,
                "cv_score": cv_score,
                "metric_name": metric_name,
                "correlation": corr_val,
                "risk": risk,
                "reason": reason
            })

        # Sort results: high risk first, then by mutual info descending
        risk_map = {"high": 3, "medium": 2, "low": 1}
        leakage_results = sorted(leakage_results, key=lambda x: (risk_map[x["risk"]], x["mutual_info"]), reverse=True)

        return {
            "status": "success",
            "target_column": target_column,
            "target_type": "classification" if is_classification else "regression",
            "leakage_features": leakage_results
        }
