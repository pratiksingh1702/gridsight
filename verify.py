import os
import json
import subprocess

print('='*50)
print('BLOCK 1: FILE COUNTS')
print('='*50)
meter_count = len(os.listdir('data/meter_readings'))
feeder_count = len(os.listdir('data/feeder_head_readings'))
case_count = len(os.listdir('case_files'))
print(f'Meter CSVs:       {meter_count}  (expected 200)')
print(f'Feeder head CSVs: {feeder_count}  (expected ~5-10)')
print(f'Case files (PDF): {case_count}')

print()
print('='*50)
print('BLOCK 2: AGENT SMOKE TESTS')
print('='*50)
try:
    from agent_cusum import cusum_score
    score = cusum_score('meter_051')
    print(f'CUSUM agent:          OK  score={score}')
except Exception as e:
    print(f'CUSUM agent:          FAIL  {e}')

try:
    from agent_peer import peer_score
    score = peer_score('meter_051')
    print(f'Peer agent:           OK  score={score}')
except Exception as e:
    print(f'Peer agent:           FAIL  {e}')

try:
    from agent_rules import rule_score
    score = rule_score('meter_051')
    print(f'Rules agent:          OK  score={score}')
except Exception as e:
    print(f'Rules agent:          FAIL  {e}')

try:
    from agent_patterns import pattern_score
    score = pattern_score('meter_051')
    print(f'Patterns agent:       OK  score={score}')
except Exception as e:
    print(f'Patterns agent:       FAIL  {e}')

try:
    from agent_feeder_balance import feeder_gap_score
    score = feeder_gap_score('Feeder_1')
    print(f'Feeder balance agent: OK  score={score}')
except Exception as e:
    print(f'Feeder balance agent: FAIL  {e}')

print()
print('='*50)
print('BLOCK 3: FUSION ENGINE - THEFT METER')
print('='*50)
try:
    from fusion_engine import evaluate_meter
    result = evaluate_meter('meter_051')
    print(f'meter_051 (bypass theft):')
    print(f'  Decision:       {result["decision"]}  (expected ESCALATE)')
    print(f'  Weighted score: {result["weighted_score"]}  (expected >=75)')
    print(f'  Agents firing:  {result["agents_firing"]}  (expected >=3)')
    print(f'  Agent scores:   {result["agent_scores"]}')
except Exception as e:
    print(f'Fusion engine FAIL: {e}')

print()
print('='*50)
print('BLOCK 4: FUSION ENGINE - CLEAN METER')
print('='*50)
try:
    from fusion_engine import evaluate_meter
    result = evaluate_meter('meter_001')
    print(f'meter_001 (clean meter):')
    print(f'  Decision:       {result["decision"]}  (expected MONITOR)')
    print(f'  Weighted score: {result["weighted_score"]}  (expected <75)')
    print(f'  Agents firing:  {result["agents_firing"]}  (expected <3)')
except Exception as e:
    print(f'Fusion engine clean test FAIL: {e}')

print()
print('='*50)
print('BLOCK 5: EVALUATION REPORT')
print('='*50)
try:
    with open('evaluation_report.json') as f:
        report = json.load(f)
    for k, v in report.items():
        print(f'  {k}: {v}')
    recall = report.get('recall_pct', report.get('recall', 0))
    precision = report.get('precision_pct', report.get('precision', 0))
    print()
    if float(str(recall).replace('%','')) >= 100:
        print('  RECALL:    PASS (100%)')
    else:
        print(f'  RECALL:    FAIL ({recall}) - should be 100%')
    if float(str(precision).replace('%','')) >= 90:
        print('  PRECISION: PASS (>=90%)')
    else:
        print(f'  PRECISION: FAIL ({precision}) - should be >=90%')
except Exception as e:
    print(f'Evaluation report FAIL: {e}')

print()
print('='*50)
print('BLOCK 6: UNIT TESTS')
print('='*50)
result = subprocess.run(['python', '-m', 'unittest', 'discover', 'tests'],
                      capture_output=True, text=True)
print(result.stdout)
if result.stderr:
    print(result.stderr)

print()
print('='*50)
print('BLOCK 7: CASE FILE CHECK')
print('='*50)
try:
    from generate_case_file import generate_case_file
    generate_case_file('meter_051')
    files = os.listdir('case_files')
    pdfs = [f for f in files if f.endswith('.pdf')]
    print(f'PDFs in case_files/: {pdfs}')
    if pdfs:
        size = os.path.getsize(f'case_files/{pdfs[-1]}')
        print(f'Latest PDF size: {size} bytes  (expected >10000)')
        if size > 10000:
            print('CASE FILE: PASS')
        else:
            print('CASE FILE: FAIL - PDF too small, likely empty')
except Exception as e:
    print(f'Case file FAIL: {e}')

print()
print('='*50)
print('VERIFICATION COMPLETE')
print('='*50)