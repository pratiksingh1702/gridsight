import os
import logging
import numpy as np
import pandas as pd
from prophet import Prophet
import config
from data_utils import prepare_meter_series, smooth_kwh_signal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def _load_weather() -> pd.DataFrame | None:
    weather_path = os.path.join("data", "weather.csv")
    if not os.path.exists(weather_path):
        return None
    try:
        wdf = pd.read_csv(weather_path)
        wdf['timestamp'] = pd.to_datetime(wdf['timestamp'])
        return wdf
    except Exception:
        return None


def _baseline_forecast(history: pd.DataFrame, window: pd.DataFrame) -> pd.Series:
    history = history.copy()
    if history.empty:
        fallback = window['kwh'].median() if 'kwh' in window.columns else 0.0
        return pd.Series([fallback] * len(window), index=window.index, dtype=float)

    history['hour'] = history['timestamp'].dt.hour
    history['minute'] = history['timestamp'].dt.minute
    history['dow'] = history['timestamp'].dt.dayofweek

    baseline = history.groupby(['hour', 'minute', 'dow'])['kwh'].median()

    window = window.copy()
    window['hour'] = window['timestamp'].dt.hour
    window['minute'] = window['timestamp'].dt.minute
    window['dow'] = window['timestamp'].dt.dayofweek

    expected = window.set_index(['hour', 'minute', 'dow']).index.map(lambda key: baseline.get(key, np.nan))
    expected = pd.Series(expected, index=window.index).astype(float)
    fallback = baseline.median() if not baseline.empty else (window['kwh'].median() if 'kwh' in window.columns else 0.0)
    expected = expected.fillna(fallback)
    return expected


def _prophet_forecast(history: pd.DataFrame, window: pd.DataFrame) -> pd.Series:
    prophet_df = history[['timestamp', 'kwh']].rename(columns={'timestamp': 'ds', 'kwh': 'y'})

    model = Prophet(daily_seasonality=True, weekly_seasonality=True, yearly_seasonality=False)

    weather_df = _load_weather()
    use_weather = weather_df is not None and 'temperature_c' in weather_df.columns

    if use_weather:
        weather_df = weather_df[['timestamp', 'temperature_c']].rename(columns={'timestamp': 'ds'})
        prophet_df = prophet_df.merge(weather_df, on='ds', how='left')
        prophet_df['temperature_c'] = prophet_df['temperature_c'].ffill().bfill()
        model.add_regressor('temperature_c')

    model.fit(prophet_df)

    future = window[['timestamp']].rename(columns={'timestamp': 'ds'})
    if use_weather:
        future = future.merge(weather_df, on='ds', how='left')
        future['temperature_c'] = future['temperature_c'].ffill().bfill()

    forecast = model.predict(future)
    return forecast['yhat']


def compute_residuals(
    meter_id: str,
    lookback_days: int | None = None,
    forecast_days: int | None = None,
) -> pd.DataFrame | None:
    lookback_days = lookback_days or config.RESIDUAL_LOOKBACK_DAYS
    forecast_days = forecast_days or config.RESIDUAL_FORECAST_DAYS

    df = prepare_meter_series(meter_id)
    if df is None or df.empty:
        return None

    df = smooth_kwh_signal(df, window=5)
    if 'kwh_smoothed' in df.columns:
        df['kwh'] = df['kwh_smoothed']

    end_ts = df['timestamp'].max()
    window_start = end_ts - pd.Timedelta(days=forecast_days)
    history_start = end_ts - pd.Timedelta(days=lookback_days + forecast_days)

    history_df = df[(df['timestamp'] >= history_start) & (df['timestamp'] < window_start)]
    window_df = df[df['timestamp'] >= window_start]

    if len(history_df) < config.RESIDUAL_MIN_HISTORY_DAYS * 96:
        expected = _baseline_forecast(history_df, window_df)
    else:
        try:
            expected = _prophet_forecast(history_df, window_df)
        except Exception as exc:
            logger.warning("[%s] Prophet forecast failed (%s). Falling back to baseline.", meter_id, exc)
            expected = _baseline_forecast(history_df, window_df)

    residual = window_df['kwh'].values - expected.values

    result = pd.DataFrame({
        'timestamp': window_df['timestamp'].values,
        'actual_kwh': window_df['kwh'].values,
        'forecast_kwh': expected.values,
        'residual_kwh': residual
    })
    return result


def classify_residual_pattern(residual_df: pd.DataFrame | None) -> dict:
    if residual_df is None or residual_df.empty:
        return {
            'type': 'unknown',
            'confidence': 0.0,
            'metrics': {}
        }

    df = residual_df.copy()
    df['date'] = pd.to_datetime(df['timestamp']).dt.date
    daily = df.groupby('date').agg({
        'actual_kwh': 'sum',
        'forecast_kwh': 'sum',
        'residual_kwh': 'sum'
    }).reset_index()

    if len(daily) < 7:
        return {
            'type': 'unknown',
            'confidence': 0.0,
            'metrics': {'days': len(daily)}
        }

    recent = daily.tail(3)
    baseline = daily.iloc[:-3]

    baseline_mean = baseline['actual_kwh'].mean() if not baseline.empty else daily['actual_kwh'].mean()
    recent_mean = recent['actual_kwh'].mean()

    sudden_drop_ratio = 1.0 - (recent_mean / baseline_mean) if baseline_mean > 0 else 0.0
    if sudden_drop_ratio >= config.RESIDUAL_SUDDEN_DROP_PCT:
        return {
            'type': 'sudden_drop',
            'confidence': min(1.0, sudden_drop_ratio / config.RESIDUAL_SUDDEN_DROP_PCT),
            'metrics': {'drop_ratio': sudden_drop_ratio}
        }

    zero_days = daily[daily['actual_kwh'] <= config.RESIDUAL_ZERO_KWH_THRESHOLD]['date']
    if len(zero_days) >= 2:
        intervals = pd.Series(pd.to_datetime(zero_days)).diff().dt.days.dropna().tolist()
        if any(interval in config.RESIDUAL_PERIODIC_INTERVAL_DAYS for interval in intervals):
            return {
                'type': 'periodic_zero',
                'confidence': min(1.0, len(intervals) / 3.0),
                'metrics': {'intervals': intervals}
            }

    x = np.arange(len(daily))
    y = daily['residual_kwh'].values
    if len(x) > 2:
        slope, intercept = np.polyfit(x, y, 1)
        y_pred = slope * x + intercept
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

        if slope <= -config.RESIDUAL_DRIFT_SLOPE_KWH_PER_DAY and r2 >= config.RESIDUAL_DRIFT_R2:
            confidence = min(1.0, abs(slope) / abs(config.RESIDUAL_DRIFT_SLOPE_KWH_PER_DAY))
            return {
                'type': 'gradual_drift',
                'confidence': confidence,
                'metrics': {'slope_kwh_per_day': slope, 'r2': r2}
            }

    return {
        'type': 'normal',
        'confidence': 0.0,
        'metrics': {}
    }
