import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.mixture import GaussianMixture

# Try safe statsmodels import for ARIMA
try:
    from statsmodels.tsa.arima.model import ARIMA as StatsARIMA
    HAS_STATSMODELS = True
except ImportError:
    HAS_STATSMODELS = False

class ForecastClusteringModule:
    """
    Handles time series forecasting (ARIMA / Prophet-style) and Gaussian Mixture Model clustering.
    """
    def __init__(self):
        pass

    def run_time_series_forecast(
        self,
        df: pd.DataFrame,
        date_column: str,
        target_column: str,
        steps: int = 30
    ) -> Dict[str, Any]:
        """
        Fits ARIMA (AIC search) and a Prophet-style Fourier additive model, returning forecasts.
        """
        # 1. Clean and parse dates
        df_valid = df.dropna(subset=[date_column, target_column]).copy()
        if len(df_valid) < 15:
            return {"status": "error", "message": "Dataset requires at least 15 valid date-target rows for forecasting."}

        try:
            df_valid[date_column] = pd.to_datetime(df_valid[date_column])
        except Exception as e:
            return {"status": "error", "message": f"Could not parse date column: {str(e)}"}

        # Sort and aggregate values by date
        df_ts = df_valid.sort_values(date_column).groupby(date_column)[target_column].mean()
        
        # Resample to a regular daily frequency and forward fill blanks
        try:
            df_ts = df_ts.resample('D').mean().ffill()
        except Exception:
            pass
            
        N = len(df_ts)
        if N < 10:
            return {"status": "error", "message": f"Time series has only {N} steps after resampling. Need at least 10."}

        dates_str = [d.strftime('%Y-%m-%d') for d in df_ts.index]
        history_vals = [float(v) for v in df_ts.values]

        # Generate future dates
        last_date = df_ts.index[-1]
        future_dates = [last_date + pd.Timedelta(days=i) for i in range(1, steps + 1)]
        future_dates_str = [d.strftime('%Y-%m-%d') for d in future_dates]

        # --- A. ARIMA Forecast ---
        arima_forecast = []
        arima_params = "ARIMA(1,1,1)" # Default display label
        
        if HAS_STATSMODELS:
            try:
                # Small parameter grid search to optimize AIC (p=[0..2], d=[0..1], q=[0..2])
                best_aic = float('inf')
                best_order = (1, 1, 1)
                best_model = None
                
                # Check a quick grid of models
                for p in [0, 1, 2]:
                    for d in [0, 1]:
                        for q in [0, 1, 2]:
                            try:
                                model = StatsARIMA(df_ts.values, order=(p, d, q))
                                res = model.fit()
                                if res.aic < best_aic:
                                    best_aic = res.aic
                                    best_order = (p, d, q)
                                    best_model = res
                            except Exception:
                                pass
                
                if best_model is not None:
                    arima_params = f"ARIMA({best_order[0]},{best_order[1]},{best_order[2]})"
                    # Forecast
                    fc_res = best_model.get_forecast(steps=steps)
                    arima_forecast = [float(v) for v in fc_res.predicted_mean]
                else:
                    arima_forecast = self._fallback_ar_forecast(df_ts.values, steps)
            except Exception:
                arima_forecast = self._fallback_ar_forecast(df_ts.values, steps)
        else:
            arima_forecast = self._fallback_ar_forecast(df_ts.values, steps)
            arima_params = "AR(2) Autoregressive (Fallback)"

        # --- B. Prophet-Style Additive Forecast (Trend + Seasonality) ---
        prophet_forecast = []
        prophet_upper = []
        prophet_lower = []
        
        try:
            # Build time indexes
            t = np.arange(N).reshape(-1, 1)
            
            # Extract weekly & yearly seasonality features
            # Day of week (0 to 6)
            dow = df_ts.index.dayofweek.values
            # Day of year (1 to 366)
            doy = df_ts.index.dayofyear.values
            
            X_seas = np.hstack([
                t, # Trend term
                np.sin(2 * np.pi * dow / 7.0).reshape(-1, 1),
                np.cos(2 * np.pi * dow / 7.0).reshape(-1, 1),
                np.sin(2 * np.pi * doy / 365.25).reshape(-1, 1),
                np.cos(2 * np.pi * doy / 365.25).reshape(-1, 1)
            ])
            
            # Fit Ridge Regression model
            ridge = Ridge(alpha=1.0)
            ridge.fit(X_seas, df_ts.values)
            
            # Calculate standard error of residuals
            preds_train = ridge.predict(X_seas)
            residuals = df_ts.values - preds_train
            res_std = np.std(residuals)
            res_std = max(res_std, 1e-4)

            # Generate future seasonality features
            future_t = np.arange(N, N + steps).reshape(-1, 1)
            future_dow = np.array([d.dayofweek for d in future_dates])
            future_doy = np.array([d.dayofyear for d in future_dates])
            
            X_future = np.hstack([
                future_t,
                np.sin(2 * np.pi * future_dow / 7.0).reshape(-1, 1),
                np.cos(2 * np.pi * future_dow / 7.0).reshape(-1, 1),
                np.sin(2 * np.pi * future_doy / 365.25).reshape(-1, 1),
                np.cos(2 * np.pi * future_doy / 365.25).reshape(-1, 1)
            ])
            
            preds_future = ridge.predict(X_future)
            
            # Generate widening uncertainty bounds
            for idx, pred in enumerate(preds_future):
                # uncertainty increases in the future
                uncertainty = 1.96 * res_std * np.sqrt(1 + (idx + 1) / 10.0)
                prophet_forecast.append(float(pred))
                prophet_upper.append(float(pred + uncertainty))
                prophet_lower.append(float(pred - uncertainty))
                
        except Exception as e:
            # Fallback to simple trend + noise
            prophet_forecast = arima_forecast
            prophet_upper = [v * 1.15 for v in arima_forecast]
            prophet_lower = [v * 0.85 for v in arima_forecast]

        return {
            "status": "success",
            "history_dates": dates_str,
            "history_values": history_vals,
            "future_dates": future_dates_str,
            "arima_forecast": arima_forecast,
            "arima_params_label": arima_params,
            "prophet_forecast": prophet_forecast,
            "prophet_upper": prophet_upper,
            "prophet_lower": prophet_lower
        }

    def _fallback_ar_forecast(self, y: np.ndarray, steps: int) -> List[float]:
        """
        Fallback AR(2) rolling forecast using scikit-learn.
        """
        N = len(y)
        if N < 3:
            return [float(y[-1])] * steps
            
        # Fit auto-regressive model y_t = c + b1*y_{t-1} + b2*y_{t-2}
        X = np.hstack([
            y[:-2].reshape(-1, 1), # y_{t-2}
            y[1:-1].reshape(-1, 1) # y_{t-1}
        ])
        target = y[2:]
        
        lr = LinearRegression()
        lr.fit(X, target)
        
        forecast = []
        last_2 = list(y[-2:])
        
        for _ in range(steps):
            pred_feat = np.array(last_2).reshape(1, -1)
            pred = lr.predict(pred_feat)[0]
            forecast.append(float(pred))
            # Shift window
            last_2.pop(0)
            last_2.append(pred)
            
        return forecast

    def run_gmm_clustering(self, df: pd.DataFrame, num_clusters: int = 3) -> Dict[str, Any]:
        """
        Fits a Gaussian Mixture Model (GMM) on numerical fields and returns cluster profiles.
        """
        # Select numeric columns
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        # Drop columns with high null rate
        numeric_cols = [c for c in numeric_cols if df[c].isnull().sum() / len(df) < 0.4 and df[c].nunique() > 2]
        
        if len(numeric_cols) < 2:
            return {"status": "error", "message": "Clustering requires at least 2 numerical features with <40% null rate."}

        df_clust = df[numeric_cols].copy()
        # Fill missing values with median
        for c in numeric_cols:
            df_clust[c] = df_clust[c].fillna(df_clust[c].median())

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(df_clust)

        # Fit GMM
        try:
            gmm = GaussianMixture(n_components=num_clusters, random_state=42)
            gmm.fit(X_scaled)
            labels = gmm.predict(X_scaled)
            
            bic_score = float(gmm.bic(X_scaled))
            aic_score = float(gmm.aic(X_scaled))
        except Exception as e:
            return {"status": "error", "message": f"GMM Fitting failed: {str(e)}"}

        df_clust["cluster"] = labels
        counts = df_clust["cluster"].value_counts().to_dict()

        # Compute cluster centroids (means) mapped back to original scale
        profiles = []
        for i in range(num_clusters):
            c_size = int(counts.get(i, 0))
            proportion = c_size / len(df)
            
            # Average values
            subset = df_clust[df_clust["cluster"] == i]
            means = {col: float(subset[col].mean()) for col in numeric_cols}
            
            profiles.append({
                "cluster_index": i,
                "size": c_size,
                "proportion": proportion,
                "means": means
            })

        return {
            "status": "success",
            "num_clusters": num_clusters,
            "aic": aic_score,
            "bic": bic_score,
            "features": numeric_cols,
            "profiles": profiles
        }
