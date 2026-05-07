# GridSight: End-to-End Build Guide — From Zero to a National-Level Hackathon Proof-of-Concept

## File 1: `GRIDSIGHT_FULL_PLAN.md` — Complete Strategy & Architecture

### 1. The Real-World Problem (Why This Matters to BESCOM)

Bangalore's electricity distribution is modernising fast. BESCOM started its urban smart‑meter rollout on 15 February 2025 and is now pushing coverage into rural areas. Those meters generate a 15‑minute kWh reading for every household and commercial connection, day and night. Yet today the data is used almost exclusively for billing. Two expensive blind spots remain:

| Blind Spot | What Actually Happens | Cost |
|------------|----------------------|------|
| **A – No early warning for demand spikes** | On a 40 °C afternoon, feeders 7B in Rajajinagar hits 92 % capacity at 18:30 with no prior alert. Transformers trip, cables overheat, and outages cascade. | Customer outages, equipment damage, overtime crew costs. |
| **B – Revenue leakage through theft & tampering** | India's AT&C losses average 20‑25 %. Bypass wiring, magnet‑based slowing, firmware tampering, and direct tapping from LT lines cost crores every year. Inspections are random; yield is poor. | Revenue loss, unfair tariffs for honest consumers. |

**Why both problems must be solved together:** A demand spike masks theft — when genuine consumption rises, a thief's artificially flat reading looks less suspicious. A unified data layer lets each engine cross‑validate the other; a suspicious meter in a high‑load zone gets a higher composite risk score.

### 2. GridSight's Core Promise (What the Prototype Will Prove)

1. **Predict localized demand 1–24 h ahead** with interpretable uncertainty bands.
2. **Colour‑code every distribution transformer by peak‑load risk.**
3. **Flag probable theft/tampering with adaptive probabilistic fusion — never on a single signal.**
4. **Generate a human‑readable, mobile‑ready Inspection Case File** that a field supervisor can act on with zero technical background.
5. **Prioritise using Expected Value** ($P(\text{theft}) \times \text{loss}$) and ROI-aware scheduling.
6. **Continuously improve with inspection feedback** (agent reliability + adaptive thresholds).
7. **Do all of the above as a read‑only decision‑support layer** — no writes to any BESCOM system, no hosted LLM, no external data leak.

### 3. Architecture at a Glance (Three Layers)

```
┌─────────────────────────────────────────────────────────┐
│                   OUTPUT LAYER                           │
│  Streamlit Dashboard (Map + Flagged‑Meter Table + Case   │
│  File PDF)   │   Mobile web view for field inspectors    │
└─────────────────────────────────────────────────────────┘
                          ▲
┌─────────────────────────────────────────────────────────┐
│               COMPUTE LAYER (Python)                     │
│  ┌────────────────────┐  ┌─────────────────────────────┐ │
│  │ Demand Engine      │  │ Anomaly Engine (5 Agents)   │ │
│  │ • Prophet per meter │  │ • CUSUM break detector      │ │
│  │ • TFT zone aggreg. │  │ • KNN peer comparator       │ │
│  │ • Risk-zone classif.│  │ • Rule engine               │ │
│  └────────────────────┘  │ • Pattern matcher           │ │
│                          │ • Feeder balance auditor    │ │
│                          └─────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────┐ │
│  │ Adaptive Fusion + Context                            │ │
│  │ • Residual intelligence • Temporal persistence        │ │
│  │ • Context features       • Physics confidence         │ │
│  └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
                          ▲
┌─────────────────────────────────────────────────────────┐
│               DATA LAYER                                 │
│  TimescaleDB (PostgreSQL hypertable)  │  File‑drop /     │
│  15‑min smart‑meter readings          │  read‑only API   │
└─────────────────────────────────────────────────────────┘
```

### 4. Detailed Component Design

#### 4.1 Data Ingestion (Week 1 Deliverable)

**Input format:** CSV or JSON files arriving every 15 min or as hourly batches.  
**Schema:** `meter_id, timestamp, kwh, voltage (optional), status_flags`.  
**Pipeline (Python + Pandas + Great Expectations):**

1. Validate schema and value ranges (e.g., kWh ≥ 0, no future timestamps).
2. Impute short gaps (< 2 h) with the **peer‑median value** for that 15‑minute slot.
3. Flag longer gaps in the dashboard ("meter offline").
4. Load into TimescaleDB hypertable, chunked by day.

