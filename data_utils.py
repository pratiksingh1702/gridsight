import os
import csv
import logging
import pandas as pd
import numpy as np
import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

_SIMULATION_METER_OVERRIDES: dict[str, pd.DataFrame] = {}
_SIMULATION_FEEDER_OVERRIDES: dict[str, pd.DataFrame] = {}

ESCALATION_LOG_COLUMNS_V1 = [
    "meter_id",
    "timestamp",
    "decision",
    "weighted_score",
    "agents_firing",
    "agent_scores",
    "evidence"
]

ESCALATION_LOG_COLUMNS_V2 = [
    "meter_id",
    "feeder_id",
    "timestamp",
    "decision",
    "weighted_score",
    "p_theft",
    "agents_firing",
    "agent_scores",
    "agent_probabilities",
    "residual_pattern",
    "physics",
    "physics_confidence",
    "context_features",
    "temporal_metrics",
    "data_quality",
    "hierarchical_classification",
    "theft_class",
    "p_theft_ci_low",
    "p_theft_ci_high",
    "uncertainty",
    "economic",
    "decision_details",
    "explainability",
    "evidence"
]

ESCALATION_NUMERIC_COLUMNS = [
    "weighted_score",
    "p_theft",
    "agents_firing",
    "physics_confidence",
    "p_theft_ci_low",
    "p_theft_ci_high",
    "uncertainty"
]


def _is_escalation_header(row: list[str]) -> bool:
    return row == ESCALATION_LOG_COLUMNS_V1 or row == ESCALATION_LOG_COLUMNS_V2


def _normalize_escalation_row(row: list[str]) -> dict:
    if len(row) == len(ESCALATION_LOG_COLUMNS_V2):
        columns = ESCALATION_LOG_COLUMNS_V2
    elif len(row) == len(ESCALATION_LOG_COLUMNS_V1):
        columns = ESCALATION_LOG_COLUMNS_V1
    elif len(row) > len(ESCALATION_LOG_COLUMNS_V1):
        columns = ESCALATION_LOG_COLUMNS_V2
        if len(row) < len(columns):
            row = row + [""] * (len(columns) - len(row))
        else:
            row = row[:len(columns)]
    else:
        columns = ESCALATION_LOG_COLUMNS_V1
        row = row + [""] * (len(columns) - len(row))

    return dict(zip(columns, row))


