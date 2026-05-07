import os
import pandas as pd
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data"))

def load_feeder_metadata() -> pd.DataFrame:
    path = os.path.join(DATA_DIR, "feeder_metadata.csv")
    if os.path.exists(path):
        return pd.read_csv(path)
    return pd.DataFrame()

def load_escalation_log() -> pd.DataFrame:
    path = os.path.join(DATA_DIR, "escalation_log.csv")
    if os.path.exists(path):
        return pd.read_csv(path)
    return pd.DataFrame()

def get_meters_list() -> List[str]:
    df = load_feeder_metadata()
    if not df.empty and 'meter_id' in df.columns:
        return df['meter_id'].unique().tolist()
    return [f"MTR-{i:04d}" for i in range(10000, 10050)] # Fallback

def get_zones_from_metadata() -> List[str]:
    df = load_feeder_metadata()
    if not df.empty and 'feeder_id' in df.columns:
        return df['feeder_id'].unique().tolist()
    return ["Whitefield", "Koramangala", "HSR Layout", "Indiranagar", "Marathahalli", "Rajajinagar", "Jayanagar"]
