# GridSight Prototype — Complete Build Prompt for AI Coding Assistant

## Role & Context

You are a senior ML engineer and full‑stack Python developer building a hackathon prototype called **GridSight** — an AI‑powered decision‑support system for BESCOM (Bangalore Electricity Supply Company) that ingests smart‑meter data and delivers two capabilities:

1. **Demand Forecasting & Risk Zoning** (Part A)
2. **Anomaly & Theft Detection** (Part B)

The system must be *read‑only*, *explainable*, and run entirely locally (no cloud APIs, no hosted LLMs). You are building a working prototype in 4 weeks that runs on a single laptop.

---

## Environment & Prerequisites

### Required Software (install once)
- Python 3.10+
- PostgreSQL 15+ with TimescaleDB extension
- VS Code or any editor

### Python Packages
```bash
pip install pandas numpy prophet streamlit folium streamlit-folium \
  scikit-learn statsmodels reportlab faker psycopg2-binary \
  great-expectations pytorch-forecasting torch matplotlib plotly
```

---

## Week 1 — Data Foundation

### Task 1.1: Set Up TimescaleDB

Write a script `setup_db.py` that:
- Connects to a local PostgreSQL instance.
- Creates a database called `gridsight`.
- Creates a hypertable `meter_readings` with columns: `meter_id TEXT, timestamp TIMESTAMPTZ, kwh DOUBLE PRECISION, voltage DOUBLE PRECISION, status TEXT`.
- Converts it to a TimescaleDB hypertable chunked by 1 day.
- Creates indexes on `(meter_id, timestamp DESC)`.

### Task 1.2: Build Synthetic Data Generator

Write `generate_data.py` that:

**Parameters (configurable):**
- `NUM_METERS = 200`
- `DAYS = 90`
- `FREQ = "15min"`
- `THEFT_METERS = 10` (meters where we inject theft)
- `FEEDER_MAPPING = {"Feeder_1": [...meter_ids...], ...}`
- `TRANSFORMER_CAPACITY_KW = {"DT_1": 500, ...}`

**Normal consumption logic:**
For each meter, generate a realistic 15‑minute load profile that:
- Has a daily sinusoidal pattern peaking at 18:00–20:00 (evening peak) and dipping at 03:00–05:00.
- Has weekly seasonality: weekdays higher than weekends.
- Includes random noise (σ ≈ 5–10 % of base load).
- Adds temperature sensitivity: when temperature > 35 °C, consumption increases by 15–25 %.
- Varies by meter type (residential: 0.3–2.0 kWh/15 min; commercial: 1.0–5.0 kWh/15 min).

**Theft injection (for 10 meters, starting after day 45):**
- 3 meters: **Bypass** — sudden 70–85 % drop (multiply by 0.15–0.30).
- 2 meters: **Flatline (firmware tamper)** — readings frozen at last value.
- 2 meters: **Night‑zero/day‑normal** — zero between 22:00–06:00, normal otherwise.
- 2 meters: **Periodic dip** — consumption drops 80 % for 2 days every 15 days (aligned with meter‑reading visits).
- 1 meter: **Gradual decline** — consumption drops 5 % per week for 6 weeks.

**Outputs:**
- CSV file per meter: `data/meter_readings/meter_{id}.csv` with columns `timestamp, kwh`.
- Feeder metadata CSV: `data/feeder_metadata.csv`.
- Weather data CSV: `data/weather.csv` with columns `timestamp, temperature_c, humidity_pct`.
- Ground‑truth file: `data/theft_ground_truth.csv` with columns `meter_id, theft_type, injection_date`.

### Task 1.3: Data Validation Pipeline

Write `validate_and_load.py` that:
- Uses Great Expectations to validate all CSVs (no negative kWh, no future timestamps, no gaps > 2 h without flag).
- Imputes gaps < 2 h with peer‑median value for that 15‑minute slot.
- Loads all validated data into TimescaleDB.

---

## Week 2 — Demand Forecasting (Part A)

### Task 2.1: Prophet Per‑Meter Model

