import unittest
import config
from probabilistic_fusion import build_agent_probabilities, fuse_probabilities

class TestFalsePositiveFilter(unittest.TestCase):
    def test_vacation_scenario(self):
        """
        Walks through the vacation scenario where consumption drops but peer group also drops.
        Only the Rules Agent flags (zero-consumption), but since others are clean, it stays MONITOR.
        """
        # Vacation Scenario:
        # 1. Consumption drops -> CUSUM might not fire if it was a gradual holiday start
        # 2. Peer group also drops -> Peer Agent remains CLEAN
        # 3. Consumption < 0.1 -> Rules Agent flags (80)
        # 4. No specific theft patterns -> Pattern Agent CLEAN
        # 5. Feeder balance remains correct -> Feeder Agent CLEAN
        
        agent_scores = {
            "cusum": 10,
            "peer": 5,
            "rules": 80,
            "patterns": 10,
            "feeder_balance": 5,
            "isolation_forest": 0
        }
        
        agent_probs = build_agent_probabilities(agent_scores)
        fusion = fuse_probabilities(agent_probs, {"type": "normal"}, {}, agent_scores)

        print(
            f"Vacation Scenario: P(theft)={fusion['p_theft']:.2f}, Decision={'ESCALATE' if fusion['p_theft'] >= config.FUSION_PROB_THRESHOLD else 'MONITOR'}"
        )
        self.assertLess(
            fusion['p_theft'],
            config.FUSION_PROB_THRESHOLD,
            "Vacation scenario should not escalate."
        )

if __name__ == "__main__":
    unittest.main()
