# MASTER PROMPT FOR AI CODING ASSISTANT
## Project: GridSight — BESCOM Hackathon Prototype (Theme 8)
## Copy this entire file and paste it to your AI coding assistant (Cursor, Windsurf, Claude, etc.)
## Read every section before starting. Do not skip anything.

---

## YOUR ROLE

You are a senior ML engineer and full-stack Python developer. You are building
**GridSight** — a complete, working hackathon prototype for BESCOM's Theme 8:
"AI for Smart Meter Intelligence & Loss Detection."

You have been given three reference files. You MUST read all three before writing
a single line of code:

1. `GRIDSIGHT_FULL_PLAN.md` — Strategy, architecture, component design, evaluation targets.
2. `GRIDSIGHT_BUILD_PROMPT.md` — Week-by-week task list, exact function signatures, deliverables checklist.
3. `SUGGESTIONS.md` — Seven improvements that MUST be incorporated. Do not skip any rated CRITICAL or HIGH.

These three files are your single source of truth. If any instruction in this master
prompt conflicts with those files, the files win.

---

## THE PROBLEM YOU ARE SOLVING

BESCOM's smart meters generate 15-minute kWh readings but the data is only used for billing.
Two problems remain unsolved:

**Problem A:** No early warning when a feeder or transformer is about to hit capacity.
Transformers trip. Outages cascade. Crews react after the fact.

**Problem B:** Revenue leakage from electricity theft. India's AT&C losses are 20-25%.
Inspections are random and low-yield. There is no systematic detection system.

**GridSight closes both gaps** as a read-only decision-support layer. It never modifies
any BESCOM system. All outputs are advisories. Humans decide and act.

---

## ABSOLUTE NON-NEGOTIABLES (Build these in from day one, never compromise them)

- NO modification to existing systems. Read-only, always.
- NO hosted LLM touching raw meter data. All models run locally.
- ALL data must be synthetic or masked. Use Faker for names/addresses.
- ALL outputs must be explainable — every alert has a full evidence trail.
- FALSE POSITIVES are minimised through multi-agent consensus, not just thresholds.
- The system is a DECISION-SUPPORT LAYER. No auto-disconnects, no automated actions.

---

## ENVIRONMENT SETUP (Do this first, before any code)

### Install required software:
- Python 3.10+
- PostgreSQL 15+ with TimescaleDB extension
- VS Code or any editor

### Install all Python packages in one command:
```bash
pip install pandas numpy prophet streamlit folium streamlit-folium \
  scikit-learn statsmodels reportlab faker psycopg2-binary \
  great-expectations pytorch-forecasting torch matplotlib plotly
```

### Project folder structure to create:
```
gridsight/
├── config.py                    ← Create this FIRST (see below)
├── setup_db.py
├── generate_data.py
├── validate_and_load.py
├── forecast_meters.py
├── forecast_zone.py
├── risk_zone.py
├── agent_cusum.py
├── agent_peer.py
├── agent_rules.py
├── agent_patterns.py
├── agent_feeder_balance.py
├── agent_isolation_forest.py    ← Optional Agent 6
├── fusion_engine.py
├── generate_case_file.py
├── field_app.py
├── update_weights.py
├── evaluate.py
├── app.py
├── dashboard_demand.py
├── demo.sh
├── README.md
├── DECISIONS.md
├── data/
│   ├── meter_readings/          ← one CSV per meter
│   ├── feeder_head_readings/    ← one CSV per feeder (CRITICAL: see Suggestion 1)
│   ├── feeder_metadata.csv
│   ├── weather.csv
│   └── theft_ground_truth.csv
├── models/
│   └── prophet/
├── case_files/
└── tests/
    ├── test_agent_consensus.py
    └── test_false_positive_filter.py
```

---

## STEP 0 — CREATE config.py FIRST (Before anything else)

This is the single file where all tunable parameters live.
Every other file must import from here. Do not hardcode any threshold anywhere else.

