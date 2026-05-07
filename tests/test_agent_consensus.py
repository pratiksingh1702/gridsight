import unittest
import config
from probabilistic_fusion import build_agent_probabilities, fuse_probabilities

class TestAgentConsensus(unittest.TestCase):
    def test_minimum_agents_firing(self):
        # Simulate agent scores where only 2 agents fire (threshold is 3)
        # Even if scores are high, it shouldn't escalate
        agent_scores = {
            "cusum": 90,
            "peer": 90,
            "rules": 0,
            "patterns": 0,
            "feeder_balance": 0,
            "isolation_forest": 0
        }
        
        agent_probs = build_agent_probabilities(agent_scores)
        fusion = fuse_probabilities(agent_probs, {"type": "normal"}, {}, agent_scores)
        self.assertLess(
            fusion['p_theft'],
            config.FUSION_PROB_THRESHOLD,
            "Should not escalate with only 2 agents firing."
        )

    def test_score_threshold(self):
        # Simulate 3 agents firing but low total score
        agent_scores = {
            "cusum": 45,
            "peer": 45,
            "rules": 45,
            "patterns": 0,
            "feeder_balance": 0,
            "isolation_forest": 0
        }
        
        agent_probs = build_agent_probabilities(agent_scores)
        fusion = fuse_probabilities(agent_probs, {"type": "normal"}, {}, agent_scores)
        self.assertLess(
            fusion['p_theft'],
            config.FUSION_PROB_THRESHOLD,
            f"Should not escalate with P(theft) {fusion['p_theft']:.2f} below threshold."
        )

if __name__ == "__main__":
    unittest.main()
