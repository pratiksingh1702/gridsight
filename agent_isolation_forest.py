import os
import pandas as pd
import numpy as np
import logging
from sklearn.ensemble import IsolationForest
import config
from data_utils import prepare_meter_series

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def isolation_forest_score(meter_id: str) -> float:
    """
    Unsupervised Anomaly Detection using Isolation Forest.
    Trains on 96-feature daily consumption profiles.
    """
    logger.info(f"[{meter_id}] Running Isolation Forest Agent...")
    
    df = prepare_meter_series(meter_id)
    if df is None or df.empty:
        logger.warning(f"[{meter_id}] Missing data for Isolation Forest.")
        return 0.0
    
    # 1. Prepare 96-feature profiles (one per day)
    df['date'] = df['timestamp'].dt.date
    df['time_slot'] = df['timestamp'].dt.hour * 4 + df['timestamp'].dt.minute // 15
    
    # Pivot to get 96 columns
    pivot_df = df.pivot(index='date', columns='time_slot', values='kwh').dropna()
    
    if len(pivot_df) < 60:
        logger.warning(f"[{meter_id}] Insufficient data for Isolation Forest baseline.")
        return 0.0
        
    # 2. Train on baseline (first 60 days)
    train_data = pivot_df.iloc[:60].values
    model = IsolationForest(contamination=0.05, random_state=42)
    model.fit(train_data)
    
    # 3. Score recent days (last 7 days)
    recent_data = pivot_df.iloc[-7:].values
    
    # decision_function returns signed proximity to separating hyperplane. 
    # Lower values are more anomalous.
    scores = model.decision_function(recent_data)
    
    # Normalize score 0-100. 
    # Typical decision_function values range from -0.5 to 0.5.
    # Anomaly threshold is usually < 0.
    avg_decision = np.mean(scores)
    
    # Simple mapping: -0.2 -> 100, 0.0 -> 40, 0.2 -> 0
    if avg_decision < 0:
        norm_score = min(100.0, 40 + abs(avg_decision) * 300)
    else:
        norm_score = max(0.0, 40 - avg_decision * 200)
        
    return float(norm_score)

if __name__ == "__main__":
    # Smoke test
    score = isolation_forest_score("meter_000")
    logger.info(f"Isolation Forest Score for meter_000: {score}")