Write `forecast_meters.py` with a function `train_and_forecast(meter_id)` that:
- Loads that meter's 90‑day history from TimescaleDB.
- Trains a Facebook Prophet model with: `daily_seasonality=True`, `weekly_seasonality=True`, `yearly_seasonality=False`.
- Adds temperature as an external regressor.
- Adds Bangalore holiday calendar (Diwali, Ugadi, Eid, Christmas, Republic Day, Independence Day, etc.).
- Forecasts the next 24 h (96 steps).
- Returns a DataFrame with columns: `ds, yhat, yhat_lower, yhat_upper`.
- Saves the trained model to `models/prophet/meter_{id}.pkl`.

### Task 2.2: TFT Zone‑Level Aggregation

Write `forecast_zone.py` that:
- Aggregates per‑meter forecasts to feeder/Distribution Transformer (DT) level.
- Prepares a multivariate time‑series dataset: aggregated demand, temperature, hour‑of‑day, day‑of‑week, is_holiday, is_weekend.
- Trains a Temporal Fusion Transformer (via `pytorch_forecasting`) with:
  - `max_prediction_length = 96` (24 h at 15‑min intervals).
  - `max_encoder_length = 192` (48 h of history).
  - Outputs P10/P50/P90 quantiles.
- Saves the trained TFT model.

### Task 2.3: Risk Zone Classifier

Write `risk_zone.py` with a function `classify_risk(predicted_peak_kw, rated_capacity_kw)`:
```python
ratio = predicted_peak_kw / rated_capacity_kw
if ratio < 0.70: return "GREEN"
elif ratio < 0.85: return "YELLOW"
elif ratio < 0.95: return "ORANGE"
else: return "RED"
```

### Task 2.4: Streamlit Demand Dashboard

Write `dashboard_demand.py` using Streamlit + Folium that:
- Shows a map of Bangalore (centre: 12.9716, 77.5946, zoom=12).
- Each DT plotted as a circle marker coloured by risk zone.
- Clicking a marker shows: DT ID, tomorrow's forecast curve with P10/P50/P90 bands, top 3 drivers, plain‑language recommendation.
- Includes a sidebar with date picker and feeder filter.

---

## Week 3 — Anomaly & Theft Detection (Part B)

### Task 3.1: Agent 1 — CUSUM Break Detector

Write `agent_cusum.py` with a function `cusum_score(meter_id, days_lookback=90)` that:
- Loads the meter's history.
- Computes the running mean over the first 60 days as baseline.
- Computes the cumulative sum of deviations from baseline over the last 30 days.
- Applies a CUSUM control chart (h=5, k=0.5 parameters).
- Returns a score 0–100: higher for more significant, sustained downward breaks.
- Returns the date the break was first detected.

### Task 3.2: Agent 2 — KNN Peer Comparator

Write `agent_peer.py` with a function `peer_score(meter_id)` that:
- Groups all meters by type (residential/commercial) and feeder.
- For each meter, computes daily average kWh for the last 30 days.
- Uses K‑Nearest Neighbours (k=20) to find "social twins" based on historical usage patterns over the first 60 days.
- If the target meter's recent average is > 3 standard deviations below the peer group's recent average, flags it.
- Returns a score 0–100 proportional to the deviation.

### Task 3.3: Agent 3 — Impossibility Rule Engine

Write `agent_rules.py` with a function `rule_score(meter_id)` that checks:
- **Zero‑consumption rule:** If the meter shows < 0.1 kWh/day for ≥ 7 consecutive days despite being a "permanently occupied" residential meter → score 80.
- **Standby minimum rule:** If daily consumption is below 0.24 kWh (1 W standby × 24 h) → score 50.
- **Tariff mismatch:** If a commercial meter shows purely residential hours (peaks at 6–9 AM, 6–10 PM, zero during business hours) → score 60.
- Returns the maximum score across all triggered rules (0 if none triggered).

### Task 3.4: Agent 4 — Pattern Matcher

Write `agent_patterns.py` with a function `pattern_score(meter_id)` that scans for:
- **Perfectly flat line:** Variance of daily kWh over last 30 days < 0.001 → score 90.
- **Night‑zero/day‑normal:** Consumption between 22:00–06:00 is < 5 % of daytime average → score 70.
- **Periodic dips:** Dips of > 60 % occurring at regular intervals (every 15, 30, or 60 days) → score 60.
- **Sudden drop aligned with service date:** If a meter replacement or complaint date exists in metadata and a drop occurs within ±2 days → score 85.
- Returns the maximum score across all matched patterns.

