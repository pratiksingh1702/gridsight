import os
import logging
import numpy as np
import pandas as pd
import config
from data_utils import load_feeder_head_data, load_meter_data, ensure_regular_frequency, impute_small_gaps

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def _estimate_line_loss_pct(avg_kw: float, feeder_id: str) -> float:
    capacity_kw = config.FEEDER_CAPACITY_KW.get(feeder_id, config.FEEDER_CAPACITY_KW_DEFAULT)
    if capacity_kw <= 0:
        capacity_kw = config.FEEDER_CAPACITY_KW_DEFAULT

    load_ratio = min(1.5, avg_kw / capacity_kw)
    loss_pct = config.LINE_LOSS_BASE_PCT + config.LINE_LOSS_LOAD_COEFF * (load_ratio ** 2)
    return float(loss_pct)


def _load_meter_kwh(meter_id: str, start_ts: pd.Timestamp, end_ts: pd.Timestamp) -> float:
    df = load_meter_data(meter_id, prefer_processed=True)
    if df is None:
        return 0.0
    df = ensure_regular_frequency(df, config.EXPECTED_FREQ)
    df = impute_small_gaps(df, config.EXPECTED_FREQ)
    mask = (df['timestamp'] >= start_ts) & (df['timestamp'] <= end_ts)
    return float(df.loc[mask, 'kwh'].sum()) if mask.any() else 0.0


def _phase_imbalance_score(feeder_id: str, start_ts: pd.Timestamp, end_ts: pd.Timestamp) -> dict:
    metadata_path = os.path.join("data", "feeder_metadata.csv")
    if not os.path.exists(metadata_path):
        return {'is_imbalanced': False, 'voltage_std': 0.0, 'score': 0.0}

    metadata = pd.read_csv(metadata_path)
    meter_ids = metadata[metadata['feeder_id'] == feeder_id]['meter_id'].tolist()

    voltages = []
    for mid in meter_ids:
        df = load_meter_data(mid, prefer_processed=True)
        if df is None or 'voltage' not in df.columns:
            continue
        df = ensure_regular_frequency(df, config.EXPECTED_FREQ)
        df = impute_small_gaps(df, config.EXPECTED_FREQ)
        mask = (df['timestamp'] >= start_ts) & (df['timestamp'] <= end_ts)
        if mask.any():
            voltages.append(df.loc[mask, 'voltage'].mean())

    if len(voltages) < 3:
        return {'is_imbalanced': False, 'voltage_std': 0.0, 'score': 0.0}

    voltage_std = float(np.std(voltages))
    is_imbalanced = voltage_std >= config.PHASE_IMBALANCE_VOLT_STD
    score = min(100.0, (voltage_std / config.PHASE_IMBALANCE_VOLT_STD) * 100.0) if config.PHASE_IMBALANCE_VOLT_STD > 0 else 0.0

    return {
        'is_imbalanced': is_imbalanced,
        'voltage_std': voltage_std,
        'score': score
    }


def _topology_context(feeder_id: str) -> dict:
    metadata_path = os.path.join("data", "feeder_metadata.csv")
    if not os.path.exists(metadata_path):
        return {'grouping': 'feeder', 'group_id': feeder_id}

    metadata = pd.read_csv(metadata_path)
    for col in config.TOPOLOGY_COLUMNS:
        if col in metadata.columns:
            group_id = metadata[metadata['feeder_id'] == feeder_id][col].dropna().unique().tolist()
            return {'grouping': col, 'group_id': group_id, 'feeder_id': feeder_id}

    return {'grouping': 'feeder', 'group_id': feeder_id}


def evaluate_feeder_physics(feeder_id: str, lookback_days: int | None = None) -> dict:
    lookback_days = lookback_days or config.PHYSICS_LOOKBACK_DAYS
    fdf = load_feeder_head_data(feeder_id, prefer_processed=True)
    if fdf is None or fdf.empty:
        return {
            'energy_balance': {'p_in_kwh': 0.0, 'p_consumption_kwh': 0.0, 'p_loss_kwh': 0.0, 'p_unknown_kwh': 0.0, 'gap_pct': 0.0},
            'line_loss_pct': 0.0,
            'phase_imbalance': {'is_imbalanced': False, 'voltage_std': 0.0, 'score': 0.0},
            'topology': _topology_context(feeder_id),
            'physics_confidence': 0.0
        }

    end_ts = fdf['timestamp'].max()
    start_ts = end_ts - pd.Timedelta(days=lookback_days)
    f_recent = fdf[(fdf['timestamp'] >= start_ts) & (fdf['timestamp'] <= end_ts)]

    p_in_kwh = float(f_recent['kwh'].sum())

    metadata_path = os.path.join("data", "feeder_metadata.csv")
    if not os.path.exists(metadata_path):
        meter_ids = []
    else:
        metadata = pd.read_csv(metadata_path)
        meter_ids = metadata[metadata['feeder_id'] == feeder_id]['meter_id'].tolist()

    p_consumption_kwh = sum(_load_meter_kwh(mid, start_ts, end_ts) for mid in meter_ids)

    hours = max(1.0, lookback_days * 24.0)
    avg_kw = p_in_kwh / hours
    line_loss_pct = _estimate_line_loss_pct(avg_kw, feeder_id)
    p_loss_kwh = p_in_kwh * (line_loss_pct / 100.0)

    p_unknown_kwh = p_in_kwh - (p_consumption_kwh + p_loss_kwh)
    gap_pct = (p_unknown_kwh / p_in_kwh) * 100.0 if p_in_kwh > 0 else 0.0

    phase = _phase_imbalance_score(feeder_id, start_ts, end_ts)

    actual_loss_pct = ((p_in_kwh - p_consumption_kwh) / p_in_kwh) * 100.0 if p_in_kwh > 0 else 0.0
    loss_dev_pct = max(0.0, actual_loss_pct - line_loss_pct)

    gap_score = min(1.0, gap_pct / max(0.1, config.FEEDER_GAP_ALERT_THRESHOLD))
    gap_score = min(1.0, gap_score * config.PHYSICS_CONFIDENCE_GAP_SCALE / 2.0)
    loss_score = min(1.0, loss_dev_pct / max(0.1, line_loss_pct))
    loss_score = min(1.0, loss_score * config.PHYSICS_CONFIDENCE_LOSS_DEV_SCALE / 2.0)

    physics_confidence = 0.4 + 0.3 * gap_score + 0.3 * loss_score
    physics_confidence = float(min(1.0, max(0.0, physics_confidence)))

    return {
        'energy_balance': {
            'p_in_kwh': p_in_kwh,
            'p_consumption_kwh': p_consumption_kwh,
            'p_loss_kwh': p_loss_kwh,
            'p_unknown_kwh': p_unknown_kwh,
            'gap_pct': gap_pct
        },
        'line_loss_pct': line_loss_pct,
        'phase_imbalance': phase,
        'topology': _topology_context(feeder_id),
        'physics_confidence': physics_confidence
    }
