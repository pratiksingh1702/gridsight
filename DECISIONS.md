# GridSight — Architecture Decision Log

## ADR-001: Why CUSUM over STL Decomposition for break detection
CUSUM detects the exact day a sustained shift begins. STL decomposition identifies that a shift exists but does not pinpoint onset. For generating an inspection case file with a specific "break detected on [date]" entry, CUSUM is superior.

## ADR-002: Why 7-day persistence threshold
One-time anomalies (power outages, meter resets) can mimic theft signatures for 1-3 days. A 7-day window eliminates these without significantly delaying detection of real theft (average bypass installation takes effect immediately and persists).

## ADR-003: Why 75/100 composite score threshold
Calibrated against synthetic ground truth: at 70, precision drops below 88%. At 80, recall drops to 91% (missing 1 of 10 injected thefts). 75 is the Pareto-optimal point for this dataset. This threshold is configurable in config.py.

## ADR-004: Why Prophet for per-meter, TFT for zone-level
Prophet trains in seconds per meter — viable for 200+ meters on a laptop. TFT requires GPU-hours to train but only needs to run once per zone (5-10 zones). The two-stage architecture balances speed and accuracy appropriately.

## ADR-005: Why TimescaleDB over InfluxDB or flat files
BESCOM DBAs know SQL. Zero retraining cost. TimescaleDB is PostgreSQL-compatible — existing BESCOM tooling (pgAdmin, JDBC connectors, Grafana) works immediately. InfluxDB uses Flux query language, creating a new skill dependency.

## ADR-006: Why CSV-mode Fallback
PostgreSQL unavailability during the initial build prompted a CSV-mode implementation (`USE_DB = False`). This ensures the prototype is portable and can be demonstrated without complex infrastructure setup while maintaining the option to scale to TimescaleDB later.

## ADR-007: Why Context-Aware Probabilistic Fusion
Static weights fail under different load regimes (night vs peak hours) and feeder types. Context-aware fusion adjusts signal influence based on time-of-day, load level, and feeder classification while preserving explainability.

## ADR-008: Why Physics Confidence Calibration
Energy-balance consistency is a strong physical constraint. A physics confidence score helps calibrate $P(\text{theft})$ upward when feeder losses are inconsistent and downward when the physics check is clean, reducing false positives.

## ADR-009: Why Expected Value for Prioritization
Inspection budgets are limited. Prioritizing cases using Expected Value ($P(\text{theft}) \times \text{loss}$) aligns field effort with economic impact instead of raw anomaly scores.

## ADR-010: Why Feedback Learning with Adaptive Thresholds
Static thresholds drift as grid behavior changes. Updating agent reliability and adaptive thresholds with inspection outcomes keeps the system calibrated without manual retuning.

## ADR-011: Why Temporal Intelligence
Single-day anomalies are common (outages, maintenance). Persistence and trend tracking distinguish transient noise from sustained theft patterns and reduce unnecessary field visits.
