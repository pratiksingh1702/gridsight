import pandas as pd
import os
import logging
from fusion_engine import evaluate_meter

# Configure logging to show minimal info
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def run_diagnostic():
    ground_truth = pd.read_csv("data/theft_ground_truth.csv")
    theft_meter_ids = ground_truth["meter_id"].tolist()

    print(f"--- Running Diagnostic Evaluation for {len(theft_meter_ids)} Theft Meters ---")
    
    escalated = []
    for meter_id in theft_meter_ids:
        try:
            result = evaluate_meter(meter_id)
            print(f"{meter_id}: decision={result['decision']}, score={result['weighted_score']:.1f}, agents={result['agents_firing']}")
            if result["decision"] == "ESCALATE":
                escalated.append(meter_id)
        except Exception as e:
            print(f"{meter_id}: FAILED with error {e}")

    recall = len(escalated) / len(theft_meter_ids) * 100
    print(f"\nRecall: {recall:.1f}% ({len(escalated)}/{len(theft_meter_ids)} caught)")

if __name__ == "__main__":
    run_diagnostic()
