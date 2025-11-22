import pandas as pd
import numpy as np
from typing import Dict, Any, List
from backend.analyzer_base import BaseAnalyzerModule
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA

class PcaModule(BaseAnalyzerModule):
    @property
    def name(self) -> str:
        return "pca"

    @property
    def display_name(self) -> str:
        return "Dimensionality Reduction & PCA Projection"

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
                "message": "PCA requires at least 2 numerical features."
            }

        # Impute and standardize
        X = df[numeric_cols].apply(lambda x: x.fillna(x.median()))
        
        # Remove zero variance columns
        valid_cols = [c for c in numeric_cols if X[c].std() > 0]
        if len(valid_cols) < 2:
            return {
                "status": "bypassed",
                "message": "PCA requires at least 2 numerical features with non-zero variance."
            }

        X = X[valid_cols]

        try:
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)

            # Fit PCA
            pca = PCA(n_components=2, random_state=42)
            coords = pca.fit_transform(X_scaled)
            explained_variance = [float(v) for v in pca.explained_variance_ratio_]

            # Limit data points to prevent client-side chart overload
            sample_size = min(len(coords), 1000)
            indices = np.arange(len(coords))
            if len(coords) > 1000:
                # Random sample
                np.random.seed(42)
                indices = np.random.choice(len(coords), size=1000, replace=False)
            
            points = []
            targets = []
            has_target = target_column is not None and target_column in df.columns
            
            for idx in indices:
                points.append({
                    "pc1": float(coords[idx, 0]),
                    "pc2": float(coords[idx, 1])
                })
                if has_target:
                    # Cast target to string/serializable for legend grouping
                    val = df.iloc[idx][target_column]
                    targets.append(str(val) if pd.notnull(val) else "Missing")

            return {
                "status": "success",
                "explained_variance": explained_variance,
                "points": points,
                "targets": targets,
                "columns_used": valid_cols
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"PCA failed: {str(e)}"
            }