> **Why TimescaleDB?** It is a PostgreSQL extension purpose‑built for time‑series. SQL‑native, so BESCOM DBAs need zero new skills. A single node handles 10 M rows/day comfortably.

#### 4.2 Demand Forecasting (Week 2 Deliverable)

**Stage 1 – Per‑meter baseline (Facebook Prophet)**

- Learns daily/weekly seasonality, holiday effects (Bangalore calendar), and weather sensitivity (temperature added as external regressor).
- Output: 96‑step (24 h) forecast with `yhat`, `yhat_lower`, `yhat_upper`.

**Stage 2 – Feeder/DT‑level aggregation (Temporal Fusion Transformer)**

- Aggregates per‑meter forecasts and refines with multivariate inputs: aggregated demand, temperature, time‑of‑day, day‑type, historical peaks.
- Output: **P10/P50/P90 probabilistic bands** — operators see uncertainty, not false precision.
- Learns feature importance per time step (weekday vs weekend, summer vs monsoon).

**Risk‑Zone Classification**

| Zone | Peak‑Load Ratio | Action |
|------|-----------------|--------|
| GREEN | < 70 % | Normal monitoring |
| YELLOW | 70–85 % | Increased watch |
| ORANGE | 85–95 % | Pre‑position crew |
| RED | > 95 % | Immediate load‑shed/transfer |

**Baselines for comparison:** Naïve persistence (tomorrow = today) and historical average (same hour, past 30 days).  
**Target:** ≥ 15 % MAPE improvement over the best baseline; < 2 % of transformers misclassified by more than one colour band.

#### 4.3 Theft Detection — The Five‑Agent Ensemble (Week 3 Deliverable)

**Design principle: "Conviction Requires Context."** No single signal ever triggers an inspection. A meter is escalated only when calibrated $P(\text{theft})$ is high **and** temporal persistence and physics confidence align.

| Agent | Technique | What It Detects |
|-------|-----------|-----------------|
| 1 – Break Detector | CUSUM (cumulative sum control chart) | Sudden, sustained downward break in consumption — signature of a newly installed bypass. |
| 2 – Peer Comparator | K‑Nearest Neighbours (15–20 "social twins" — same type, sub‑area, historical profile) | Target meter's consumption falls > 3σ below the peer band. Neutralises weather and seasonal effects. |
| 3 – Impossibility Checker | Rule engine | Occupied premise with near‑zero consumption for 7 days; reading below standby minimum; tariff‑category mismatch. |
| 4 – Pattern Matcher | Template signatures | Perfectly flat line (firmware/magnet tamper); night‑zero/day‑normal (bypass active only at night); periodic dips aligned with meter‑reading dates. |
| 5 – Feeder Balance Auditor | Energy balance: SCADA feeder‑head meter vs sum of all consumer meters on that feeder | Persistent > 5–8 % gap after technical losses → under‑reporting somewhere on the feeder. |

**Score Fusion:**

```
p_theft = sigmoid( Σ (agent_probᵢ × reliabilityᵢ × contextᵢ) + residual + physics + temporal )
adjusted_p = p_theft × physics_confidence

if adjusted_p ≥ threshold AND persistence is high:
    → ESCALATE (generate Inspection Case File)
else:
    → MONITOR
```

**Reliability and thresholds are updated via a feedback loop:** inspection outcomes update agent reliability and adaptive thresholds, keeping the system calibrated over time.

#### 4.4 Outputs — Explainable & Actionable

**Demand Dashboard (Streamlit + Folium):**
- Colour‑coded map of Bangalore with each transformer node coloured by tomorrow's risk zone.
- Click a node → 24‑h forecast curve with P10/P50/P90 bands, top 3 prediction drivers, plain‑language recommendation.

**Inspection Case File (auto‑generated PDF):**
1. Meter ID, location, consumer name (from billing), tariff category.
2. Side‑by‑side consumption graph: target meter (last 90 days) vs peer‑group median.
3. Table listing which agents fired, on what dates, and what each observed.
4. Prioritised field checklist (e.g., "1. Check meter seal — Agent 1 detected break on [date]. 2. Inspect LT connection point. 3. Check for bypass wiring.").
5. Calibrated $P(\text{theft})$, confidence interval, and reasoning chain.