```python
# config.py
# All tunable parameters for GridSight.
# BESCOM analysts adjust these without touching model code.

# Theft Detection
ESCALATION_SCORE_THRESHOLD = 75
MIN_AGENTS_FIRING = 3
PERSISTENCE_DAYS = 7
AGENT_FIRE_THRESHOLD = 40

# Agent Weights (initially equal, updated by feedback loop)
AGENT_WEIGHTS = {
    "cusum": 1.0,
    "peer": 1.0,
    "rules": 1.0,
    "patterns": 1.0,
    "feeder_balance": 1.0,
    "isolation_forest": 0.0,  # Disabled by default; enable via dashboard toggle
}

# Feeder Balance
NORMAL_TECHNICAL_LOSS_PCT = 3.0
FEEDER_GAP_ALERT_THRESHOLD = 5.0
FESTIVAL_DAY_TOLERANCE = 10.0

# Demand Forecasting Risk Zones
RISK_ZONE_YELLOW = 0.70
RISK_ZONE_ORANGE = 0.85
RISK_ZONE_RED = 0.95

# Data Pipeline
MAX_IMPUTABLE_GAP_HOURS = 2
NEW_METER_MIN_DAYS = 30

# Synthetic Data Generation
NUM_METERS = 200
DAYS = 90
FREQ = "15min"
THEFT_METERS = 10
```

---

## WEEK 1 — DATA FOUNDATION

### STEP 1: setup_db.py
Build this first. Connects to local PostgreSQL, creates the `gridsight` database,
creates a TimescaleDB hypertable `meter_readings` with columns:
`meter_id TEXT, timestamp TIMESTAMPTZ, kwh DOUBLE PRECISION, voltage DOUBLE PRECISION, status TEXT`
Chunked by 1 day. Index on `(meter_id, timestamp DESC)`.

Also create a `feeder_head_readings` table with the same schema for feeder-head SCADA data.
Also create an `escalation_log` table: `meter_id, timestamp, weighted_score, agents_firing, outcome`.
Also create an `agent_weights_log` table: `timestamp, agent_name, old_weight, new_weight, reason`.

### STEP 2: generate_data.py
Read `GRIDSIGHT_BUILD_PROMPT.md` Task 1.2 for the full spec.

**CRITICAL ADDITION from SUGGESTIONS.md S1 — implement this or Agent 5 will not work:**
For every feeder, after generating all consumer meter readings, compute and save:
```python
feeder_head_kwh = sum(consumer_meter_readings_on_feeder) * 1.03 + gaussian_noise(sigma=0.005)
```
Save to `data/feeder_head_readings/feeder_{id}_head.csv`.

**Theft injection (10 meters, starting after day 45):**
- 3 meters: Bypass — sudden 70–85% drop
- 2 meters: Flatline — readings frozen at last value
- 2 meters: Night-zero/day-normal — zero 22:00–06:00, normal otherwise
- 2 meters: Periodic dip — drops 80% for 2 days every 15 days
- 1 meter: Gradual decline — drops 5% per week for 6 weeks

Save ground truth to `data/theft_ground_truth.csv`.

**ADDITION from SUGGESTIONS.md S2 — Add voltage data:**
In the same CSV, generate voltage readings:
- Normal meters: voltage ~ 230V ± 5V (Gaussian noise)
- Theft meters (bypass type): voltage drops 8–15V below feeder average on theft days

### STEP 3: validate_and_load.py
Read `GRIDSIGHT_BUILD_PROMPT.md` Task 1.3. Use Great Expectations.
Impute gaps < 2h with peer-median. Load into TimescaleDB.

---

## WEEK 2 — DEMAND FORECASTING

### STEP 4: forecast_meters.py
Read `GRIDSIGHT_BUILD_PROMPT.md` Task 2.1.
Prophet per-meter with: daily + weekly seasonality, temperature regressor,
Bangalore holiday calendar (Diwali, Ugadi, Eid, Christmas, Republic Day, Independence Day,
Kannada Rajyotsava, Ganesh Chaturthi, Dasara).
Output: 96-step (24h) forecast with yhat, yhat_lower, yhat_upper.

**Add this note in docstring and README (SUGGESTIONS.md S5):**
"Production weather source: IMD Open Data (mausam.imd.gov.in) or Open-Meteo API
(api.open-meteo.com/v1/forecast?latitude=12.97&longitude=77.59&hourly=temperature_2m).
Resample hourly data to 15-min via linear interpolation. This is the only external
data dependency. No consumer data leaves the BESCOM environment."

### STEP 5: forecast_zone.py
Read `GRIDSIGHT_BUILD_PROMPT.md` Task 2.2.
TFT zone-level aggregation. P10/P50/P90 quantile outputs.

