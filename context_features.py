import os
import logging
import pandas as pd
import numpy as np
import config
from data_utils import prepare_meter_series

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def _time_of_day_bucket(hour: int) -> str:
    for label, bounds in config.TIME_OF_DAY_BINS.items():
        if bounds[0] <= hour <= bounds[1]:
            return label
    return "afternoon"


def _load_level_ratio(df: pd.DataFrame) -> float:
    df = df.copy()
    df['date'] = df['timestamp'].dt.date
    daily = df.groupby('date')['kwh'].sum()

    if len(daily) < 10:
        return 1.0

    recent = daily.tail(7).mean()
    baseline = daily.iloc[:-7].tail(30).mean() if len(daily) > 14 else daily.mean()
    if baseline <= 0:
        return 1.0
    return float(recent / baseline)


def _load_feeder_type(meter_id: str) -> str:
    meta_path = os.path.join("data", "feeder_metadata.csv")
    if not os.path.exists(meta_path):
        return config.FEEDER_TYPE_DEFAULT

    meta = pd.read_csv(meta_path)
    row = meta[meta['meter_id'] == meter_id]
    if row.empty:
        return config.FEEDER_TYPE_DEFAULT

    for col in ['feeder_type', 'feeder_category', 'feeder_class']:
        if col in row.columns and pd.notna(row.iloc[0][col]):
            return str(row.iloc[0][col]).lower()

    return config.FEEDER_TYPE_DEFAULT


def build_context_features(meter_id: str) -> dict:
    df = prepare_meter_series(meter_id)
    if df is None or df.empty:
        return {
            'time_of_day': 'unknown',
            'load_level': 'normal',
            'load_ratio': 1.0,
            'feeder_type': config.FEEDER_TYPE_DEFAULT
        }

    last_ts = pd.to_datetime(df['timestamp']).max()
    time_bucket = _time_of_day_bucket(last_ts.hour)

    load_ratio = _load_level_ratio(df)
    if load_ratio < config.LOAD_LEVEL_THRESHOLDS['low']:
        load_level = 'low'
    elif load_ratio > config.LOAD_LEVEL_THRESHOLDS['high']:
        load_level = 'high'
    else:
        load_level = 'normal'

    feeder_type = _load_feeder_type(meter_id)

    return {
        'time_of_day': time_bucket,
        'load_level': load_level,
        'load_ratio': load_ratio,
        'feeder_type': feeder_type
    }
