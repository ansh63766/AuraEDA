import pandas as pd
import numpy as np
from typing import Dict, Any, List
from backend.analyzer_base import BaseAnalyzerModule

class DistributionModule(BaseAnalyzerModule):
    @property
    def name(self) -> str:
        return "distributions"

    @property
    def display_name(self) -> str:
        return "Feature Distributions & Outliers"

    def run(self, df: pd.DataFrame, target_column: str = None) -> Dict[str, Any]:
        n_rows = len(df)
        features = {}

        for col in df.columns:
            # Basic info
            col_series = df[col]
            null_count = int(col_series.isnull().sum())
            unique_count = int(col_series.nunique())
            
            # Determine high-level variable type
            if pd.api.types.is_numeric_dtype(col_series):
                is_numeric = True
                type_name = "numerical"
            elif pd.api.types.is_datetime64_any_dtype(col_series):
                is_numeric = False
                type_name = "datetime"
            else:
                is_numeric = False
                type_name = "categorical"

            # Zero values (only for numeric columns)
            zero_count = 0
            zero_rate = 0.0
            if is_numeric:
                zero_count = int((col_series == 0).sum())
                zero_rate = float(zero_count / n_rows) if n_rows > 0 else 0.0

            # Base metadata
            col_meta = {
                "name": col,
                "type": type_name,
                "null_count": null_count,
                "null_rate": float(null_count / n_rows) if n_rows > 0 else 0.0,
                "zero_count": zero_count,
                "zero_rate": zero_rate,
                "unique_count": unique_count,
                "cardinality_ratio": float(unique_count / n_rows) if n_rows > 0 else 0.0,
            }

            non_null_series = col_series.dropna()
            
            if len(non_null_series) == 0:
                col_meta["stats"] = {}
                col_meta["plot_data"] = {}
                features[col] = col_meta
                continue

            if is_numeric:
                # Compute descriptive statistics
                mean_val = float(non_null_series.mean())
                median_val = float(non_null_series.median())
                min_val = float(non_null_series.min())
                max_val = float(non_null_series.max())
                std_val = float(non_null_series.std()) if len(non_null_series) > 1 else 0.0
                
                skew_val = float(non_null_series.skew()) if len(non_null_series) > 2 else 0.0
                kurt_val = float(non_null_series.kurt()) if len(non_null_series) > 2 else 0.0

                # Quantiles (extended to include P1, P5, P95, P99)
                quantiles = {}
                try:
                    q_vals = np.percentile(non_null_series, [1, 5, 10, 25, 50, 75, 90, 95, 99])
                    quantiles = {
                        "q01": float(q_vals[0]),
                        "q05": float(q_vals[1]),
                        "q10": float(q_vals[2]),
                        "q25": float(q_vals[3]),
                        "q50": float(q_vals[4]),
                        "q75": float(q_vals[5]),
                        "q90": float(q_vals[6]),
                        "q95": float(q_vals[7]),
                        "q99": float(q_vals[8])
                    }
                except Exception:
                    pass

                # Outlier detection (IQR)
                outlier_count = 0
                outlier_rate = 0.0
                if "q25" in quantiles and "q75" in quantiles:
                    q25 = quantiles["q25"]
                    q75 = quantiles["q75"]
                    iqr = q75 - q25
                    if iqr > 0:
                        lower_bound = q25 - 1.5 * iqr
                        upper_bound = q75 + 1.5 * iqr
                        outliers = non_null_series[(non_null_series < lower_bound) | (non_null_series > upper_bound)]
                        outlier_count = int(len(outliers))
                        outlier_rate = float(outlier_count / len(non_null_series))

                col_meta["stats"] = {
                    "mean": mean_val,
                    "median": median_val,
                    "min": min_val,
                    "max": max_val,
                    "std": std_val,
                    "skewness": skew_val,
                    "kurtosis": kurt_val,
                    "quantiles": quantiles,
                    "outlier_count": outlier_count,
                    "outlier_rate": outlier_rate
                }

                # Histogram data
                try:
                    # Determine number of bins using Freedman-Diaconis rule or fallback
                    bins_count = 20
                    if len(non_null_series) > 10:
                        counts, bin_edges = np.histogram(non_null_series, bins=bins_count)
                        bin_labels = []
                        for i in range(len(bin_edges) - 1):
                            bin_labels.append(f"{bin_edges[i]:.2f} - {bin_edges[i+1]:.2f}")
                        
                        # Generate simple smoothed KDE-like curve using moving average of counts
                        smoothed = list(counts)
                        if len(counts) > 2:
                            for idx in range(1, len(counts) - 1):
                                smoothed[idx] = float((counts[idx-1] + counts[idx] + counts[idx+1]) / 3)

                        col_meta["plot_data"] = {
                            "histogram": {
                                "labels": bin_labels,
                                "counts": counts.tolist(),
                                "kde": [float(x) for x in smoothed]
                            }
                        }
                except Exception as e:
                    col_meta["plot_data"] = {"error": f"Could not compute histogram: {str(e)}"}

            else:
                # Categorical column
                val_counts = non_null_series.value_counts()
                top_category = str(val_counts.index[0]) if len(val_counts) > 0 else "N/A"
                top_freq = int(val_counts.iloc[0]) if len(val_counts) > 0 else 0
                top_rate = float(top_freq / len(non_null_series)) if len(non_null_series) > 0 else 0.0

                col_meta["stats"] = {
                    "top_category": top_category,
                    "top_frequency": top_freq,
                    "top_rate": top_rate,
                    "cardinality": unique_count
                }

                # Categorical distribution plot data (limit to top 15 and group rest as 'Other')
                try:
                    max_cats = 15
                    if len(val_counts) > max_cats:
                        top_cats = val_counts.iloc[:max_cats]
                        other_sum = val_counts.iloc[max_cats:].sum()
                        
                        labels = [str(x) for x in top_cats.index] + ["Other"]
                        counts = [int(x) for x in top_cats.values] + [int(other_sum)]
                    else:
                        labels = [str(x) for x in val_counts.index]
                        counts = [int(x) for x in val_counts.values]

                    col_meta["plot_data"] = {
                        "bar_chart": {
                            "labels": labels,
                            "counts": counts
                        }
                    }
                except Exception as e:
                    col_meta["plot_data"] = {"error": f"Could not compute categorical distributions: {str(e)}"}

            features[col] = col_meta

        return {
            "features": features
        }
