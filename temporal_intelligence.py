import os
import logging
import pandas as pd
import numpy as np
import config
from data_utils import load_escalation_log

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def _load_history(meter_id: str) -> pd.DataFrame:
    log_path = os.path.join("data", "escalation_log.csv")
    if not os.path.exists(log_path):
        return pd.DataFrame()

    df = load_escalation_log(log_path)
    if df.empty:
        return df

    df = df[df['meter_id'] == meter_id].copy()
    if df.empty:
        return df

    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True, errors="coerce")
    df = df.dropna(subset=['timestamp'])
    if df.empty:
        return df
    if 'p_theft' not in df.columns and 'weighted_score' in df.columns:
        df['p_theft'] = df['weighted_score'] / 100.0

    return df.sort_values('timestamp')


def compute_temporal_metrics(meter_id: str) -> dict:
    df = _load_history(meter_id)
    if df.empty:
        return {
            'persistence_days': 0,
            'trend_slope': 0.0,
            'volatility': 0.0,
            'is_persistent': False,
            'last_seen': None
        }

    lookback = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=config.TEMPORAL_LOOKBACK_DAYS)
    recent = df[df['timestamp'] >= lookback] if not df.empty else df
    if recent.empty:
        recent = df.tail(10)

    values = recent['p_theft'].astype(float).values
    if len(values) < 2:
        trend = 0.0
        volatility = 0.0
    else:
        x = np.arange(len(values))
        trend, _ = np.polyfit(x, values, 1)
        volatility = float(np.std(values))

    above_threshold = recent[recent['p_theft'] >= config.TEMPORAL_PERSISTENCE_THRESHOLD]
    persistence_days = above_threshold['timestamp'].dt.date.nunique() if not above_threshold.empty else 0

    is_persistent = persistence_days >= config.PERSISTENCE_DAYS_MEDIUM

    return {
        'persistence_days': int(persistence_days),
        'trend_slope': float(trend),
        'volatility': float(volatility),
        'is_persistent': bool(is_persistent),
        'last_seen': recent['timestamp'].max().isoformat() if not recent.empty else None
    }