### STEP 6: risk_zone.py
Read `GRIDSIGHT_BUILD_PROMPT.md` Task 2.3.
Import thresholds from config.py — do NOT hardcode 0.70, 0.85, 0.95.

### STEP 7: dashboard_demand.py
Read `GRIDSIGHT_BUILD_PROMPT.md` Task 2.4.
Streamlit + Folium map of Bangalore. Colour-coded transformer nodes.
Click a node → 24h forecast curve + P10/P50/P90 bands + top 3 drivers + plain-language recommendation.

---

## WEEK 3 — ANOMALY & THEFT DETECTION

### STEP 8: agent_cusum.py
Read `GRIDSIGHT_BUILD_PROMPT.md` Task 3.1. CUSUM break detector.
Returns score 0–100 and date of first detected break.

### STEP 9: agent_peer.py
Read `GRIDSIGHT_BUILD_PROMPT.md` Task 3.2. KNN peer comparator (k=20).
Social twins by type + sub-area + historical profile. 3σ threshold.

### STEP 10: agent_rules.py
Read `GRIDSIGHT_BUILD_PROMPT.md` Task 3.3.

**ADDITION from SUGGESTIONS.md S2 — Add voltage anomaly rule:**
```python
# Voltage anomaly rule
meter_avg_voltage = mean(meter voltage last 30 days)
feeder_avg_voltage = mean(feeder voltage last 30 days)
if abs(meter_avg_voltage - feeder_avg_voltage) > 0.08 * feeder_avg_voltage:
    if days_exceeding_threshold > 5 AND consumption_trend == "declining":
        rule_scores.append(65)
```
Return the maximum score across all triggered rules.

### STEP 11: agent_patterns.py
Read `GRIDSIGHT_BUILD_PROMPT.md` Task 3.4.
Perfectly flat line, night-zero/day-normal, periodic dips, drop aligned with service date.

### STEP 12: agent_feeder_balance.py
Read `GRIDSIGHT_BUILD_PROMPT.md` Task 3.5.
Reads from `data/feeder_head_readings/` (synthetic SCADA data created in Step 2).
Uses config.py values for NORMAL_TECHNICAL_LOSS_PCT and FEEDER_GAP_ALERT_THRESHOLD.
Uses FESTIVAL_DAY_TOLERANCE on known festival days.

### STEP 13: agent_isolation_forest.py (Optional — implement after core agents)
Trains Isolation Forest on full 96-feature daily profile (one feature per 15-min slot).
Trained on first 60 days. Disabled by default (weight = 0.0 in config.py).
Returns anomaly score 0–100 via decision_function normalisation.
Enabled via dashboard sidebar toggle which updates config.AGENT_WEIGHTS["isolation_forest"] = 1.0.

### STEP 14: fusion_engine.py
Read `GRIDSIGHT_BUILD_PROMPT.md` Task 3.6.
Import all agent modules. Import thresholds from config.py.
Escalation logic:
  IF agents_firing >= MIN_AGENTS_FIRING
  AND weighted_score >= ESCALATION_SCORE_THRESHOLD
  AND persistence >= PERSISTENCE_DAYS
  THEN "ESCALATE"
  ELSE "MONITOR"

Store result in escalation_log table.

### STEP 15: generate_case_file.py
Read `GRIDSIGHT_BUILD_PROMPT.md` Task 3.7.
ReportLab PDF with 5 sections:
1. Meter information
2. Consumption graph (matplotlib: target meter vs peer-group median, 90 days)
3. Agent evidence table (which agents fired, on what dates, what they observed)
4. Prioritised field checklist (ordered by agent score, highest first)
5. Composite score + confidence level + which thresholds were crossed

### STEP 16: field_app.py
Read `GRIDSIGHT_BUILD_PROMPT.md` Task 3.8.
Minimal Streamlit, mobile-optimised (375px portrait). Inspector view.
Shows assigned case files. Inspector checks items, submits outcome.
Outcome triggers update_weights.py.

---

## WEEK 4 — INTEGRATION, DEMO MODE & POLISH

### STEP 17: app.py (Unified Dashboard)
Read `GRIDSIGHT_BUILD_PROMPT.md` Task 4.1.
Two tabs: "Demand Forecast" + "Theft Detection."

