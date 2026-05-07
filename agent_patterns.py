import os
import pandas as pd
import numpy as np
import logging
import config
from data_utils import prepare_meter_series

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def pattern_score(meter_id: str) -> float:
    """
    Scans for specific consumption signatures like flatlines, night-zero patterns, and periodic dips.
    """
    logger.info(f"[{meter_id}] Running Patterns Agent...")
    
    df = prepare_meter_series(meter_id)
    if df is None or df.empty:
        logger.warning(f"[{meter_id}] Missing data for Patterns Agent.")
        return 0.0
    
    scores = []
    
    # 1. Perfectly flat line (Variance of daily kWh < 0.001)
    daily_kwh = df.groupby(df['timestamp'].dt.date)['kwh'].sum()
    if daily_kwh.iloc[-30:].var() < 0.001:
        scores.append(90)
        
    # 2. Night-zero / Day-normal
    # Night: 22:00 - 06:00, Day: 06:00 - 22:00
    df['is_night'] = (df['timestamp'].dt.hour >= 22) | (df['timestamp'].dt.hour < 6)
    night_avg = df[df['is_night']]['kwh'].mean()
    day_avg = df[~df['is_night']]['kwh'].mean()
    
    if day_avg > 0.1 and night_avg < 0.05 * day_avg:
        scores.append(70)
        
    # 3. Periodic dips (dips > 60% every 15, 30, or 60 days)
    # Simplified check for 15-day periodicity
    diff_pct = daily_kwh.pct_change()
    dips = (diff_pct < -0.60)
    if dips.sum() >= 2:
        # Check intervals between dips
        dip_dates = daily_kwh.index[dips]
        intervals = pd.Series(dip_dates).diff().dt.days
        if any(i in [14, 15, 16, 29, 30, 31] for i in intervals):
            scores.append(60)
            
    # 4. Sudden drop aligned with service date (Placeholder metadata)
    # Assuming metadata has a 'last_service_date' column for some meters
    # For prototype, we'll check for a sudden > 50% drop in last 90 days.
    # 4. Sudden sustained drop (bypass signature)
    if len(daily_kwh) >= 60:
        recent_30 = daily_kwh.iloc[-30:]
        baseline_30 = daily_kwh.iloc[-60:-30]
        if len(baseline_30) > 0 and baseline_30.mean() > 0.1:
            drop_ratio = recent_30.mean() / baseline_30.mean()
            if drop_ratio < 0.50:  # 50% drop
                scores.append(100)  # high confidence bypass pattern

    return float(max(scores) if scores else 0.0)

if __name__ == "__main__":
    # Smoke test
    score = pattern_score("meter_000")
    logger.info(f"Patterns Score for meter_000: {score}")
