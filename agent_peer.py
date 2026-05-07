import os
import pandas as pd
import numpy as np
import logging
from sklearn.neighbors import NearestNeighbors
import config
from data_utils import load_meter_data

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def peer_score(meter_id: str) -> float:
    """
    KNN Peer Comparator Agent.
    Finds 20 'social twins' and compares target meter's recent consumption to theirs.
    """
    logger.info(f"[{meter_id}] Running Peer Agent...")
    
    # 1. Load metadata to find peers
    metadata = pd.read_csv(os.path.join("data", "feeder_metadata.csv"))
    target_meta = metadata[metadata['meter_id'] == meter_id].iloc[0]
    
    # Peers: same type and same feeder
    peers_meta = metadata[(metadata['type'] == target_meta['type']) & 
                           (metadata['feeder_id'] == target_meta['feeder_id'])]
    
    if len(peers_meta) < 5:
        logger.warning(f"[{meter_id}] Too few peers ({len(peers_meta)}) for comparison.")
        return 0.0
        
    # 2. Build profile for KNN (average hourly load over first 60 days)
    # This is a simplification: 24 features (one per hour)
    profiles = []
    meter_ids = peers_meta['meter_id'].tolist()
    
    valid_meter_ids = []
    for mid in meter_ids:
        df = load_meter_data(mid, prefer_processed=True)
        if df is None or df.empty:
            continue
        df = df.copy()
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Baseline: first 60 days
        baseline_mask = df['timestamp'] < (df['timestamp'].min() + pd.Timedelta(days=60))
        baseline_df = df[baseline_mask]
        
        if len(baseline_df) < 24 * 4 * 30: continue # Need at least 30 days
        
        hourly_profile = baseline_df.groupby(baseline_df['timestamp'].dt.hour)['kwh'].mean().values
        if len(hourly_profile) == 24:
            profiles.append(hourly_profile)
            valid_meter_ids.append(mid)
            
    if len(profiles) < 5:
        return 0.0
        
    X = np.array(profiles)
    if meter_id not in valid_meter_ids:
        logger.warning(f"[{meter_id}] Target meter missing baseline profile for peer comparison.")
        return 0.0
    target_idx = valid_meter_ids.index(meter_id)
    
    # 3. Find 20 social twins
    k = min(20, len(X)-1)
    knn = NearestNeighbors(n_neighbors=k+1)
    knn.fit(X)
    distances, indices = knn.kneighbors(X[target_idx].reshape(1, -1))
    
    # indices[0][0] is the target itself
    peer_indices = indices[0][1:]
    peer_ids = [valid_meter_ids[idx] for idx in peer_indices]
    
    # 4. Compare recent performance (last 30 days)
    peer_averages = []
    for pid in peer_ids:
        pdf = load_meter_data(pid, prefer_processed=True)
        if pdf is None or pdf.empty:
            continue
        pdf = pdf.copy()
        pdf['timestamp'] = pd.to_datetime(pdf['timestamp'])
        recent_mask = pdf['timestamp'] >= (pdf['timestamp'].max() - pd.Timedelta(days=30))
        peer_averages.append(pdf[recent_mask]['kwh'].mean())

    target_df = load_meter_data(meter_id, prefer_processed=True)
    if target_df is None or target_df.empty:
        return 0.0
    target_df = target_df.copy()
    target_df['timestamp'] = pd.to_datetime(target_df['timestamp'])
    target_recent_mask = target_df['timestamp'] >= (target_df['timestamp'].max() - pd.Timedelta(days=30))
    target_avg = target_df[target_recent_mask]['kwh'].mean()
    
    if not peer_averages:
        return 0.0

    peer_mean = np.mean(peer_averages)
    peer_std = np.std(peer_averages)
    
    if peer_std == 0: peer_std = 0.001
    
    # Z-score (looking for downward deviation)
    z = (peer_mean - target_avg) / peer_std
    
    # Score 0-100: starts firing at z=3
    if z > 3:
        score = min(100.0, 50.0 + (z - 3) * 10)
    else:
        score = max(0.0, z * 10) # Low score
        
    return float(score)

if __name__ == "__main__":
    # Smoke test
    score = peer_score("meter_000")
    logger.info(f"Peer Score for meter_000: {score}")
