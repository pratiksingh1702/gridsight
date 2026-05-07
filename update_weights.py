import os
import logging
from datetime import datetime
import config
from feedback_learning import record_inspection_result
from data_utils import load_escalation_log

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def update_agent_weights(meter_id: str, outcome: str):
    """
    Adjusts agent weights based on field inspection feedback.
    outcome: "tampered" or "clean"
    """
    logger.info(f"[{meter_id}] Updating weights for outcome: {outcome}")
    
    # 1. Get which agents fired for this meter
    log_path = os.path.join("data", "escalation_log.csv")
    if not os.path.exists(log_path):
        return
        
    df_log = load_escalation_log(log_path)
    if df_log.empty:
        return
    res = df_log[df_log['meter_id'] == meter_id].iloc[-1]
    
    import ast
    agent_scores = ast.literal_eval(res['agent_scores'])
    firing_agents = [name for name, score in agent_scores.items() if score >= config.AGENT_FIRE_THRESHOLD]
    
    # 2. Update logic
    weights = config.AGENT_WEIGHTS.copy()
    delta = 0.1 if outcome == "tampered" else -0.05
    
    for agent in firing_agents:
        weights[agent] = max(0.1, weights[agent] + delta)
        
    # 3. Normalize to keep sum constant (initially 5.0 for 5 core agents, or sum of current)
    original_sum = sum(config.AGENT_WEIGHTS.values())
    new_sum = sum(weights.values())
    
    for agent in weights:
        weights[agent] = (weights[agent] / new_sum) * original_sum
        
    # 4. Log changes
    logger.info(f"New weights: {weights}")

    outcome_key = "confirmed_theft" if outcome == "tampered" else "false_positive"
    try:
        record_inspection_result(meter_id, outcome_key)
    except Exception as exc:
        logger.warning("[%s] Feedback learning update failed: %s", meter_id, exc)
    
    # Note: In production, we'd update config.py or a dynamic DB table.
    # For prototype, we'll write to a weights log.
    weights_log = os.path.join("data", "agent_weights_log.csv")
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "meter_id": meter_id,
        "outcome": outcome,
        "new_weights": str(weights)
    }
    
    log_df = pd.DataFrame([log_entry])
    if os.path.exists(weights_log):
        log_df.to_csv(weights_log, mode='a', header=False, index=False)
    else:
        log_df.to_csv(weights_log, index=False)

if __name__ == "__main__":
    # Smoke test
    # Ensure escalation_log exists
    if os.path.exists(os.path.join("data", "escalation_log.csv")):
        update_agent_weights("meter_000", "clean")
