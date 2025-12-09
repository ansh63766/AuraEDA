import pandas as pd
import numpy as np
from typing import Dict, Any, List
from backend.analyzer_base import BaseAnalyzerModule
import scipy.stats as stats
from statsmodels.tsa.stattools import adfuller, acf, pacf
from statsmodels.tsa.seasonal import seasonal_decompose

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

    def analyze_time_series(self, df: pd.DataFrame, date_col: str, num_col: str, lag: int = 1) -> Dict[str, Any]:
        """
        Executes intensive time series diagnostic suite:
        - STL-like seasonal decompose
        - Lag plot data
        - ACF/PACF calculations
        - Augmented Dickey-Fuller (ADF) stationarity test
        - Z-score time spikes
        - Seasonality heatmap grid
        """
        try:
            # Parse dates and numeric columns, drop nulls and sort
            ts_df = pd.DataFrame({
                "date": pd.to_datetime(df[date_col], errors="coerce"),
                "value": pd.to_numeric(df[num_col], errors="coerce")
            }).dropna().sort_values("date")

            if len(ts_df) < 15:
                return {
                    "status": "error",
                    "message": f"Insufficient data ({len(ts_df)} rows) after parsing dates/numeric columns."
                }

            ts_df = ts_df.set_index("date")
            series = ts_df["value"]

            # 1. ADF Stationarity Test
            try:
                adf_res = adfuller(series.values)
                adf_stat = float(adf_res[0])
                adf_p = float(adf_res[1])
                adf_crit = {k: float(v) for k, v in adf_res[4].items()}
                stationary = adf_p < 0.05
                adf_interpretation = (
                    f"Stationary (p = {adf_p:.4f} < 0.05). The series shows no unit root "
                    "and has a stable mean/variance over time."
                    if stationary else
                    f"Non-stationary (p = {adf_p:.4f} >= 0.05). The series possesses a unit root, "
                    "indicating trend or seasonality variance requiring differencing."
                )
            except Exception as e:
                adf_stat, adf_p, adf_crit = 0.0, 1.0, {}
                adf_interpretation = f"ADF test failed: {str(e)}"

            # 2. Estimate Seasonality Period for Decomposition
            inferred_freq = pd.infer_freq(series.index)
            period = 7  # Daily default (weekly cycle)
            if inferred_freq:
                if 'H' in inferred_freq:
                    period = 24
                elif 'D' in inferred_freq:
                    period = 7
                elif 'W' in inferred_freq:
                    period = 4
                elif 'M' in inferred_freq:
                    period = 12
            else:
                # Guess based on median timedelta
                diffs = pd.Series(series.index).diff().dropna()
                if not diffs.empty:
                    median_diff_secs = diffs.dt.total_seconds().median()
                    if median_diff_secs < 7200:      # Hourly-ish
                        period = 24
                    elif median_diff_secs < 100000:   # Daily-ish
                        period = 7
                    elif median_diff_secs < 650000:   # Weekly-ish
                        period = 4
                    elif median_diff_secs < 2800000:  # Monthly-ish
                        period = 12

            # Ensure period fits within dataset size
            if len(series) <= period * 2:
                period = max(2, len(series) // 3)

            # 3. Seasonal Decompose (STL Alternative)
            try:
                decomp = seasonal_decompose(series, model="additive", period=period)
                # Fill missing indices at boundaries
                trend = decomp.trend.bfill().ffill().tolist()
                seasonal = decomp.seasonal.tolist()
                residual = decomp.resid.fillna(0.0).tolist()
            except Exception as e:
                # Fallback to simple moving average trend
                trend = series.rolling(window=max(2, period), center=True).mean().bfill().ffill().tolist()
                seasonal = [0.0] * len(series)
                residual = (series - pd.Series(trend, index=series.index)).tolist()

            # 4. ACF & PACF
            try:
                nlags = min(30, len(series) // 2 - 1)
                if nlags > 0:
                    acf_vals = acf(series.values, nlags=nlags).tolist()
                    pacf_vals = pacf(series.values, nlags=nlags, method="ywadjusted").tolist()
                    acf_lags = list(range(len(acf_vals)))
                    pacf_lags = list(range(len(pacf_vals)))
                    conf_interval = float(1.96 / np.sqrt(len(series)))
                else:
                    acf_vals, pacf_vals, acf_lags, pacf_lags, conf_interval = [], [], [], [], 0.0
            except Exception as e:
                acf_vals, pacf_vals, acf_lags, pacf_lags, conf_interval = [], [], [], [], 0.0

            # 5. Lag Plot
            safe_lag = min(max(1, int(lag)), len(series) - 2)
            y_t = series.values[safe_lag:].tolist()
            y_t_lag = series.values[:-safe_lag].tolist()

            # 6. Z-score Time Spikes
            # Roll standard deviation with a dynamic window
            win = min(7, len(series) // 2)
            spike_records = []
            if win > 2:
                try:
                    rolling_std = series.rolling(window=win).std()
                    mean_std = rolling_std.mean()
                    std_std = rolling_std.std()
                    if std_std > 0:
                        z_scores = (rolling_std - mean_std) / std_std
                        spikes = z_scores[z_scores.abs() > 3.0].dropna()
                        for idx in spikes.index:
                            spike_records.append({
                                "timestamp": str(idx.strftime('%Y-%m-%d %H:%M:%S') if hasattr(idx, 'strftime') else idx),
                                "value": float(series.loc[idx]),
                                "z_score": float(z_scores.loc[idx])
                            })
                except Exception:
                    pass

            # 7. Seasonality Heatmap
            try:
                weeks = series.index.isocalendar().week.astype(int)
                days = series.index.dayofweek.astype(int)
                
                heat_df = pd.DataFrame({
                    "val": series.values,
                    "week": weeks,
                    "day": days
                })
                # Pivot
                grouped_pivot = heat_df.groupby(["day", "week"])["val"].mean().unstack()
                
                # Reindex Y to ensure all 7 days are represented
                grouped_pivot = grouped_pivot.reindex(range(7))
                
                # Fill missing weeks or filter out excess
                all_weeks = sorted(list(grouped_pivot.columns))
                z_matrix = []
                for d in range(7):
                    row_vals = []
                    for w in all_weeks:
                        val = grouped_pivot.loc[d, w]
                        row_vals.append(float(val) if not pd.isna(val) else None)
                    z_matrix.append(row_vals)
                    
                heatmap_data = {
                    "x": [int(w) for w in all_weeks],
                    "y": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
                    "z": z_matrix
                }
            except Exception as e:
                heatmap_data = {"x": [], "y": [], "z": []}

            return {
                "status": "success",
                "timestamps": [str(idx.strftime('%Y-%m-%d %H:%M:%S') if hasattr(idx, 'strftime') else idx) for idx in series.index],
                "observed": series.tolist(),
                "trend": trend,
                "seasonal": seasonal,
                "residual": residual,
                "adf": {
                    "statistic": adf_stat,
                    "p_value": adf_p,
                    "critical_values": adf_crit,
                    "interpretation": adf_interpretation
                },
                "acf": {
                    "lags": acf_lags,
                    "values": acf_vals,
                    "conf_interval": conf_interval
                },
                "pacf": {
                    "lags": pacf_lags,
                    "values": pacf_vals,
                    "conf_interval": conf_interval
                },
                "lag_plot": {
                    "y_t": y_t,
                    "y_t_lag": y_t_lag,
                    "lag": safe_lag
                },
                "spikes": spike_records,
                "seasonality_heatmap": heatmap_data
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Time series analysis failed: {str(e)}"
            }