### Task 3.5: Agent 5 — Feeder Balance Auditor

Write `agent_feeder_balance.py` with a function `feeder_gap_score(feeder_id)` that:
- Sums all consumer meter readings on that feeder for the last 7 days.
- Compares against the SCADA feeder‑head meter total energy.
- Computes the percentage gap.
- If gap > 5–8 % consistently (after subtracting known technical losses of ~3 %), scores each meter on that feeder proportionally to the gap.
- Returns a score 0–100 for each meter.

### Task 3.6: Score Fusion & Escalation Engine

Write `fusion_engine.py` with a function `evaluate_meter(meter_id)` that:
- Calls all 5 agents and collects scores.
- Computes calibrated $P(\text{theft})$ using context-aware probabilistic fusion.
- Adjusts probability using physics confidence and temporal persistence.
- Returns:
  - `"ESCALATE"` if adaptive threshold is met or expected value is high.
  - `"MONITOR"` otherwise.
- Stores the result in `escalation_log` table, including confidence interval and uncertainty.

### Task 3.6b: Context + Temporal Intelligence

Write `context_features.py` and `temporal_intelligence.py` that:
- Extract time-of-day, load level, and feeder type context.
- Track persistence and trend slope for each meter using recent fusion history.

### Task 3.6c: Feedback Learning Loop

Write `feedback_learning.py` that:
- Records inspection outcomes.
- Updates agent reliability scores.
- Updates adaptive thresholds for fusion and classification.

### Task 3.7: Inspection Case File Generator

Write `generate_case_file.py` that, for each escalated meter:
- Queries meter metadata, 90‑day consumption history, peer‑group median, agent firing details.
- Uses `matplotlib` to generate a side‑by‑side consumption plot.
- Uses ReportLab to build a PDF with:
  - Title: "GridSight Inspection Case File — Meter [ID]"
  - Section 1: Meter information.
  - Section 2: Consumption graph.
  - Section 3: Agent evidence table.
  - Section 4: Prioritised field checklist.
  - Section 5: Calibrated $P(\text{theft})$, confidence interval, and reasoning chain.
- Saves PDF to `case_files/meter_{id}_{date}.pdf`.

### Task 3.8: Mobile Web View

Write `field_app.py` as a minimal Streamlit page optimised for mobile (portrait 375 px):
- Shows a list of assigned case files for the logged‑in inspector.
- Clicking a case file shows the PDF and a checklist.
- Inspector can check off each item and submit outcome.
- Submission triggers weight update.

---

## Week 4 — Integration, Evaluation & Polish

### Task 4.1: Unified Dashboard

Write `app.py` (main Streamlit entry point) with two tabs:
- **Tab 1 "Demand Forecast"** — the risk map from Task 2.4.
- **Tab 2 "Theft Detection"** — a table of escalated meters with: meter ID, $P(\text{theft})$, expected value, ROI, urgency, confidence interval, "Download Case File" button, "Mark Outcome" dropdown.

### Task 4.2: Feedback Loop

Write `update_weights.py` that:
- Reads field inspection outcomes.
- For confirmed theft: increases weights of firing agents by +0.1 for that segment.
- For clean cases: decreases weights of firing agents by −0.05.
- Normalises weights to keep sum constant.
- Logs all weight changes to audit table.
- Also updates agent reliability and adaptive thresholds.

### Task 4.3: Evaluation Script

Write `evaluate.py` that:
- Loads theft ground truth.
- Checks which injected thefts were escalated (recall) and on what date (time‑to‑detection).
- Counts non‑theft meters that were escalated (false positives → precision).
- For forecasting, computes MAPE, RMSE, and P10/P90 calibration.
- Outputs a summary report: `evaluation_report.json` and `evaluation_report.md`.

### Task 4.4: Demo Script & Documentation

Write a `demo.sh` script that launches everything:
- Starts TimescaleDB.
- Runs the full data generation & load pipeline.
- Trains all models.
- Starts the Streamlit dashboard.
- Prints the dashboard URL.

