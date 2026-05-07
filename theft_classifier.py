import logging
import json
import os
import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def classify_theft(residual_pattern: dict, agent_scores: dict, physics: dict) -> dict:
    pattern_type = residual_pattern.get('type', 'unknown')
    physics_gap = float(physics.get('energy_balance', {}).get('gap_pct', 0.0)) if physics else 0.0
    phase_imbalance = bool(physics.get('phase_imbalance', {}).get('is_imbalanced', False)) if physics else False

    rules_score = agent_scores.get('rules', 0.0)
    patterns_score = agent_scores.get('patterns', 0.0)
    cusum_score = agent_scores.get('cusum', 0.0)

    if pattern_type == 'sudden_drop' and (patterns_score >= 70 or rules_score >= 70) and physics_gap > 0:
        return {'class': 'bypass', 'confidence': 0.8}

    if pattern_type == 'periodic_zero' or (patterns_score >= 60 and rules_score >= 50):
        return {'class': 'illegal_tapping', 'confidence': 0.65}

    if pattern_type == 'gradual_drift' or (cusum_score >= 60 and phase_imbalance):
        return {'class': 'tampering', 'confidence': 0.6}

    return {'class': 'normal_anomaly', 'confidence': 0.4}


def _load_anomaly_threshold() -> float:
    if not os.path.exists(config.ADAPTIVE_THRESHOLDS_PATH):
        return 0.45
    try:
        with open(config.ADAPTIVE_THRESHOLDS_PATH, 'r') as f:
            data = json.load(f)
        return float(data.get('anomaly_noise_threshold', 0.45))
    except Exception:
        return 0.45


def classify_incident(
    p_theft: float,
    residual_pattern: dict,
    agent_scores: dict,
    physics: dict,
    temporal: dict
) -> dict:
    anomaly_threshold = _load_anomaly_threshold()
    if temporal.get('is_persistent'):
        anomaly_threshold = 0.4

    stage_1 = 'anomaly' if p_theft >= anomaly_threshold else 'noise'

    physics_conf = float(physics.get('physics_confidence', 0.5)) if physics else 0.5
    tech_signal = bool(physics.get('phase_imbalance', {}).get('is_imbalanced', False)) if physics else False
    stage_2 = 'theft' if (p_theft >= 0.55 and physics_conf >= 0.45 and not tech_signal) else 'technical_issue'

    theft_type = classify_theft(residual_pattern, agent_scores, physics)

    return {
        'stage_1': stage_1,
        'stage_2': stage_2,
        'theft_type': theft_type,
        'confidence': min(1.0, max(0.0, p_theft))
    }
