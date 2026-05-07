import os
import pandas as pd
import numpy as np
import logging
import config
from data_utils import prepare_meter_series, load_feeder_head_data

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def rule_score(meter_id: str) -> float:
    """
    Implements a rule-based engine for anomaly detection.
    Includes zero-consumption, standby minimum, tariff mismatch, and voltage anomaly rules.
    """
    logger.info(f"[{meter_id}] Running Rules Agent...")
    
    df = prepare_meter_series(meter_id)
    if df is None or df.empty:
        logger.warning(f"[{meter_id}] Missing data for Rules Agent.")
        return 0.0
    
    # Load metadata
    metadata_path = os.path.join("data", "feeder_metadata.csv")
    if not os.path.exists(metadata_path):
        logger.warning(f"[{meter_id}] Metadata missing for Rules Agent.")
        return 0.0
    metadata = pd.read_csv(metadata_path)
    if metadata[metadata['meter_id'] == meter_id].empty:
        logger.warning(f"[{meter_id}] Metadata row missing for Rules Agent.")
        return 0.0
    target_meta = metadata[metadata['meter_id'] == meter_id].iloc[0]
    
    scores = []
    
    # Rule 1: Zero-consumption ( < 0.1 kWh/day for >= 7 days )
    daily_kwh = df.groupby(df['timestamp'].dt.date)['kwh'].sum()
    consecutive_low = (daily_kwh < 0.1).astype(int).groupby((daily_kwh >= 0.1).astype(int).cumsum()).cumsum()
    if consecutive_low.max() >= 7:
        scores.append(80)
        
    # Rule 1b: Consumption collapse rule (catches bypass)
    if len(daily_kwh) >= 60:
        recent_avg = daily_kwh.iloc[-30:].mean()
        baseline_avg = daily_kwh.iloc[-60:-30].mean()
        if baseline_avg > 0.1 and recent_avg / baseline_avg < 0.50:
            scores.append(100)  # Suspicious drop
        
    # Rule 2: Standby minimum ( daily < 0.24 kWh )
    if daily_kwh.iloc[-7:].mean() < 0.24:
        scores.append(50)
        
    # Rule 3: Tariff mismatch
    # Residential peaks 6-9 AM, 6-10 PM. Commercial peaks 9 AM - 6 PM.
    if target_meta['type'] == 'commercial':
        hourly_avg = df.groupby(df['timestamp'].dt.hour)['kwh'].mean()
        peak_hours = hourly_avg.sort_values(ascending=False).head(4).index
        res_peak_hours = [6,7,8,18,19,20,21,22]
        if all(h in res_peak_hours for h in peak_hours):
            scores.append(60)
            
    # Rule 4: Voltage anomaly (Suggestion 2)
    # Meter voltage deviates > 8% from feeder average for > 5 days + consumption declining
    feeder_id = target_meta['feeder_id']
    fdf = load_feeder_head_data(feeder_id, prefer_processed=True)
    if fdf is not None and not fdf.empty:
        fdf = fdf.copy()
        fdf['timestamp'] = pd.to_datetime(fdf['timestamp'])
        
        # Align data
        df_v = df.merge(fdf[['timestamp', 'voltage']], on='timestamp', suffixes=('', '_feeder'))
        
        # Daily check
        daily_v = df_v.groupby(df_v['timestamp'].dt.date).agg({'voltage': 'mean', 'voltage_feeder': 'mean', 'kwh': 'sum'})
        v_diff_pct = abs(daily_v['voltage'] - daily_v['voltage_feeder']) / daily_v['voltage_feeder']
        days_v_anom = (v_diff_pct > 0.08).sum()
        
        # Consumption trend (last 30 days vs previous 30)
        recent_30 = daily_v['kwh'].iloc[-30:].mean()
        prev_30 = daily_v['kwh'].iloc[-60:-30].mean()
        
        if days_v_anom > 5 and recent_30 < 0.8 * prev_30:
            scores.append(65)

    return float(max(scores) if scores else 0.0)

if __name__ == "__main__":
    # Smoke test
    score = rule_score("meter_000")
    logger.info(f"Rules Score for meter_000: {score}")
