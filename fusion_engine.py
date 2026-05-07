import os
import json
import pandas as pd
import logging
from datetime import datetime
import config

# Import Agents
from agent_cusum import cusum_score
from agent_peer import peer_score
from agent_rules import rule_score
from agent_patterns import pattern_score
from agent_feeder_balance import feeder_gap_score
from agent_isolation_forest import isolation_forest_score
from residual_intelligence import compute_residuals, classify_residual_pattern
from probabilistic_fusion import build_agent_probabilities, fuse_probabilities
from physics_engine import evaluate_feeder_physics
from theft_classifier import classify_theft, classify_incident
from economic_impact import compute_economic_impact
from decision_engine import make_decision
from explainability import build_explainability
from context_features import build_context_features
from temporal_intelligence import compute_temporal_metrics
from feedback_learning import load_agent_reliability
from data_utils import prepare_meter_series, compute_data_quality

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def _safe_agent_call(fn, meter_id: str, default):
    try:
        return fn(meter_id)
    except Exception as exc:
        logger.warning("[%s] Agent %s failed: %s", meter_id, fn.__name__, exc)
        return default


def evaluate_meter(meter_id: str, log_result: bool = True) -> dict:
    """
    Runs all anomaly detection agents on a meter and returns escalation decision.
    """
    logger.info(f"[{meter_id}] Starting fusion evaluation...")
    
    metadata_path = os.path.join("data", "feeder_metadata.csv")
    feeder_id = None
    if os.path.exists(metadata_path):
        metadata = pd.read_csv(metadata_path)
        if not metadata[metadata['meter_id'] == meter_id].empty:
            feeder_id = metadata[metadata['meter_id'] == meter_id].iloc[0]['feeder_id']

    res_cusum = _safe_agent_call(cusum_score, meter_id, {"score": 0.0, "detection_date": None})
    res_peer = _safe_agent_call(peer_score, meter_id, 0.0)
    res_rules = _safe_agent_call(rule_score, meter_id, 0.0)
    res_patterns = _safe_agent_call(pattern_score, meter_id, 0.0)
    res_iforest = _safe_agent_call(isolation_forest_score, meter_id, 0.0)

    res_feeder = 0.0
    if feeder_id:
        try:
            res_feeder = feeder_gap_score(feeder_id).get(meter_id, 0.0)
        except Exception as exc:
            logger.warning("[%s] Feeder balance failed: %s", meter_id, exc)
    
    agent_scores = {
        "cusum": res_cusum['score'],
        "peer": res_peer,
        "rules": res_rules,
        "patterns": res_patterns,
        "feeder_balance": res_feeder,
        "isolation_forest": res_iforest
    }
    
    # 2. Legacy Weighted Score (for compatibility)
    weights = config.AGENT_WEIGHTS
    numerator = sum(agent_scores[name] * weights[name] for name in agent_scores)
    denominator = sum(weights.values())
    weighted_score = numerator / denominator if denominator > 0 else 0.0

    # 3. Residual Intelligence
    residual_df = compute_residuals(meter_id)
    residual_pattern = classify_residual_pattern(residual_df)

    # 3b. Context + Data Quality
    context = build_context_features(meter_id)
    meter_df = prepare_meter_series(meter_id)
    data_quality = compute_data_quality(meter_df) if meter_df is not None else {}

    # 3c. Temporal Intelligence
    temporal = compute_temporal_metrics(meter_id)

    # 4. Physics Engine
    physics = evaluate_feeder_physics(feeder_id) if feeder_id else {}

    # 5. Probabilistic Fusion
    agent_probs = build_agent_probabilities(agent_scores)
    reliability = load_agent_reliability()
    fusion = fuse_probabilities(
        agent_probs,
        residual_pattern,
        physics,
        agent_scores,
        context=context,
        reliability=reliability,
        temporal=temporal,
        data_quality=data_quality
    )
    p_theft = fusion['p_theft']

    # 6. Theft Classification
    theft_class = classify_theft(residual_pattern, agent_scores, physics)
    hierarchical = classify_incident(p_theft, residual_pattern, agent_scores, physics, temporal)

    # 7. Economic Impact
    economic = compute_economic_impact(meter_id, residual_df, p_theft)

    # 8. Decision Engine
    decision_details = make_decision(p_theft, economic, theft_class, temporal)
    decision = decision_details['decision']

    # 9. Explainability
    explainability = build_explainability(
        agent_scores,
        agent_probs,
        residual_pattern,
        physics,
        economic,
        context=context,
        temporal=temporal,
        fusion_meta=fusion
    )

    # 10. Agent firing count (for reporting)
    firing_count = sum(1 for score in agent_scores.values() if score >= config.AGENT_FIRE_THRESHOLD)
        
    result = {
        "meter_id": meter_id,
        "feeder_id": feeder_id,
        "timestamp": datetime.now().isoformat(),
        "decision": decision,
        "weighted_score": float(weighted_score),
        "p_theft": float(p_theft),
        "agents_firing": int(firing_count),
        "agent_scores": agent_scores,
        "agent_probabilities": agent_probs,
        "residual_pattern": residual_pattern,
        "physics": physics,
        "physics_confidence": fusion.get('physics_confidence', 0.0),
        "context_features": context,
        "temporal_metrics": temporal,
        "data_quality": data_quality,
        "hierarchical_classification": hierarchical,
        "theft_class": theft_class,
        "p_theft_ci_low": fusion.get('p_theft_ci_low'),
        "p_theft_ci_high": fusion.get('p_theft_ci_high'),
        "uncertainty": fusion.get('uncertainty'),
        "economic": economic,
        "decision_details": decision_details,
        "explainability": explainability,
        "evidence": res_cusum.get('detection_date')
    }

    # 11. Log result
    if log_result:
        log_path = os.path.join("data", "escalation_log.csv")
        loggable = result.copy()
        loggable['agent_scores'] = json.dumps(agent_scores)
        loggable['agent_probabilities'] = json.dumps(agent_probs)
        loggable['residual_pattern'] = json.dumps(residual_pattern)
        loggable['physics'] = json.dumps(physics)
        loggable['physics_confidence'] = fusion.get('physics_confidence')
        loggable['context_features'] = json.dumps(context)
        loggable['temporal_metrics'] = json.dumps(temporal)
        loggable['data_quality'] = json.dumps(data_quality)
        loggable['hierarchical_classification'] = json.dumps(hierarchical)
        loggable['theft_class'] = json.dumps(theft_class)
        loggable['p_theft_ci_low'] = fusion.get('p_theft_ci_low')
        loggable['p_theft_ci_high'] = fusion.get('p_theft_ci_high')
        loggable['uncertainty'] = fusion.get('uncertainty')
        loggable['economic'] = json.dumps(economic)
        loggable['decision_details'] = json.dumps(decision_details)
        loggable['explainability'] = json.dumps(explainability)

        log_df = pd.DataFrame([loggable])
        if os.path.exists(log_path):
            log_df.to_csv(log_path, mode='a', header=False, index=False)
        else:
            log_df.to_csv(log_path, index=False)

    return result

if __name__ == "__main__":
    # Smoke test
    res = evaluate_meter("meter_000")
    logger.info(
        f"Fusion Result for meter_000: {res['decision']} (P: {res['p_theft']:.2f}, Score: {res['weighted_score']:.1f})"
    )