def load_escalation_log(path: str | None = None) -> pd.DataFrame:
    path = path or os.path.join("data", "escalation_log.csv")
    if not os.path.exists(path):
        return pd.DataFrame(columns=ESCALATION_LOG_COLUMNS_V2)

    rows: list[dict] = []
    try:
        with open(path, newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            first_row = next(reader, None)
            if first_row is None:
                return pd.DataFrame(columns=ESCALATION_LOG_COLUMNS_V2)

            if not _is_escalation_header(first_row):
                rows.append(_normalize_escalation_row(first_row))

            for row in reader:
                if not row or all(cell == "" for cell in row):
                    continue
                if _is_escalation_header(row):
                    continue
                rows.append(_normalize_escalation_row(row))
    except Exception as exc:
        logger.warning("[escalation_log] Failed reading %s: %s", path, exc)
        return pd.DataFrame(columns=ESCALATION_LOG_COLUMNS_V2)

    df = pd.DataFrame(rows)
    for col in ESCALATION_LOG_COLUMNS_V2:
        if col not in df.columns:
            df[col] = pd.NA

    for col in ESCALATION_NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def _read_csv_if_exists(path: str, label: str) -> pd.DataFrame | None:
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_csv(path)
        if 'timestamp' not in df.columns:
            logger.warning("[%s] Missing timestamp column in %s", label, path)
            return None
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    except Exception as exc:
        logger.warning("[%s] Failed reading %s: %s", label, path, exc)
        return None


def set_simulation_overrides(
    meter_overrides: dict[str, pd.DataFrame] | None = None,
    feeder_overrides: dict[str, pd.DataFrame] | None = None,
) -> None:
    global _SIMULATION_METER_OVERRIDES, _SIMULATION_FEEDER_OVERRIDES
    _SIMULATION_METER_OVERRIDES = meter_overrides or {}
    _SIMULATION_FEEDER_OVERRIDES = feeder_overrides or {}


def clear_simulation_overrides() -> None:
    _SIMULATION_METER_OVERRIDES.clear()
    _SIMULATION_FEEDER_OVERRIDES.clear()


def _normalize_timeseries(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df


def _get_meter_override(meter_id: str) -> pd.DataFrame | None:
    override = _SIMULATION_METER_OVERRIDES.get(meter_id)
    if override is None:
        return None
    return _normalize_timeseries(override)


def _get_feeder_override(feeder_id: str) -> pd.DataFrame | None:
    override = _SIMULATION_FEEDER_OVERRIDES.get(feeder_id)
    if override is None:
        return None
    return _normalize_timeseries(override)


def load_meter_data(meter_id: str, prefer_processed: bool = True) -> pd.DataFrame | None:
    override = _get_meter_override(meter_id)
    if override is not None:
        return override

    candidates = []
    if prefer_processed:
        candidates.append(os.path.join("data", "processed", "meter_readings", f"{meter_id}.csv"))
    candidates.append(os.path.join("data", "meter_readings", f"{meter_id}.csv"))

    for path in candidates:
        df = _read_csv_if_exists(path, meter_id)
        if df is not None:
            return df

    logger.warning("[%s] No meter data found.", meter_id)
    return None


def load_feeder_head_data(feeder_id: str, prefer_processed: bool = True) -> pd.DataFrame | None:
    override = _get_feeder_override(feeder_id)
    if override is not None:
        return override

    candidates = []
    if prefer_processed:
        candidates.append(os.path.join("data", "processed", "feeder_head_readings", f"{feeder_id}_head.csv"))
    candidates.append(os.path.join("data", "feeder_head_readings", f"{feeder_id}_head.csv"))

    for path in candidates:
        df = _read_csv_if_exists(path, feeder_id)
        if df is not None:
            return df

    logger.warning("[%s] No feeder head data found.", feeder_id)
    return None


def ensure_regular_frequency(df: pd.DataFrame, expected_freq: str | None = None) -> pd.DataFrame:
    expected_freq = expected_freq or config.EXPECTED_FREQ
    df = df.sort_values('timestamp')

    if len(df) < 2:
        return df

    median_delta = df['timestamp'].diff().median()
    expected_delta = pd.Timedelta(expected_freq)

    if pd.isna(median_delta) or median_delta <= expected_delta * 1.2:
        return df

    logger.info("Resampling to %s due to low-frequency readings (%s)", expected_freq, median_delta)

    resampled = df.set_index('timestamp').resample(expected_freq).mean()
    if 'kwh' in resampled.columns:
        resampled['kwh'] = resampled['kwh'].interpolate('time')
    if 'voltage' in resampled.columns:
        resampled['voltage'] = resampled['voltage'].interpolate('time')

    resampled['status'] = resampled.get('status', pd.Series(index=resampled.index, dtype=object))
    resampled['status'] = resampled['status'].fillna('RESAMPLED')
    return resampled.reset_index()


def impute_small_gaps(df: pd.DataFrame, expected_freq: str | None = None) -> pd.DataFrame:
    expected_freq = expected_freq or config.EXPECTED_FREQ
    df = df.sort_values('timestamp')
    df = df.set_index('timestamp').asfreq(expected_freq)

    if 'kwh' not in df.columns:
        return df.reset_index()

    missing_mask = df['kwh'].isna()
    if not missing_mask.any():
        return df.reset_index()

    df['hour'] = df.index.hour
    df['minute'] = df.index.minute
    df['dow'] = df.index.dayofweek

    median_kwh = df.groupby(['hour', 'minute', 'dow'])['kwh'].transform('median')
    df['kwh'] = df['kwh'].fillna(median_kwh)
    df['kwh'] = df['kwh'].ffill().bfill()

    if 'voltage' in df.columns:
        df['voltage'] = df['voltage'].ffill().bfill()

    df['status'] = df.get('status', pd.Series(index=df.index, dtype=object))
    df['status'] = df['status'].fillna('IMPUTED')

    return df.reset_index().rename(columns={'index': 'timestamp'})


def smooth_kwh_signal(df: pd.DataFrame, window: int = 5) -> pd.DataFrame:
    if 'kwh' not in df.columns or df.empty:
        return df
    df = df.copy()
    df['kwh_smoothed'] = df['kwh'].rolling(window=window, min_periods=1, center=True).median()
    return df


def compute_data_quality(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {'missing_ratio': 1.0, 'imputed_ratio': 0.0, 'resampled_ratio': 0.0}

    total = len(df)
    status = df.get('status', pd.Series(index=df.index, dtype=object))
    imputed_ratio = float((status == 'IMPUTED').sum()) / total if total > 0 else 0.0
    resampled_ratio = float((status == 'RESAMPLED').sum()) / total if total > 0 else 0.0
    missing_ratio = float(df['kwh'].isna().sum()) / total if 'kwh' in df.columns and total > 0 else 0.0

    return {
        'missing_ratio': missing_ratio,
        'imputed_ratio': imputed_ratio,
        'resampled_ratio': resampled_ratio
    }


def prepare_meter_series(meter_id: str) -> pd.DataFrame | None:
    df = load_meter_data(meter_id, prefer_processed=True)
    if df is None:
        return None
    df = ensure_regular_frequency(df, config.EXPECTED_FREQ)
    df = impute_small_gaps(df, config.EXPECTED_FREQ)
    return df
