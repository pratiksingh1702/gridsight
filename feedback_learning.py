import os
import json
import logging
from datetime import datetime
import pandas as pd
import config

from data_utils import load_escalation_log
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def _load_escalation_record(meter_id: str) -> dict | None:
    log_path = os.path.join("data", "escalation_log.csv")
    if not os.path.exists(log_path):
        return None

    df = load_escalation_log(log_path)
    row = df[df['meter_id'] == meter_id]
    if row.empty:
        return None

    return row.iloc[-1].to_dict()


def _parse_json(value):
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    try:
        return json.loads(value)
    except Exception:
        return {}


def load_agent_reliability() -> dict:
    if not os.path.exists(config.AGENT_RELIABILITY_PATH):
        return {agent: 1.0 for agent in config.AGENT_WEIGHTS}

    df = pd.read_csv(config.AGENT_RELIABILITY_PATH)
    if df.empty:
        return {agent: 1.0 for agent in config.AGENT_WEIGHTS}

    reliabilities = {row['agent']: float(row['reliability']) for _, row in df.iterrows()}
    for agent in config.AGENT_WEIGHTS:
        reliabilities.setdefault(agent, 1.0)

    return reliabilities


def _save_agent_reliability(stats: dict):
    records = []
    for agent, data in stats.items():
        records.append({
            'agent': agent,
            'correct': data['correct'],
            'total': data['total'],
            'reliability': data['reliability']
        })

    df = pd.DataFrame(records)
    os.makedirs(os.path.dirname(config.AGENT_RELIABILITY_PATH), exist_ok=True)
    df.to_csv(config.AGENT_RELIABILITY_PATH, index=False)


def update_agent_reliability(agent_scores: dict, outcome: str):
    stats = {}
    if os.path.exists(config.AGENT_RELIABILITY_PATH):
        df = pd.read_csv(config.AGENT_RELIABILITY_PATH)
        for _, row in df.iterrows():
            stats[row['agent']] = {
                'correct': float(row.get('correct', 0.0)),
                'total': float(row.get('total', 0.0)),
                'reliability': float(row.get('reliability', 1.0))
            }

    for agent in config.AGENT_WEIGHTS:
        stats.setdefault(agent, {'correct': 0.0, 'total': 0.0, 'reliability': 1.0})

    fired_agents = [name for name, score in agent_scores.items() if score >= config.AGENT_FIRE_THRESHOLD]
    for agent in fired_agents:
        stats[agent]['total'] += 1.0
        if outcome == 'confirmed_theft':
            stats[agent]['correct'] += 1.0

    for agent, data in stats.items():
        accuracy = (data['correct'] + config.RELIABILITY_SMOOTHING) / (data['total'] + 2 * config.RELIABILITY_SMOOTHING)
        reliability = config.RELIABILITY_MIN + (config.RELIABILITY_MAX - config.RELIABILITY_MIN) * accuracy
        data['reliability'] = float(reliability)

    _save_agent_reliability(stats)


def update_adaptive_thresholds(outcome: str):
    thresholds = {
        'fusion_prob_threshold': config.FUSION_PROB_THRESHOLD,
        'anomaly_noise_threshold': 0.45
    }

    if os.path.exists(config.ADAPTIVE_THRESHOLDS_PATH):
        try:
            with open(config.ADAPTIVE_THRESHOLDS_PATH, 'r') as f:
                thresholds.update(json.load(f))
        except Exception:
            pass

    if outcome == 'false_positive':
        thresholds['fusion_prob_threshold'] = min(0.9, thresholds['fusion_prob_threshold'] + 0.02)
        thresholds['anomaly_noise_threshold'] = min(0.6, thresholds['anomaly_noise_threshold'] + 0.01)
    elif outcome == 'missed_theft':
        thresholds['fusion_prob_threshold'] = max(0.5, thresholds['fusion_prob_threshold'] - 0.02)
        thresholds['anomaly_noise_threshold'] = max(0.35, thresholds['anomaly_noise_threshold'] - 0.01)

    os.makedirs(os.path.dirname(config.ADAPTIVE_THRESHOLDS_PATH), exist_ok=True)
    with open(config.ADAPTIVE_THRESHOLDS_PATH, 'w') as f:
        json.dump(thresholds, f, indent=2)


def record_inspection_result(
    meter_id: str,
    outcome: str,
    theft_type: str | None = None,
    notes: str | None = None
) -> dict:
    if outcome not in ['confirmed_theft', 'false_positive', 'missed_theft']:
        raise ValueError("outcome must be confirmed_theft, false_positive, or missed_theft")

    escalation = _load_escalation_record(meter_id)
    agent_scores = _parse_json(escalation.get('agent_scores')) if escalation else {}

    update_agent_reliability(agent_scores, outcome)
    update_adaptive_thresholds(outcome)

    entry = {
        'timestamp': datetime.now().isoformat(),
        'meter_id': meter_id,
        'outcome': outcome,
        'theft_type': theft_type or '',
        'notes': notes or ''
    }

    os.makedirs(os.path.dirname(config.INSPECTION_RESULTS_PATH), exist_ok=True)
    if os.path.exists(config.INSPECTION_RESULTS_PATH):
        df = pd.read_csv(config.INSPECTION_RESULTS_PATH)
        df = pd.concat([df, pd.DataFrame([entry])], ignore_index=True)
    else:
        df = pd.DataFrame([entry])
    df.to_csv(config.INSPECTION_RESULTS_PATH, index=False)

    return entry
