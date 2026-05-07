# GridSight — Suggestions & Improvement Log
## Authored by: Architecture Review (Pre-Build)
## Status: Must be incorporated before handing to AI coding assistant

---

## SUGGESTION 1 — Feeder Topology Mock in Synthetic Generator

**The Gap:**
Agent 5 (Feeder Balance Auditor) compares consumer meter totals against a SCADA feeder-head reading.
The current `generate_data.py` spec does not generate this feeder-head meter. Without it, Agent 5 has
nothing to compare against and will either crash or silently skip — making your strongest "catch-all"
agent completely untestable in the prototype.

**What to Add:**
In `generate_data.py`, for every feeder, generate one additional "feeder head" synthetic reading:

```
feeder_head_kwh = sum(all consumer meter readings on that feeder)
                + (3% technical line loss)
                + small Gaussian noise (σ = 0.5%)
```

Save these to `data/feeder_head_readings/feeder_{id}_head.csv`.
The Feeder Balance Auditor then reads this file instead of a live SCADA feed.

**Why It Matters:**
Agent 5 is the one agent that catches ANY bypass — even ones that fool the consumer meter completely —
because the missing energy must show up as a gap at the feeder level. If this agent is untestable,
you lose your most robust defence. Judges will ask: "What if a thief bypasses the meter entirely?"
This is your answer. Make sure it works.

---

## SUGGESTION 2 — Use Voltage Signal in Agent 3 (Impossibility Checker)

**The Gap:**
The data schema already includes a `voltage` column. None of the five agents use it. This is a missed
signal — voltage dips or spikes at a meter that does NOT correspond to feeder-level voltage changes
are a known indicator of bypass wiring or tampered meter hardware.

**What to Add:**
In `agent_rules.py`, add one additional rule:

```
Voltage anomaly rule:
- Compute the meter's average voltage over the last 30 days.
- Compute the feeder average voltage for the same period.
- If the meter's voltage deviates > 8% from the feeder average on > 5 days,
  AND the consumption is simultaneously dropping → score 65.
```

**Why It Matters:**
It uses data you are already generating (voltage column exists). It adds a physics-based signal
that is hard to spoof. It shows judges that you understand distribution grid behaviour, not just
data science. One extra rule, significant credibility boost.

---

## SUGGESTION 3 — Live False-Positive Demo in the Dashboard

**The Gap:**
The "vacation scenario" (a family away on holiday — consumption drops, but peer group also drops,
so only 1 of 5 agents fires, score stays at 18/100, no escalation) exists only as a test file
(`test_false_positive_filter.py`). Judges read code for 30 seconds. They watch demos for 3 minutes.

**What to Add:**
In `app.py`, add a "Demo Mode" toggle in the sidebar. When activated:

1. Dashboard loads the vacation scenario meter.
2. Agents run one by one with a 1-second animated delay between each.
3. Each agent's result appears on screen: green checkmark (not firing) or red flag (firing).
4. Score counter fills up to 18/100 — stays below the 75 threshold line.
5. Final banner: "NO ESCALATION — Normal variability detected. 1/5 agents flagged. Threshold: 3/5."

**Why It Matters:**
Most teams demo only the happy path (theft caught). Showing what the system correctly does NOT do
is rare, memorable, and directly answers the "false positives minimised" non-negotiable. This is a
2-3 minute demo segment that will separate your submission from every other team.

**Implementation effort:** ~100 lines of Streamlit code + sleep/animation. High return on investment.

---

## SUGGESTION 4 — Add Isolation Forest as Agent 6 (Optional, Toggleable)

**The Gap:**
The technology stack table in the full plan already lists "Isolation Forest" under anomaly agents.
But the five-agent design doesn't include it. This inconsistency will be noticed by a technical judge
reviewing both documents.

**What to Add:**
Implement `agent_isolation_forest.py` that:
- Trains an Isolation Forest on the full 96-feature daily profile (one kWh reading per 15-min slot).
- Trained on the first 60 days of data for each meter.
- Returns an anomaly score 0–100 based on the isolation forest's `decision_function` output.
- Is **disabled by default** in `fusion_engine.py`.
- Can be enabled via a toggle in the Streamlit sidebar ("Enable Agent 6 — Isolation Forest").

When enabled, the fusion engine runs 6 agents, escalation threshold remains ≥ 3/6 firing.

**Why It Matters:**
Isolation Forest catches multivariate anomalies that pattern-matching and rule engines miss —
for example, a meter with individually normal readings that are collectively inconsistent
(e.g., consumption that is always uniform across all 96 time slots, which is humanly impossible).
Making it optional keeps the prototype stable while showing architectural extensibility.

---

## SUGGESTION 5 — Explicitly State the Weather Data Source

**The Gap:**
The forecast model uses temperature as an external regressor. `generate_data.py` generates synthetic
weather. But judges will ask: "In production, where does weather come from?" The build prompt is
currently silent on this.

**What to Add:**
In `README.md` and `forecast_meters.py` docstring, add this note:

```
Production Weather Source:
Replace data/weather.csv with a one-way API feed from:
- IMD (India Meteorological Department) Open Data Portal: https://mausam.imd.gov.in
- Or: Open-Meteo API (free, no key required): https://open-meteo.com
  Example: api.open-meteo.com/v1/forecast?latitude=12.97&longitude=77.59&hourly=temperature_2m

Both sources provide hourly temperature for Bangalore (lat 12.97, lon 77.59).
Resample to 15-min via linear interpolation. This is the ONLY external data dependency.
Zero raw meter data leaves the BESCOM environment.
```

