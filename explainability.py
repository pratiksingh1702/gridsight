import logging
import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def build_explainability(
    agent_scores: dict,
    agent_probs: dict,
    residual_pattern: dict,
    physics: dict,
    economic: dict,
    context: dict | None = None,
    temporal: dict | None = None,
    fusion_meta: dict | None = None
) -> dict:
    factors = []
    reasoning_chain = []

    if residual_pattern and residual_pattern.get('type') not in ['normal', 'unknown']:
        factors.append(
            f"Residual pattern: {residual_pattern.get('type')} (conf {residual_pattern.get('confidence', 0.0):.2f})"
        )
        reasoning_chain.append("Residual intelligence flagged a structured deviation pattern.")

    energy_balance = physics.get('energy_balance', {}) if physics else {}
    gap_pct = float(energy_balance.get('gap_pct', 0.0))
    if gap_pct >= config.FEEDER_GAP_ALERT_THRESHOLD:
        factors.append(f"Feeder energy gap {gap_pct:.1f}%")
        reasoning_chain.append("Energy balance shows a material feeder gap beyond expected losses.")

    phase = physics.get('phase_imbalance', {}) if physics else {}
    if phase.get('is_imbalanced'):
        factors.append(f"Phase imbalance detected (std {phase.get('voltage_std', 0.0):.1f}V)")
        reasoning_chain.append("Phase imbalance indicates possible technical anomalies.")

    sorted_agents = sorted(agent_probs.items(), key=lambda item: item[1], reverse=True)
    for name, prob in sorted_agents[:3]:
        score = agent_scores.get(name, 0.0)
        factors.append(f"{name} agent score {score:.1f} (p={prob:.2f})")
        reasoning_chain.append(f"{name} agent contributed strongly to theft probability.")

    if context:
        factors.append(
            f"Context: {context.get('time_of_day', 'unknown')} | load {context.get('load_level', 'normal')} | feeder {context.get('feeder_type', 'mixed')}"
        )
        reasoning_chain.append("Context-aware fusion adjusted weights based on time and load regime.")

    if temporal:
        factors.append(
            f"Temporal: persistence {temporal.get('persistence_days', 0)} days, trend {temporal.get('trend_slope', 0.0):.2f}"
        )
        reasoning_chain.append("Temporal intelligence evaluated persistence vs transient anomalies.")

    if fusion_meta:
        reasoning_chain.append(
            f"Final probability adjusted by physics confidence {fusion_meta.get('physics_confidence', 0.5):.2f}."
        )

    return {
        'contributing_factors': factors,
        'reasoning_chain': reasoning_chain,
        'agent_scores': agent_scores,
        'agent_probabilities': agent_probs,
        'physics_validation': physics,
        'economic_impact': economic,
        'confidence_interval': {
            'p_theft_low': fusion_meta.get('p_theft_ci_low') if fusion_meta else None,
            'p_theft_high': fusion_meta.get('p_theft_ci_high') if fusion_meta else None
        },
        'uncertainty': fusion_meta.get('uncertainty') if fusion_meta else None
    }
