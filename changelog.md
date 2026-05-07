# Changelog

## 2026-05-05

### Added
- Residual intelligence layer for forecast vs actual deltas and pattern labeling.
- Probabilistic fusion engine with calibrated agent probabilities and logistic fusion features.
- Physics engine upgrade with energy balance, dynamic line loss, phase imbalance, and topology context.
- Theft classification module for bypass, tampering, illegal tapping, and normal anomaly.
- Economic impact module with loss estimation, ROI, and priority scoring.
- Decision engine for action recommendation, urgency, and inspection schedule.
- Explainability layer with contributing factors and physics validation context.
- Data utilities for handling missing data and low-frequency readings.
- Context-aware fusion features (time of day, load level, feeder type) and adaptive weighting with agent reliability.
- Physics confidence scoring and probability adjustment using feeder consistency.
- Hierarchical classification stages (anomaly/noise, theft/technical, theft type).
- Temporal intelligence for persistence and trend tracking.
- Feedback learning loop with inspection results and adaptive thresholds.
- Uncertainty estimation and probability confidence intervals.
- Simulation Lab tab with anomaly injection, pipeline replay, and diagnostics visualizations.
- Simulation validation modes: scenario comparison, severity sweep, physics consistency, signal alignment, robustness tests, and run history logging.

### Changed
- Fusion pipeline now outputs P(theft) and structured decision artifacts while keeping legacy weighted score.
- Streamlit theft dashboard updated with feeder risk heatmap, ROI-ranked action table, detailed case panel, and loss simulation.
- Case file generator enriched with probabilistic outputs, theft class, ROI, and urgency.
- Agent robustness improvements for missing or irregular data.
- Escalation log loading now tolerates mixed schemas and normalizes timestamps to UTC for temporal metrics.
- Test expectations updated to validate probabilistic fusion behavior.
- Risk-adjusted economics now prioritize expected value.
- Decision engine integrates persistence and adaptive thresholds.

### Notes
- Core modular architecture (data -> models -> fusion -> output) preserved and extended.
