import os
import pandas as pd
import numpy as np
import logging
from datetime import datetime
import config
from data_utils import prepare_meter_series

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def cusum_score(meter_id: str, days_lookback: int = 90) -> dict:
    """
    Computes a CUSUM-based score to detect sustained downward breaks in consumption.
    
    Args:
        meter_id: Meter identifier.
        days_lookback: History to load.
        
    Returns:
        dict: {'score': float (0-100), 'detection_date': str or None}
    """
    logger.info(f"[{meter_id}] Running CUSUM Agent...")
    
    df = prepare_meter_series(meter_id)
    if df is None or df.empty:
        logger.warning(f"[{meter_id}] Data file not found for CUSUM.")
        return {"score": 0.0, "detection_date": None}
    df = df.sort_values('timestamp')
    
    # We need daily totals for CUSUM break detection
    daily_df = df.groupby(df['timestamp'].dt.date)['kwh'].sum().reset_index()
    daily_df.columns = ['date', 'kwh']
    
    if len(daily_df) < 60:
        logger.warning(f"[{meter_id}] Insufficient data for CUSUM (need 60 days baseline).")
        return {"score": 0.0, "detection_date": None}
        
    # Baseline: first 60 days
    baseline_mean = daily_df.iloc[:60]['kwh'].mean()
    baseline_std = daily_df.iloc[:60]['kwh'].std()
    
    if baseline_std == 0: baseline_std = 0.001
    
    # Test period: from day 61 onwards
    test_df = daily_df.iloc[60:].copy()
    
    # CUSUM parameters (standard)
    k = 0.5 # Reference value (slack)
    h = 5.0 # Threshold (multiples of std)
    
    # Cumulative Sum of deviations
    # We are looking for a DOWNWARD shift, so we look at (mean - k*std - val)
    s_low = 0
    s_low_list = []
    detection_date = None
    
    for i, row in test_df.iterrows():
        # Standardized deviation
        z = (row['kwh'] - baseline_mean) / baseline_std
        # Cumulative sum for downward shift
        s_low = max(0, s_low - (z + k))
        s_low_list.append(s_low)
        
        if s_low > h and detection_date is None:
            detection_date = row['date']
            
    # Normalize score 0-100 based on h
    max_cusum = max(s_low_list) if s_low_list else 0
    score = min(100.0, (max_cusum / h) * 50.0) if max_cusum > 0 else 0.0
    
    # If detection_date is found, boost score
    if detection_date:
        score = max(score, config.AGENT_FIRE_THRESHOLD + 10)
        
    return {
        "score": float(score),
        "detection_date": str(detection_date) if detection_date else None
    }

if __name__ == "__main__":
    # Smoke test on a known theft meter
    # We know meter_001 might be theft (randomly assigned in generate_data)
    # Let's try meter_000
    res = cusum_score("meter_000")
    logger.info(f"CUSUM Result for meter_000: {res}")
