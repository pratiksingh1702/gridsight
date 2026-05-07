import os
import sys

# Add project root to sys.path to import project-level config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
import config as project_config

class AppConfig:
    PROJECT_NAME: str = "GridSight AI Backend"
    API_V1_STR: str = "/api/v1"
    
    # Use parameters from project config
    AGENT_FIRE_THRESHOLD = project_config.AGENT_FIRE_THRESHOLD
    FUSION_PROB_THRESHOLD = project_config.FUSION_PROB_THRESHOLD
    
    # Backend specific
    WS_HEARTBEAT_INTERVAL = 30
    WS_BROADCAST_INTERVAL = 5.0  # seconds

settings = AppConfig()
