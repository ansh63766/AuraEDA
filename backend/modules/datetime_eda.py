import pandas as pd
import numpy as np
from typing import Dict, Any, List
from backend.analyzer_base import BaseAnalyzerModule

class DatetimeEdaModule(BaseAnalyzerModule):
    @property
    def name(self) -> str:
        return "datetime_eda"

    @property
    def display_name(self) -> str:
        return "Advanced Datetime & Seasonality Audit"

    def run(self, df: pd.DataFrame, target_column: str = None) -> Dict[str, Any]:
        datetime_features = {}

        for col in df.columns:
            series = df[col]
            
            # Skip if already a known datatype that isn't date-like
            if pd.api.types.is_numeric_dtype(series):
                continue
                
            # Test parsing a sample to see if it's date-like
            sample = series.dropna().head(100)
            if len(sample) < 5:
                continue

            try:
                # Attempt to convert to datetime
                parsed = pd.to_datetime(sample, errors="coerce")
                valid_ratio = parsed.notnull().sum() / len(sample)
                
                # If >60% of non-null samples parse as datetime, treat column as datetime
                if valid_ratio > 0.60:
                    # Full parse
                    full_parsed = pd.to_datetime(series, errors="coerce")
                    valid_series = full_parsed.dropna().sort_values()
                    
                    if len(valid_series) < 5:
                        continue

                    min_date = valid_series.min()
                    max_date = valid_series.max()
                    date_range_days = (max_date - min_date).days

                    # 1. Timeline Trend (group by week or month to get a smooth curve)
                    # Determine frequency based on range
                    if date_range_days > 365 * 2:
                        freq = "ME" # group by month end
                    elif date_range_days > 60:
                        freq = "W"  # group by week
                    else:
                        freq = "D"  # group by day
                        
                    timeline = valid_series.value_counts().resample(freq).sum()
                    timeline_labels = [str(x.date()) for x in timeline.index]
                    timeline_counts = [int(x) for x in timeline.values]

                    # 2. Seasonality Decompositions
                    # Hourly
                    hour_counts = valid_series.dt.hour.value_counts().reindex(range(24), fill_value=0)
                    hourly_data = {
                        "labels": [f"{h:02d}:00" for h in range(24)],
                        "counts": [int(x) for x in hour_counts.values]
                    }

                    # Weekly (0=Monday, 6=Sunday)
                    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                    weekly_counts = valid_series.dt.dayofweek.value_counts().reindex(range(7), fill_value=0)
                    weekly_data = {
                        "labels": day_names,
                        "counts": [int(x) for x in weekly_counts.values]
                    }

                    # Monthly (1=Jan, 12=Dec)
                    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                    monthly_counts = valid_series.dt.month.value_counts().reindex(range(1, 13), fill_value=0)
                    monthly_data = {
                        "labels": month_names,
                        "counts": [int(x) for x in monthly_counts.values]
                    }

                    datetime_features[col] = {
                        "column": col,
                        "min_date": str(min_date),
                        "max_date": str(max_date),
                        "range_days": int(date_range_days),
                        "timeline": {
                            "labels": timeline_labels,
                            "counts": timeline_counts
                        },
                        "hourly": hourly_data,
                        "weekly": weekly_data,
                        "monthly": monthly_data
                    }
            except Exception:
                continue

        if not datetime_features:
            return {
                "status": "bypassed",
                "message": "No date/time columns detected in the dataset."
            }

        return {
            "status": "success",
            "features": datetime_features
        }