**CRITICAL ADDITION from SUGGESTIONS.md S3 — Demo Mode:**
Add a "Demo Mode" toggle in the sidebar. When activated:
- Loads the vacation scenario: one meter whose consumption dropped while peer group also dropped.
- Runs agents one by one with 1-second animated delay between each.
- Each agent result appears on screen (green = not firing, red = firing).
- Score counter animates from 0 up to 18/100.
- A red threshold line is visible at 75/100.
- Final banner: "NO ESCALATION — Normal variability detected. 1/5 agents flagged. Required: 3/5."
- This must be visually clear. Use Streamlit's st.progress, st.metric, and st.success/st.warning.

Also add to the sidebar:
- "Enable Agent 6 — Isolation Forest" toggle (enables the optional sixth agent)
- Date picker for forecast date
- Feeder filter dropdown

### STEP 18: update_weights.py
Read `GRIDSIGHT_BUILD_PROMPT.md` Task 4.2.
Confirmed theft: +0.1 to firing agents' weights.
Clean case: -0.05 to firing agents' weights.
Normalise so sum of weights stays constant.
Log every change to agent_weights_log table.

### STEP 19: evaluate.py
Read `GRIDSIGHT_BUILD_PROMPT.md` Task 4.3.
Output:
- Recall: what % of 10 injected thefts were escalated (target: 100%)
- Precision: what % of escalated meters are actual theft (target: >90%)
- Time-to-detection: average days from injection to escalation flag (target: <5 days)
- MAPE for demand forecasting vs naive baseline and historical average baseline
- P10/P90 calibration: what % of actuals fall within the band (target: 90%)
Save as evaluation_report.json and evaluation_report.md.

### STEP 20: DECISIONS.md
Write this file. Read `SUGGESTIONS.md` S6 for the full template.
Must include at minimum:
- ADR-001: Why CUSUM over STL Decomposition
- ADR-002: Why 7-day persistence threshold
- ADR-003: Why 75/100 composite score threshold
- ADR-004: Why Prophet for per-meter, TFT for zone-level
- ADR-005: Why TimescaleDB over InfluxDB or flat files
Add any other decisions you made during the build.

### STEP 21: Tests
Write `tests/test_agent_consensus.py`:
- Generate 100 random score combinations.
- Assert that no combination with < MIN_AGENTS_FIRING firing agents returns "ESCALATE".
- Assert that no combination below ESCALATION_SCORE_THRESHOLD returns "ESCALATE".

Write `tests/test_false_positive_filter.py`:
- Creates the vacation scenario (consumption drop, peer group also drops, only 1 agent fires).
- Asserts the fusion engine returns "MONITOR", not "ESCALATE".
- Prints which agent fired and the final score.

### STEP 22: demo.sh
One-command launcher. Read `GRIDSIGHT_BUILD_PROMPT.md` Task 4.4.
Starts TimescaleDB, runs full pipeline, trains models, launches Streamlit at localhost:8501.
Print "GridSight is running at http://localhost:8501" when ready.

### STEP 23: README.md
Include:
- System architecture diagram (ASCII art — use the one from GRIDSIGHT_FULL_PLAN.md Section 3)
- Setup instructions (step by step, no assumptions)
- How to run the demo
- Evaluation results (fill in after running evaluate.py)
- Weather data production note (IMD / Open-Meteo — from SUGGESTIONS.md S5)

---

## CODING STANDARDS — APPLY TO EVERY SINGLE FILE

Every function you write must have:
1. **Type hints** on all parameters and return values
2. **Docstring** with: what it does, inputs, outputs, example usage
3. **Logging** at INFO level for all important steps using Python's `logging` module with timestamps
4. **Exception handling** — no bare `except:` clauses ever. Catch specific exceptions.
5. **Import from config.py** — never hardcode any threshold, weight, or parameter

Example of what every function should look like:
```python
import logging
from config import ESCALATION_SCORE_THRESHOLD, MIN_AGENTS_FIRING

logger = logging.getLogger(__name__)

def evaluate_meter(meter_id: str) -> dict:
    """
    Runs all anomaly detection agents on a meter and returns escalation decision.

    Args:
        meter_id: Unique meter identifier (e.g., "meter_042")

    Returns:
        dict with keys: decision ("ESCALATE"/"MONITOR"), weighted_score (float),
                        agents_firing (int), agent_scores (dict)

    Example:
        result = evaluate_meter("meter_042")
        # {"decision": "ESCALATE", "weighted_score": 84.2, "agents_firing": 4, ...}
    """
    logger.info(f"[{meter_id}] Starting fusion evaluation at {datetime.now().isoformat()}")
    try:
        # ... implementation
    except ValueError as e:
        logger.error(f"[{meter_id}] Invalid data: {e}")
        raise
```