**Mobile‑First Field Access:** Lightweight web view (no app install). Inspector checks off each item and submits outcome (clean / tampered / confirmed theft). This feedback immediately updates agent weights.

### 5. Technology Stack (With Justification)

| Component | Technology | Why |
|-----------|-----------|-----|
| Data storage | TimescaleDB (PostgreSQL extension) | Optimised for time‑series; SQL‑native; zero new skill required for BESCOM DBAs. |
| Data pipeline | Python + Pandas + Great Expectations | Standard stack; built‑in data‑quality validation before any model sees the data. |
| Per‑meter forecasting | Facebook Prophet | Interpretable; handles seasonality and holidays natively; fast to train per meter. |
| Zone‑level forecasting | PyTorch TFT (via pytorch‑forecasting) | State‑of‑art probabilistic accuracy; learns feature importance automatically. |
| Anomaly agents | scikit‑learn (KNN), statsmodels (CUSUM), custom rule engine | Lightweight; auditable; no GPU required; each agent independently testable. |
| Score fusion | Adaptive probabilistic fusion with context + physics confidence | Calibrated probability with explainable adjustments. |
| Dashboard | Streamlit + Folium | Browser‑based; no client install; map tiles work offline for internal networks. |
| Case file | Python ReportLab (PDF) | Standard, portable format usable on any device. |

### 6. Risk Mitigation Table

| Risk | Impact | Mitigation |
|------|--------|-----------|
| False theft accusation | Legal/reputational harm | Context-aware fusion + physics confidence + temporal persistence; human sign‑off before field visit. |
| Seasonal variation mistaken as anomaly | Elevated FPs in summer/monsoon | Peer comparator neutralises seasonal effects; all agents use seasonal decomposition; year‑on‑year comparison. |
| Data gaps / meter offline | Missing signal | Short gaps filled via peer‑median; longer gaps flagged; meter excluded from anomaly scoring until data resumes. |
| Thieves adapt to detection patterns | Sophisticated adversarial bypass | Modular agent design; new templates can be added; feeder‑balance audit catches any bypass that moves energy. |
| Forecasting accuracy degrades under novel conditions | Wrong risk‑zone classification | P10/P90 bands communicate uncertainty; human override always available; model retrained monthly. |
| Scalability bottleneck | Slow alerts as network grows | Batch agent processing; stateless containers; horizontal scaling; TimescaleDB handles 10 M+ rows/day. |

### 7. Evaluation Framework

**Demand Forecasting:**

| Metric | Naïve Baseline | GridSight Target |
|--------|---------------|------------------|
| MAPE (day‑ahead) | ~18 % | < 8 % |
| Risk‑zone accuracy | N/A | > 98 % correct band |
| P10/P90 calibration | N/A | 90 % of actuals within band |

**Theft Detection (on synthetic data with injected anomalies):**

| Metric | Target |
|--------|--------|
| Recall (injected thefts caught) | **100 %** (zero missed theft) |
| Precision (flags that are correct) | > 90 % (< 10 % false positives) |
| Time‑to‑detection (injection to flag) | < 5 days average |
| False‑positive filter example | Walk‑through showing a genuine vacation‑driven drop correctly *not* escalated. |

### 8. Sample Scenario Walk‑Through (Key for Judges)

> *"A cluster of 40 meters in Indiranagar shows sharp evening peaks consistently above 90 % of transformer capacity at 18:30–20:00. Simultaneously, Meter ID 4471 shows a 70 % drop in consumption over 9 days while neighbouring meters show normal or rising usage."*

**GridSight's response:**

- **Demand Engine** flags Feeder 12‑C as **ORANGE** at 16:00 the previous day. Plain‑language alert: *"Predicted peak 87 % capacity at 18:45. Primary driver: working weekday + 37 °C forecast. Recommended: activate standby transformer T‑12‑C2."*
- **For Meter 4471:** Agents 1 (CUSUM break detected day 3), 2 (3.4σ below 18 peer meters), and 3 (zero‑day rule triggered day 8) all fire. Calibrated $P(\text{theft}) = 0.82$ with high physics confidence and 9‑day persistence. An Inspection Case File is auto‑generated and assigned to field supervisor.

