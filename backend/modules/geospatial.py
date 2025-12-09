import pandas as pd
import numpy as np
from typing import Dict, Any, List
from backend.analyzer_base import BaseAnalyzerModule
from sklearn.cluster import DBSCAN

US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME",
    "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA",
    "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"
}

class GeospatialModule(BaseAnalyzerModule):
    @property
    def name(self) -> str:
        return "geospatial"

    @property
    def display_name(self) -> str:
        return "Geospatial Diagnostics & Clustering"

    def run(self, df: pd.DataFrame, target_column: str = None) -> Dict[str, Any]:
        """
        Auto-scans columns to detect if latitude/longitude coordinate fields or US states exist.
        """
        lat_cols = []
        lon_cols = []
        state_cols = []

        for col in df.columns:
            col_lower = str(col).lower()
            
            # Check for coordinates
            if pd.api.types.is_numeric_dtype(df[col]):
                if any(x in col_lower for x in ["lat", "latitude"]) and "plat" not in col_lower:
                    lat_cols.append(col)
                elif any(x in col_lower for x in ["lon", "lng", "longitude", "long"]):
                    lon_cols.append(col)
            
            # Check for US state codes
            else:
                non_null = df[col].dropna().astype(str).str.strip().str.upper()
                if len(non_null) > 10:
                    sample = non_null.head(50)
                    match_ratio = sum(s in US_STATES for s in sample) / len(sample)
                    if match_ratio > 0.70:
                        state_cols.append(col)

        status = "success" if (lat_cols and lon_cols) or state_cols else "bypassed"

        return {
            "status": status,
            "detected_lat_columns": lat_cols,
            "detected_lon_columns": lon_cols,
            "detected_state_columns": state_cols
        }

    def analyze_spatial(self, df: pd.DataFrame, lat_col: str, lon_col: str, color_col: str = None, eps: float = 0.5, min_samples: int = 5) -> Dict[str, Any]:
        """
        Filters non-null spatial coordinates, performs DBSCAN clustering, and formats spatial points.
        """
        try:
            cols = [lat_col, lon_col]
            if color_col and color_col in df.columns:
                cols.append(color_col)

            spatial_df = df[cols].dropna()
            
            if len(spatial_df) == 0:
                return {
                    "status": "error",
                    "message": "No overlapping non-null rows found for coordinates."
                }

            # Downsample to max 5000 points to keep client rendering interactive and smooth
            if len(spatial_df) > 5000:
                spatial_df = spatial_df.sample(n=5000, random_state=42)

            coords = spatial_df[[lat_col, lon_col]].values

            # Run DBSCAN
            try:
                db = DBSCAN(eps=float(eps), min_samples=int(min_samples))
                cluster_labels = db.fit_predict(coords)
            except Exception as e:
                cluster_labels = np.zeros(len(coords), dtype=int)

            points = []
            for i, row in enumerate(spatial_df.values):
                lat = float(row[0])
                lon = float(row[1])
                cluster_id = int(cluster_labels[i])
                
                pt = {
                    "lat": lat,
                    "lon": lon,
                    "cluster_id": cluster_id
                }
                
                if color_col:
                    val = row[2]
                    pt["color_value"] = str(val) if not isinstance(val, (int, float)) else float(val)

                points.append(pt)

            # Aggregate cluster stats
            unique_clusters = set(cluster_labels)
            n_clusters = len(unique_clusters - {-1})
            noise_points = int(sum(cluster_labels == -1))

            return {
                "status": "success",
                "points": points,
                "n_clusters": n_clusters,
                "noise_points": noise_points,
                "color_column_type": str(df[color_col].dtype) if color_col else None
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Geospatial clustering failed: {str(e)}"
            }

    def analyze_choropleth(self, df: pd.DataFrame, state_col: str, value_col: str) -> Dict[str, Any]:
        """
        Aggregates metric values by US State codes for client-side choropleth maps.
        """
        try:
            temp_df = df[[state_col, value_col]].dropna()
            temp_df[state_col] = temp_df[state_col].astype(str).str.strip().str.upper()
            
            # Only keep valid US states
            temp_df = temp_df[temp_df[state_col].isin(US_STATES)]
            
            if len(temp_df) == 0:
                return {
                    "status": "error",
                    "message": "No valid US State codes found in data."
                }

            is_numeric = pd.api.types.is_numeric_dtype(df[value_col])
            
            if is_numeric:
                agg = temp_df.groupby(state_col)[value_col].mean().to_dict()
                agg_type = "mean"
            else:
                # For categorical, do a count of rows
                agg = temp_df.groupby(state_col).size().to_dict()
                agg_type = "count"

            # Format to JSON
            state_data = [{"state": k, "value": float(v)} for k, v in agg.items()]

            return {
                "status": "success",
                "type": agg_type,
                "data": state_data
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Choropleth aggregation failed: {str(e)}"
            }