---

## EDGE CASES — HANDLE ALL OF THESE, DO NOT SKIP

1. **Meter offline > 2h:** Exclude from anomaly scoring entirely. Show "OFFLINE" badge on dashboard.
2. **Festival days (Diwali, etc.):** Feeder Balance Agent uses FESTIVAL_DAY_TOLERANCE (10%) instead of FEEDER_GAP_ALERT_THRESHOLD (5%).
3. **New meter < 60 days history:** Use available history only. Flag as "INSUFFICIENT BASELINE" if < NEW_METER_MIN_DAYS (30) days.
4. **Transformer RED for 3+ consecutive days:** Auto-escalate the risk zone annotation with "PERSISTENT OVERLOAD RISK" label.
5. **Negative kWh readings:** Route to a separate `meter_faults` table. Never score as theft. Show "METER FAULT" on dashboard.
6. **Voltage data missing:** Agent 3 voltage rule should gracefully skip with a log warning, not crash.
7. **Feeder head data missing:** Agent 5 should skip scoring for that feeder and log a warning.

---

## DEMO SCRIPT — HOW THE FINAL DEMO SHOULD RUN (Practice this)

1. Open `http://localhost:8501`
2. Tab 1 "Demand Forecast":
   - Show colour-coded Bangalore map
   - Click an ORANGE transformer node
   - Show the 24h forecast with P10/P50/P90 bands
   - Read out the plain-language recommendation
3. Tab 2 "Theft Detection":
   - Show the table of flagged meters with composite scores
   - Click "Download Case File" for the highest-scored meter
   - Open the PDF — show the evidence table and field checklist
4. Sidebar → Enable "Demo Mode":
   - Run the vacation false-positive scenario
   - Watch agents fire one by one
   - Final score: 18/100 — NO ESCALATION
   - Say: "This is what the system correctly does NOT do."
5. Run `python evaluate.py` live:
   - Recall: 100% — all 10 injected thefts caught
   - Precision: >90%
   - MAPE improvement: show the number vs baseline

---

## FINAL ACCEPTANCE CHECKLIST (All must pass before submission)

- [ ] `demo.sh` runs without errors and opens dashboard at localhost:8501
- [ ] Dashboard shows colour-coded Bangalore map with GREEN/YELLOW/ORANGE/RED nodes
- [ ] Dashboard shows theft detection table with composite scores
- [ ] "Download Case File" generates a valid, readable PDF
- [ ] Demo Mode runs the vacation scenario and shows NO ESCALATION correctly
- [ ] `python evaluate.py` prints Recall >= 100%, Precision >= 90%
- [ ] `python -m pytest tests/` — all tests pass
- [ ] `DECISIONS.md` exists and has at least 5 ADRs
- [ ] `README.md` is complete with setup instructions and eval results
- [ ] `config.py` exists and all files import from it (no hardcoded thresholds)
- [ ] Feeder head synthetic data exists in `data/feeder_head_readings/`
- [ ] Voltage data is included in meter readings and used by Agent 3
- [ ] Weather data source is documented in README and forecast_meters.py

---

## REFERENCE DOCUMENT SUMMARY

| File | What It Contains | When to Read It |
|------|-----------------|-----------------|
| GRIDSIGHT_FULL_PLAN.md | Full strategy, architecture diagrams, evaluation targets, scenario walk-through, why each technology was chosen | Before writing architecture. Before writing README. When a judge asks "why did you build it this way?" |
| GRIDSIGHT_BUILD_PROMPT.md | Week-by-week tasks, exact function signatures, parameters, edge cases, deliverables checklist | While coding each component. Cross-check every function against the spec. |
| SUGGESTIONS.md | 7 improvements with priority ratings. S1 and S7 are CRITICAL — implement before anything else. | Before writing a single line of code. Then again during Week 4 polish. |

---

## YOU ARE READY TO BUILD. START WITH config.py. THEN setup_db.py. THEN generate_data.py.
## DO NOT SKIP THE SUGGESTIONS. THE CRITICAL ONES BREAK THE SYSTEM IF MISSING.