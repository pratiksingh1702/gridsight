import logging
import math
import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def score_to_probability(score: float, agent_name: str) -> float:
    params = config.AGENT_PROB_CALIBRATION.get(agent_name, config.AGENT_PROB_CALIBRATION['default'])
    alpha = params['alpha']
    beta = params['beta']
    return float(_sigmoid(alpha * (score - beta)))


def build_agent_probabilities(agent_scores: dict) -> dict:
    return {name: score_to_probability(score, name) for name, score in agent_scores.items()}


def _context_factor(agent_name: str, context: dict) -> float:
    if not context:
        return 1.0

    time_bucket = context.get('time_of_day', 'afternoon')
    factors = config.AGENT_CONTEXT_FACTORS.get(agent_name, config.AGENT_CONTEXT_FACTORS['default'])
    time_factor = factors.get(time_bucket, 1.0)

    feeder_type = context.get('feeder_type', config.FEEDER_TYPE_DEFAULT)
    feeder_factor = config.FEEDER_TYPE_FACTORS.get(feeder_type, 1.0)

    return float(time_factor * feeder_factor)


def _adjust_for_physics(p_theft: float, physics_confidence: float) -> float:
    impact = config.PHYSICS_CONFIDENCE_IMPACT
    adjusted = p_theft * (1.0 + (physics_confidence - 0.5) * impact)
    return float(min(1.0, max(0.0, adjusted)))


def _confidence_interval(p_theft: float, n_eff: float) -> tuple[float, float]:
    if n_eff <= 0:
        return (max(0.0, p_theft - 0.1), min(1.0, p_theft + 0.1))

    variance = (p_theft * (1.0 - p_theft)) / n_eff
    margin = config.CONFIDENCE_Z * math.sqrt(max(0.0, variance))
    return (max(0.0, p_theft - margin), min(1.0, p_theft + margin))


def fuse_probabilities(
    agent_probs: dict,
    residual_pattern: dict,
    physics: dict,
    agent_scores: dict,
    context: dict | None = None,
    reliability: dict | None = None,
    temporal: dict | None = None,
    data_quality: dict | None = None
) -> dict:
    coefs = config.FUSION_LOGIT_COEFS
    bias = coefs.get('bias', 0.0)

    residual_type = residual_pattern.get('type', 'unknown')
    residual_features = {
        'residual_sudden_drop': 1.0 if residual_type == 'sudden_drop' else 0.0,
        'residual_periodic_zero': 1.0 if residual_type == 'periodic_zero' else 0.0,
        'residual_gradual_drift': 1.0 if residual_type == 'gradual_drift' else 0.0
    }

    energy_balance = physics.get('energy_balance', {}) if physics else {}
    gap_pct = float(energy_balance.get('gap_pct', 0.0))
    gap_feature = min(1.0, gap_pct / config.FEEDER_GAP_ALERT_THRESHOLD) if config.FEEDER_GAP_ALERT_THRESHOLD > 0 else 0.0

    phase = physics.get('phase_imbalance', {}) if physics else {}
    phase_score = float(phase.get('score', 0.0))
    phase_feature = min(1.0, phase_score / 100.0)

    firing_count = sum(1 for score in agent_scores.values() if score >= config.AGENT_FIRE_THRESHOLD)
    firing_ratio = min(1.0, firing_count / max(1, len(agent_scores)))

    reliability = reliability or {}
    adjusted_agent_probs = {}
    for name, prob in agent_probs.items():
        reliability_factor = reliability.get(name, 1.0)
        context_factor = _context_factor(name, context or {})
        adjusted_prob = prob * reliability_factor * context_factor
        adjusted_agent_probs[name] = float(min(1.0, max(0.0, adjusted_prob)))

    context_features = {
        'context_night': 1.0 if (context or {}).get('time_of_day') == 'night' else 0.0,
        'context_morning': 1.0 if (context or {}).get('time_of_day') == 'morning' else 0.0,
        'context_afternoon': 1.0 if (context or {}).get('time_of_day') == 'afternoon' else 0.0,
        'context_evening': 1.0 if (context or {}).get('time_of_day') == 'evening' else 0.0,
        'context_load_low': 1.0 if (context or {}).get('load_level') == 'low' else 0.0,
        'context_load_high': 1.0 if (context or {}).get('load_level') == 'high' else 0.0,
        'context_feeder_industrial': 1.0 if (context or {}).get('feeder_type') == 'industrial' else 0.0,
        'context_feeder_rural': 1.0 if (context or {}).get('feeder_type') == 'rural' else 0.0
    }

    temporal_features = {
        'temporal_persistence': 1.0 if (temporal or {}).get('is_persistent') else 0.0,
        'temporal_trend': float((temporal or {}).get('trend_slope', 0.0))
    }

    features = {
        **adjusted_agent_probs,
        **residual_features,
        'physics_gap': gap_feature,
        'phase_imbalance': phase_feature,
        'firing_ratio': firing_ratio,
        **context_features,
        **temporal_features
    }

    linear = bias
    for name, value in features.items():
        weight = coefs.get(name, 0.0)
        linear += weight * value

    p_theft = _sigmoid(linear)

    physics_confidence = float((physics or {}).get('physics_confidence', 0.5))
    p_theft = _adjust_for_physics(p_theft, physics_confidence)

    n_eff = sum(reliability.get(name, 1.0) for name in agent_probs)
    ci_low, ci_high = _confidence_interval(p_theft, n_eff)

    missing_ratio = float((data_quality or {}).get('missing_ratio', 0.0))
    imputed_ratio = float((data_quality or {}).get('imputed_ratio', 0.0))
    uncertainty = max(config.UNCERTAINTY_FLOOR, 1.0 / (1.0 + n_eff))
    uncertainty = min(1.0, uncertainty + 0.5 * missing_ratio + 0.3 * imputed_ratio)

    return {
        'p_theft': float(p_theft),
        'linear_score': float(linear),
        'features': features,
        'physics_confidence': physics_confidence,
        'p_theft_ci_low': float(ci_low),
        'p_theft_ci_high': float(ci_high),
        'uncertainty': float(uncertainty)
    }