**Why It Matters:**
It closes the "no external data" concern judges will raise. Weather is aggregate area-level data —
not consumer-specific — so it does not violate the privacy non-negotiable. Naming IMD specifically
shows BESCOM-context awareness. The Open-Meteo alternative shows you have a free fallback.

---

## SUGGESTION 6 — Add DECISIONS.md (Architecture Decision Log)

**The Gap:**
Hackathon judging criteria includes "quality of architecture and risk handling." Most teams submit
code and a README. A one-page decision log — explaining *why* specific choices were made over
obvious alternatives — signals engineering maturity and deliberate design thinking.

**What to Add:**
Create `DECISIONS.md` in Week 4. Template:

```markdown
# GridSight — Architecture Decision Log

## ADR-001: Why CUSUM over STL Decomposition for break detection
CUSUM detects the exact day a sustained shift begins. STL decomposition identifies
that a shift exists but does not pinpoint onset. For generating an inspection case
file with a specific "break detected on [date]" entry, CUSUM is superior.

## ADR-002: Why 7-day persistence threshold
One-time anomalies (power outages, meter resets) can mimic theft signatures for
1-3 days. A 7-day window eliminates these without significantly delaying detection
of real theft (average bypass installation takes effect immediately and persists).

## ADR-003: Why 75/100 composite score threshold
Calibrated against synthetic ground truth: at 70, precision drops below 88%.
At 80, recall drops to 91% (missing 1 of 10 injected thefts). 75 is the
Pareto-optimal point for this dataset. This threshold is configurable in config.py.

## ADR-004: Why Prophet for per-meter, TFT for zone-level
Prophet trains in seconds per meter — viable for 200+ meters on a laptop.
TFT requires GPU-hours to train but only needs to run once per zone (5-10 zones).
The two-stage architecture balances speed and accuracy appropriately.

## ADR-005: Why TimescaleDB over InfluxDB or flat files
BESCOM DBAs know SQL. Zero retraining cost. TimescaleDB is PostgreSQL-compatible —
existing BESCOM tooling (pgAdmin, JDBC connectors, Grafana) works immediately.
InfluxDB uses Flux query language, creating a new skill dependency.
```

**Why It Matters:**
Takes 1 hour to write. Judges who are engineers will read it and immediately trust the architecture.
It shows you made deliberate choices, not just "whatever the tutorial used."

---

## SUGGESTION 7 — Add a `config.py` Central Configuration File

**The Gap:**
Thresholds, weights, and parameters are currently scattered across multiple files
(75/100 in fusion_engine.py, 7 days in escalation logic, ±5% in feeder balance agent, etc.).
If a judge asks "can BESCOM analysts tune the sensitivity?" the answer right now requires
editing multiple Python files.

**What to Add:**
Create `config.py` at the project root:

```python
# config.py — All tunable parameters in one place
# BESCOM analysts can adjust these without touching model code.

# --- Theft Detection Thresholds ---
ESCALATION_SCORE_THRESHOLD = 75        # Composite score to trigger escalation (0-100)
MIN_AGENTS_FIRING = 3                  # Minimum agents that must fire for escalation
PERSISTENCE_DAYS = 7                   # Consecutive flag days before escalation
AGENT_FIRE_THRESHOLD = 40              # Individual agent score to count as "firing"

# --- Agent Weights (must sum to 5.0 initially) ---
AGENT_WEIGHTS = {
    "cusum": 1.0,
    "peer": 1.0,
    "rules": 1.0,
    "patterns": 1.0,
    "feeder_balance": 1.0,
}

# --- Feeder Balance Tolerances ---
NORMAL_TECHNICAL_LOSS_PCT = 3.0        # Expected line loss %
FEEDER_GAP_ALERT_THRESHOLD = 5.0      # Gap % above which to flag
FESTIVAL_DAY_TOLERANCE = 10.0         # Extended tolerance on festival days

# --- Demand Forecasting ---
RISK_ZONE_YELLOW = 0.70               # GREEN → YELLOW threshold
RISK_ZONE_ORANGE = 0.85               # YELLOW → ORANGE threshold
RISK_ZONE_RED = 0.95                  # ORANGE → RED threshold

# --- Data Pipeline ---
MAX_IMPUTABLE_GAP_HOURS = 2           # Gaps shorter than this get peer-median imputed
NEW_METER_MIN_DAYS = 30               # Below this, flag as "insufficient data"
```

**Why It Matters:**
Every other file imports from config.py. This makes the system demonstrably configurable by
non-engineers. When a judge asks "what if we want to lower sensitivity for a specific feeder?"
you point to one file. It also prevents the common hackathon bug where you change a threshold
in one file and forget to update it in another.

---

## QUICK REFERENCE — Priority Order for Implementation

| Priority | Suggestion | Effort | Impact |
|----------|-----------|--------|--------|
| 🔴 CRITICAL | S1 — Feeder head mock data | 30 min | Agent 5 works at all |
| 🔴 CRITICAL | S7 — config.py | 1 hour | System is tunable |
| 🟠 HIGH | S3 — Live FP demo in dashboard | 2 hours | Best demo moment |
| 🟠 HIGH | S6 — DECISIONS.md | 1 hour | Judges trust architecture |
| 🟡 MEDIUM | S2 — Voltage rule in Agent 3 | 1 hour | Physics realism |
| 🟡 MEDIUM | S5 — Weather source in README | 20 min | Closes production gap |
| 🟢 OPTIONAL | S4 — Isolation Forest Agent 6 | 3 hours | Extensibility signal |