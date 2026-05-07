# config.py
# All tunable parameters for GridSight.
# BESCOM analysts adjust these without touching model code.

import os

# System Mode
USE_DB = False

# Legacy Consensus Thresholds (kept for compatibility and reporting)
AGENT_FIRE_THRESHOLD = 50
MIN_AGENTS_FIRING = 3
ESCALATION_SCORE_THRESHOLD = 75
PERSISTENCE_DAYS = 7

# Agent Weights (Total = 10.0 for easier math)
AGENT_WEIGHTS = {
    "cusum": 3.0,
    "peer": 1.0,
    "rules": 3.0,
    "patterns": 3.0,
    "feeder_balance": 1.0,
    "isolation_forest": 0.0
}

# Probabilistic Fusion
FUSION_PROB_THRESHOLD = 0.70
FUSION_FORCE_INSPECTION_ROI = 2.0
FUSION_MIN_PROB_FOR_ROI = 0.50

# Context-Aware Fusion
TIME_OF_DAY_BINS = {
    "night": [0, 5],
    "morning": [6, 11],
    "afternoon": [12, 17],
    "evening": [18, 23]
}
LOAD_LEVEL_THRESHOLDS = {
    "low": 0.7,
    "high": 1.3
}
FEEDER_TYPE_DEFAULT = "mixed"

AGENT_CONTEXT_FACTORS = {
    "default": {"night": 1.0, "morning": 1.0, "afternoon": 1.0, "evening": 1.0},
    "cusum": {"night": 0.95, "morning": 1.0, "afternoon": 1.05, "evening": 1.05},
    "peer": {"night": 1.0, "morning": 1.05, "afternoon": 1.05, "evening": 1.0},
    "rules": {"night": 1.05, "morning": 1.0, "afternoon": 0.95, "evening": 1.0},
    "patterns": {"night": 1.05, "morning": 1.0, "afternoon": 1.0, "evening": 1.0},
    "feeder_balance": {"night": 0.95, "morning": 1.0, "afternoon": 1.05, "evening": 1.05},
    "isolation_forest": {"night": 1.0, "morning": 1.0, "afternoon": 1.0, "evening": 1.0}
}

FEEDER_TYPE_FACTORS = {
    "urban": 1.05,
    "rural": 0.95,
    "industrial": 1.1,
    "mixed": 1.0
}

AGENT_PROB_CALIBRATION = {
    "default": {"alpha": 0.10, "beta": 50},
    "cusum": {"alpha": 0.10, "beta": 45},
    "peer": {"alpha": 0.08, "beta": 50},
    "rules": {"alpha": 0.11, "beta": 50},
    "patterns": {"alpha": 0.12, "beta": 50},
    "feeder_balance": {"alpha": 0.09, "beta": 45},
    "isolation_forest": {"alpha": 0.08, "beta": 50}
}

FUSION_LOGIT_COEFS = {
    "bias": -2.0,
    "cusum": 0.9,
    "peer": 0.7,
    "rules": 0.9,
    "patterns": 1.0,
    "feeder_balance": 0.6,
    "isolation_forest": 0.5,
    "residual_sudden_drop": 1.2,
    "residual_periodic_zero": 0.8,
    "residual_gradual_drift": 0.9,
    "physics_gap": 0.8,
    "phase_imbalance": 0.6,
    "firing_ratio": 0.7,
    "context_night": 0.1,
    "context_morning": 0.05,
    "context_afternoon": 0.05,
    "context_evening": 0.1,
    "context_load_low": -0.2,
    "context_load_high": 0.2,
    "context_feeder_industrial": 0.2,
    "context_feeder_rural": -0.1,
    "temporal_persistence": 0.4,
    "temporal_trend": 0.2
}

# Residual Intelligence Layer
RESIDUAL_LOOKBACK_DAYS = 30
RESIDUAL_FORECAST_DAYS = 14
RESIDUAL_MIN_HISTORY_DAYS = 45
RESIDUAL_SUDDEN_DROP_PCT = 0.40
RESIDUAL_ZERO_KWH_THRESHOLD = 0.1
RESIDUAL_PERIODIC_INTERVAL_DAYS = [7, 14, 15, 30]
RESIDUAL_DRIFT_SLOPE_KWH_PER_DAY = 0.25
RESIDUAL_DRIFT_R2 = 0.5

# Physics Engine
FEEDER_GAP_ALERT_THRESHOLD = 1.0  # % gap to flag feeder
NORMAL_TECHNICAL_LOSS_PCT = 3.0
LINE_LOSS_BASE_PCT = 2.0
LINE_LOSS_LOAD_COEFF = 4.0
PHYSICS_LOOKBACK_DAYS = 7
PHASE_IMBALANCE_VOLT_STD = 4.0
FEEDER_CAPACITY_KW_DEFAULT = 1000.0
FEEDER_CAPACITY_KW = {}
TOPOLOGY_COLUMNS = ["transformer_id", "dt_id", "section_id"]
PHYSICS_CONFIDENCE_GAP_SCALE = 2.5
PHYSICS_CONFIDENCE_LOSS_DEV_SCALE = 1.5
PHYSICS_CONFIDENCE_IMPACT = 0.6

# Economic Impact
TARIFF_RESIDENTIAL_PER_KWH = 7.0
TARIFF_COMMERCIAL_PER_KWH = 10.0
INSPECTION_COST = 1500.0
RECOVERY_RATE = 0.6
LOSS_PROJECTION_DAYS = 30
LOSS_SCALE_FOR_PRIORITY = 5000.0
ROI_TARGET = 1.5
MIN_EXPECTED_VALUE_FOR_ESCALATION = 2000.0

# Decision Engine
URGENCY_THRESHOLDS = {
    "critical": 0.85,
    "high": 0.70,
    "medium": 0.55
}
PERSISTENCE_DAYS_HIGH = 5
PERSISTENCE_DAYS_MEDIUM = 3

# Demand Forecasting Risk Zones
RISK_ZONE_YELLOW = 0.70
RISK_ZONE_ORANGE = 0.85
RISK_ZONE_RED = 0.95

# Data Pipeline
EXPECTED_FREQ = "15min"
MAX_IMPUTABLE_GAP_HOURS = 2
NEW_METER_MIN_DAYS = 30

# Temporal Intelligence
TEMPORAL_LOOKBACK_DAYS = 14
TEMPORAL_PERSISTENCE_THRESHOLD = 0.65
TEMPORAL_TREND_SLOPE_THRESHOLD = 0.03

# Feedback Learning
INSPECTION_RESULTS_PATH = os.path.join("data", "inspection_results.csv")
AGENT_RELIABILITY_PATH = os.path.join("data", "agent_reliability.csv")
ADAPTIVE_THRESHOLDS_PATH = os.path.join("data", "adaptive_thresholds.json")
RELIABILITY_SMOOTHING = 3.0
RELIABILITY_MIN = 0.5
RELIABILITY_MAX = 1.5

# Uncertainty Estimation
CONFIDENCE_Z = 1.64
UNCERTAINTY_FLOOR = 0.05

# Synthetic Data Generation
NUM_METERS = 200
DAYS = 90
FREQ = "15min"
THEFT_METERS = 10
