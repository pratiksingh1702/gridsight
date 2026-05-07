import os
import pandas as pd
import numpy as np
import logging
import config
from data_utils import load_feeder_head_data, load_meter_data

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def feeder_gap_score(feeder_id: str) -> dict:
    """
    Feeder Balance Auditor Agent.
    Compares sum of consumer meters against feeder-head SCADA reading.
    Returns a dictionary of scores for all meters on this feeder.
    """
    logger.info(f"[{feeder_id}] Running Feeder Balance Agent...")
    
    # 1. Load feeder head data
    fdf = load_feeder_head_data(feeder_id, prefer_processed=True)
    if fdf is None or fdf.empty:
        logger.warning(f"[{feeder_id}] Feeder head data missing.")
        return {}
    fdf = fdf.copy()
    fdf['timestamp'] = pd.to_datetime(fdf['timestamp'])
    
    # Last 7 days
    recent_fdf = fdf[fdf['timestamp'] >= (fdf['timestamp'].max() - pd.Timedelta(days=7))]
    feeder_total_kwh = recent_fdf['kwh'].sum()
    
    # 2. Load all consumer data for this feeder
    metadata = pd.read_csv(os.path.join("data", "feeder_metadata.csv"))
    meter_ids = metadata[metadata['feeder_id'] == feeder_id]['meter_id'].tolist()
    
    consumer_total_kwh = 0
    meter_totals = {}
    
    for mid in meter_ids:
        mdf = load_meter_data(mid, prefer_processed=True)
        if mdf is None or mdf.empty:
            continue
        mdf = mdf.copy()
        mdf['timestamp'] = pd.to_datetime(mdf['timestamp'])
        recent_mdf = mdf[mdf['timestamp'] >= (fdf['timestamp'].max() - pd.Timedelta(days=7))]
        m_total = recent_mdf['kwh'].sum()
        consumer_total_kwh += m_total
        meter_totals[mid] = m_total
            
    # 3. Compute Gap
    # Expected: feeder_head = consumer_sum * (1 + tech_loss)
    # Gap = (feeder_head / (1 + tech_loss)) - consumer_sum
    tech_loss = config.NORMAL_TECHNICAL_LOSS_PCT / 100.0
    adjusted_feeder_total = feeder_total_kwh / (1 + tech_loss)
    
    gap_kwh = adjusted_feeder_total - consumer_total_kwh
    gap_pct = (gap_kwh / adjusted_feeder_total) * 100.0 if adjusted_feeder_total > 0 else 0
    
    logger.info(f"[{feeder_id}] Energy Gap: {gap_pct:.2f}% (Threshold: {config.FEEDER_GAP_ALERT_THRESHOLD}%)")
    
    scores = {}
    if gap_pct > config.FEEDER_GAP_ALERT_THRESHOLD:
        # Assign score to all meters on feeder, but could be weighted by their consumption drop
        # For prototype: score proportional to gap, max 100
        base_score = min(100.0, (gap_pct / config.FEEDER_GAP_ALERT_THRESHOLD) * 60.0)
        for mid in meter_ids:
            scores[mid] = base_score
    else:
        for mid in meter_ids:
            scores[mid] = 0.0
            
    return scores

if __name__ == "__main__":
    # Smoke test
    scores = feeder_gap_score("Feeder_1")
    logger.info(f"Feeder Balance Scores (first 5): {dict(list(scores.items())[:5])}")
