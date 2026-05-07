import numpy as np
import pandas as pd


def _normalize_timeseries(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    if 'status' not in df.columns:
        df['status'] = "NORMAL"
    return df


def select_injection_window(df: pd.DataFrame, duration: pd.Timedelta) -> tuple[pd.Timestamp, pd.Timestamp]:
    df = _normalize_timeseries(df)
    end_ts = df['timestamp'].max()
    start_ts = end_ts - duration
    return start_ts, end_ts


def apply_bypass(df: pd.DataFrame, severity: float, start_ts: pd.Timestamp, end_ts: pd.Timestamp) -> pd.DataFrame:
    df = _normalize_timeseries(df)
    mask = (df['timestamp'] >= start_ts) & (df['timestamp'] <= end_ts)
    if not mask.any():
        return df

    drop_pct = 0.2 + 0.6 * float(severity)
    df.loc[mask, 'kwh'] = df.loc[mask, 'kwh'] * (1.0 - drop_pct)

    if 'voltage' in df.columns:
        voltage_drop = 4.0 + 10.0 * float(severity)
        df.loc[mask, 'voltage'] = df.loc[mask, 'voltage'] - voltage_drop

    df.loc[mask, 'status'] = "SIM_BYPASS"
    df['kwh'] = df['kwh'].clip(lower=0.001)
    return df


def apply_tampering(
    df: pd.DataFrame,
    severity: float,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
    seed: int | None = None,
) -> pd.DataFrame:
    df = _normalize_timeseries(df)
    mask = (df['timestamp'] >= start_ts) & (df['timestamp'] <= end_ts)
    if not mask.any():
        return df

    rng = np.random.default_rng(seed)
    window_idx = df[mask].index
    window_len = len(window_idx)

    noise_scale = 0.03 + 0.12 * float(severity)
    noise = rng.normal(0.0, noise_scale, size=window_len)
    df.loc[window_idx, 'kwh'] = df.loc[window_idx, 'kwh'] * (1.0 + noise)

    period_hours = max(4, int(12 - 6 * float(severity)))
    zero_hours = max(1, int(2 + 2 * float(severity)))
    periodic_mask = mask & (df['timestamp'].dt.hour % period_hours < zero_hours)

    zero_frac = 0.03 + 0.15 * float(severity)
    zero_count = max(1, int(window_len * zero_frac))
    random_zero_idx = rng.choice(window_idx, size=zero_count, replace=False)

    df.loc[periodic_mask, 'kwh'] = 0.001
    df.loc[random_zero_idx, 'kwh'] = 0.001
    df.loc[periodic_mask | df.index.isin(random_zero_idx), 'status'] = "SIM_TAMPER"

    df['kwh'] = df['kwh'].clip(lower=0.001)
    return df


def apply_illegal_tapping_feeder(
    df: pd.DataFrame,
    severity: float,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
    seed: int | None = None,
) -> pd.DataFrame:
    df = _normalize_timeseries(df)
    mask = (df['timestamp'] >= start_ts) & (df['timestamp'] <= end_ts)
    if not mask.any():
        return df

    rng = np.random.default_rng(seed)
    add_pct = 0.05 + 0.25 * float(severity)
    jitter = rng.normal(0.0, 0.01, size=int(mask.sum()))

    df.loc[mask, 'kwh'] = df.loc[mask, 'kwh'] * (1.0 + add_pct + jitter)
    df.loc[mask, 'status'] = "SIM_TAP"
    df['kwh'] = df['kwh'].clip(lower=0.001)
    return df


def apply_missing_data(
    df: pd.DataFrame,
    missing_ratio: float,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
    seed: int | None = None,
) -> pd.DataFrame:
    df = _normalize_timeseries(df)
    if missing_ratio <= 0:
        return df

    mask = (df['timestamp'] >= start_ts) & (df['timestamp'] <= end_ts)
    window_idx = df[mask].index
    if len(window_idx) == 0:
        return df

    rng = np.random.default_rng(seed)
    missing_count = max(1, int(len(window_idx) * float(missing_ratio)))
    missing_idx = rng.choice(window_idx, size=missing_count, replace=False)
    df.loc[missing_idx, 'kwh'] = np.nan
    df.loc[missing_idx, 'status'] = "SIM_MISSING"
    return df


def apply_noise(
    df: pd.DataFrame,
    noise_level: float,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
    seed: int | None = None,
) -> pd.DataFrame:
    df = _normalize_timeseries(df)
    if noise_level <= 0:
        return df

    mask = (df['timestamp'] >= start_ts) & (df['timestamp'] <= end_ts)
    if not mask.any():
        return df

    rng = np.random.default_rng(seed)
    noise = rng.normal(0.0, float(noise_level), size=int(mask.sum()))
    df.loc[mask, 'kwh'] = df.loc[mask, 'kwh'] * (1.0 + noise)

    if 'voltage' in df.columns:
        v_noise = rng.normal(0.0, float(noise_level) * 2.0, size=int(mask.sum()))
        df.loc[mask, 'voltage'] = df.loc[mask, 'voltage'] + v_noise

    df.loc[mask, 'status'] = df.loc[mask, 'status'].fillna("NORMAL")
    df['kwh'] = df['kwh'].clip(lower=0.001)
    return df


def align_feeder_head_with_meters(
    feeder_df: pd.DataFrame,
    original_meters: dict[str, pd.DataFrame],
    modified_meters: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    feeder_df = _normalize_timeseries(feeder_df)
    if feeder_df.empty:
        return feeder_df

    feeder_df = feeder_df.set_index('timestamp')
    delta_series = pd.Series(0.0, index=feeder_df.index)

    for meter_id, original_df in original_meters.items():
        modified_df = modified_meters.get(meter_id)
        if modified_df is None:
            continue

        original_df = _normalize_timeseries(original_df).set_index('timestamp')
        modified_df = _normalize_timeseries(modified_df).set_index('timestamp')

        common = original_df[['kwh']].join(modified_df[['kwh']], how='inner', lsuffix='_before', rsuffix='_after')
        if common.empty:
            continue

        delta = common['kwh_before'] - common['kwh_after']
        delta_series = delta_series.add(delta, fill_value=0.0)

    feeder_df['kwh'] = feeder_df['kwh'] - delta_series.reindex(feeder_df.index).fillna(0.0)
    feeder_df['kwh'] = feeder_df['kwh'].clip(lower=0.001)
    feeder_df['status'] = feeder_df.get('status', pd.Series(index=feeder_df.index, dtype=object)).fillna("NORMAL")
    feeder_df['status'] = feeder_df['status'].astype(str)
    feeder_df.loc[delta_series.reindex(feeder_df.index).fillna(0.0) != 0.0, 'status'] = "SIM_ALIGN"

    return feeder_df.reset_index()