Write `README.md` with:
- System architecture diagram (ASCII art).
- Setup instructions.
- How to run the demo.
- Evaluation results.

---

## Non‑Functional Requirements

### Every function must:
- Use type hints.
- Include a docstring describing inputs, outputs, and purpose.
- Log timestamped messages at INFO level for important steps.
- Handle exceptions gracefully (no bare excepts).

### Data privacy:
- No real consumer data should be used.
- All data generation must use Faker for names/addresses.
- The synthetic data generator must be clearly documented as producing synthetic data.

### Testing:
- Write a `test_agent_consensus.py` that verifies no meter is escalated with < 3 agents firing.
- Write `test_false_positive_filter.py` that walks through the "vacation scenario" described in the plan.

---

## Critical Edge Cases to Handle

1. **Meter offline for > 2 h:** Exclude from anomaly scoring; mark as "offline" on dashboard.
2. **Festival day (Diwali):** Feeder Balance Agent uses ±10 % tolerance instead of ±5 %.
3. **New meter (< 60 days of history):** Use only available history; flag as "insufficient data for baseline" if < 30 days.
4. **Transformer near capacity for consecutive days:** Escalate risk zone from ORANGE to RED if 3+ consecutive days predicted.
5. **Negative consumption readings:** Flag as "meter fault," not theft; route to maintenance queue.

---

## Deliverables Checklist

- [ ] `setup_db.py` — TimescaleDB hypertable setup.
- [ ] `generate_data.py` — Synthetic 200‑meter dataset with injected theft.
- [ ] `validate_and_load.py` — Data validation and DB loading.
- [ ] `forecast_meters.py` — Prophet per‑meter forecasting.
- [ ] `forecast_zone.py` — TFT zone‑level aggregation.
- [ ] `risk_zone.py` — Risk zone classifier.
- [ ] `dashboard_demand.py` — Streamlit map dashboard.
- [ ] `agent_cusum.py` — CUSUM break detector.
- [ ] `agent_peer.py` — KNN peer comparator.
- [ ] `agent_rules.py` — Impossibility rule engine.
- [ ] `agent_patterns.py` — Pattern matcher.
- [ ] `agent_feeder_balance.py` — Feeder balance auditor.
- [ ] `data_utils.py` — Data quality, smoothing, and robustness utilities.
- [ ] `residual_intelligence.py` — Forecast residual analysis and pattern labeling.
- [ ] `context_features.py` — Time-of-day, load regime, and feeder context.
- [ ] `temporal_intelligence.py` — Persistence and trend tracking.
- [ ] `probabilistic_fusion.py` — Adaptive probabilistic fusion.
- [ ] `physics_engine.py` — Energy balance and physics confidence.
- [ ] `economic_impact.py` — Expected value and ROI model.
- [ ] `decision_engine.py` — Action, urgency, and scheduling.
- [ ] `explainability.py` — Reasoning chain and confidence intervals.
- [ ] `feedback_learning.py` — Inspection feedback and adaptive thresholds.
- [ ] `fusion_engine.py` — Score fusion & escalation logic.
- [ ] `generate_case_file.py` — PDF case file generator.
- [ ] `field_app.py` — Mobile web view for inspectors.
- [ ] `update_weights.py` — Feedback loop weight update.
- [ ] `evaluate.py` — Evaluation script.
- [ ] `app.py` — Unified Streamlit dashboard.
- [ ] `demo.sh` — One‑command demo launcher.
- [ ] `README.md` — Complete documentation.
- [ ] `test_agent_consensus.py` — Consensus gate test.
- [ ] `test_false_positive_filter.py` — Vacation FP filter test.
- [ ] `evaluation_report.md` — Final evaluation results.

---

## Final Acceptance Criteria

1. Running `demo.sh` opens a Streamlit dashboard at `http://localhost:8501`.
2. Dashboard shows a colour‑coded map of Bangalore with risk zones.
3. Dashboard shows a table of flagged meters with $P(\text{theft})$ and expected value.
4. Clicking "Download Case File" generates a valid PDF.
5. Running `evaluate.py` prints recall ≥ 100 % (all 10 injected thefts caught) and precision ≥ 90 %.
6. All tests pass.
7. README is complete and accurate.