### 9. Four‑Week Implementation Roadmap

| Week | Focus | Deliverables |
|------|-------|-------------|
| **1 – Data Foundation** | Synthetic data generator (200 meters, realistic profiles, injected anomalies, weather co‑variates); data pipeline; TimescaleDB schema; data‑quality validation. | Working synthetic data generator script; loaded TimescaleDB hypertable. |
| **2 – Demand Forecasting** | Prophet per‑meter model; TFT zone aggregation; P10/P50/P90 output; risk‑zone classifier; basic Streamlit map dashboard. | Live Streamlit map with GREEN/YELLOW/ORANGE/RED transformer nodes. |
| **3 – Theft Detection** | All 5 anomaly agents; scoring fusion; escalation logic; Case File generator; mobile‑responsive web view. | Auto‑generated PDF Case File for each escalated meter. |
| **4 – Integration & Evaluation** | Unified dashboard; feedback loop; full evaluation run against synthetic ground truth; documentation; demo video. | Polished prototype ready for hackathon judging. |

### 10. Public Datasets You Can Use Today

1. **1000‑Household 15‑min Dataset (Slovakia)** — Mendeley Data, DOI: `10.17632/pns69yxgrp.2`. 15‑minute active/reactive energy for 1000 anonymized households, mix of rural/urban, full year 2016.  
2. **Electricity Consumption Dataset (Portugal, 172 Buildings)** — Mendeley Data, DOI: `10.17632/vryvyfz2tj.1`. 15‑minute intervals, 172 buildings, includes weather data, May 2022–Sep 2023.  
3. **Electricity Demand Dataset (Hugging Face)** — `EDS-lab/electricity-demand`. Harmonised compilation of multiple open smart‑meter datasets, includes weather and metadata. Ready for demand forecasting.  
4. **Saudi Electricity Data (Kaggle)** — 15‑minute readings, multiple meters, ideal for testing peer‑comparison logic.  
5. **LADPU Smart Meter Data (Los Alamos, USA)** — 1,757 households, Landis+Gyr meters, full‑year.  
6. **Faraday Synthetic Generator (OpenSynth/LF Energy)** — VAE‑based model trained on 300 M+ UK smart‑meter readings. Can generate realistic synthetic profiles conditioned on property type and low‑carbon technology ownership.  
7. **OpenSynth 10 M Synthetic Load Profiles** — Trained on Octopus Energy customer data, ideal if you need large‑scale synthetic data.

> **For the prototype:** The fastest path is to write your own synthetic data generator (see File 2) that produces exactly the data shape your models expect. This gives you ground truth for evaluating theft detection recall. You can use the public datasets above for additional realism and model benchmarking.

### 11. Non‑Negotiables Check

| Constraint | GridSight Compliance |
|-----------|---------------------|
| No modification to existing systems | Read‑only file drops or API endpoints; zero write access. |
| Works as decision‑support layer | All outputs are advisories; no auto‑disconnects; human decision required. |
| Masked/synthetic data | Configurable synthetic data generator with injected anomalies. |
| Explainable & auditable outputs | Every alert includes full evidence file; every model decision logged with inputs, model version, outputs. |
| False positives minimised | Context-aware fusion + physics confidence + temporal persistence + feedback loop. |
| No hosted LLM on sensitive data | All models are classical ML / time‑series algorithms running locally; zero raw data leaves the BESCOM compute environment. Only external dependency: aggregated area‑level weather forecast. |

### 12. What Wins Hackathons — Extra Polish Points

1. **Walk through a false‑positive that the system correctly filters out** — e.g., a family on vacation during school holidays where the peer group also drops — only 1 of 5 agents fires, score 18/100, no escalation. Judges want to see edge‑case thinking.
2. **Show the human‑readable Case File PDF** — the field checklist makes it real for a BESCOM lineman.
3. **Live dashboard with actual 15‑minute data flowing** — colour‑coded map, clickable transformer nodes, a table of flagged meters.
4. **Quantify everything** — "Our MAPE is 7.2 %, the baseline is 18.4 %, that's a 61 % improvement."
5. **Have the BESCOM context ready** — smart‑meter rollout started 15 Feb 2025; KERC guidelines issued 6 Mar 2024. Shows domain awareness.