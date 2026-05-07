import pandas as pd
import json
from fusion_engine import evaluate_meter

print('='*60)
print('THEFT METER FINAL CHECK')
print('='*60)

gt = pd.read_csv('data/theft_ground_truth.csv')
caught = []
missed = []

for _, row in gt.iterrows():
    mid = row['meter_id']
    theft_type = row['theft_type']
    r = evaluate_meter(mid)
    status = 'CAUGHT' if r['decision'] == 'ESCALATE' else 'MISSED'
    if status == 'CAUGHT':
        caught.append(mid)
    else:
        missed.append(mid)
    print(f'{status} | {mid} | {theft_type} | score={r["weighted_score"]:.1f} | agents={r["agents_firing"]}')
    print(f'       agent scores: {r["agent_scores"]}')
    print()

print('='*60)
print(f'RECALL: {len(caught)}/10 = {len(caught)*10}%')
print(f'CAUGHT: {caught}')
print(f'MISSED: {missed}')
print('='*60)

print()
print('EVALUATION REPORT:')
with open('evaluation_report.json') as f:
    print(json.dumps(json.load(f), indent=2))