import logging
import json
import os
import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def _urgency_level(p_theft: float, roi: float, loss_value: float) -> str:
    if p_theft >= config.URGENCY_THRESHOLDS['critical'] or (roi >= config.ROI_TARGET and loss_value >= config.LOSS_SCALE_FOR_PRIORITY):
        return 'CRITICAL'
    if p_theft >= config.URGENCY_THRESHOLDS['high'] or roi >= config.ROI_TARGET:
        return 'HIGH'
    if p_theft >= config.URGENCY_THRESHOLDS['medium']:
        return 'MEDIUM'
    return 'LOW'


def _inspection_schedule(urgency: str) -> str:
    return {
        'CRITICAL': 'Within 24 hours',
        'HIGH': 'Within 3 days',
        'MEDIUM': 'Within 7 days',
        'LOW': 'Monitor, recheck in 14 days'
    }[urgency]


def _load_adaptive_thresholds() -> dict:
    if not os.path.exists(config.ADAPTIVE_THRESHOLDS_PATH):
        return {
            'fusion_prob_threshold': config.FUSION_PROB_THRESHOLD,
            'anomaly_noise_threshold': 0.45
        }

    try:
        with open(config.ADAPTIVE_THRESHOLDS_PATH, 'r') as f:
            data = json.load(f)
    except Exception:
        data = {}

    data.setdefault('fusion_prob_threshold', config.FUSION_PROB_THRESHOLD)
    data.setdefault('anomaly_noise_threshold', 0.45)
    return data


def make_decision(p_theft: float, economic: dict, theft_class: dict, temporal: dict | None = None) -> dict:
    roi = float(economic.get('roi', 0.0))
    loss_value = float(economic.get('loss_value', 0.0))
    expected_value = float(economic.get('expected_value', 0.0))

    thresholds = _load_adaptive_thresholds()
    fusion_threshold = thresholds['fusion_prob_threshold']

    escalate = p_theft >= fusion_threshold
    if not escalate and roi >= config.FUSION_FORCE_INSPECTION_ROI and p_theft >= config.FUSION_MIN_PROB_FOR_ROI:
        escalate = True
    if not escalate and expected_value >= config.MIN_EXPECTED_VALUE_FOR_ESCALATION:
        escalate = True

    if temporal and temporal.get('is_persistent') and p_theft >= config.URGENCY_THRESHOLDS['medium']:
        escalate = True

    urgency = _urgency_level(p_theft, roi, loss_value)
    if temporal and temporal.get('persistence_days', 0) >= config.PERSISTENCE_DAYS_HIGH:
        urgency = 'HIGH' if urgency == 'MEDIUM' else urgency

    schedule = _inspection_schedule(urgency)

    if escalate:
        action = f"Dispatch inspection for {theft_class.get('class', 'anomaly')}"
    else:
        action = "Monitor and schedule follow-up analytics"

    return {
        'decision': 'ESCALATE' if escalate else 'MONITOR',
        'action_recommendation': action,
        'urgency': urgency,
        'inspection_schedule': schedule,
        'fusion_threshold': fusion_threshold
    }
