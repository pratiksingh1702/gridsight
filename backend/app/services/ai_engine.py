import os
import sys
import logging
from datetime import datetime

# Add project root to sys.path to import project-level modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

try:
    import fusion_engine
    import config as project_config
    from data_utils import prepare_meter_series
except ImportError as e:
    logging.error(f"Failed to import project modules: {e}")
    fusion_engine = None

logger = logging.getLogger(__name__)

class AIEngine:
    def __init__(self):
        self.enabled = fusion_engine is not None
        if not self.enabled:
            logger.warning("AI Engine disabled due to missing modules.")

    def evaluate_meter(self, meter_id: str):
        if not self.enabled:
            return self._mock_evaluation(meter_id)
        
        try:
            # Use the actual fusion engine
            result = fusion_engine.evaluate_meter(meter_id, log_result=False)
            return result
        except Exception as e:
            logger.error(f"AI evaluation failed for {meter_id}: {e}")
            return self._mock_evaluation(meter_id)

    def _mock_evaluation(self, meter_id: str):
        # Fallback if AI fails or is not available
        import random
        return {
            "meter_id": meter_id,
            "decision": "monitor",
            "weighted_score": random.uniform(0, 100),
            "p_theft": random.uniform(0, 1),
            "agents_firing": random.randint(0, 5),
            "timestamp": datetime.now().isoformat()
        }

    def get_meter_data(self, meter_id: str):
        if not self.enabled:
            return None
        try:
            return prepare_meter_series(meter_id)
        except:
            return None

ai_engine = AIEngine()
