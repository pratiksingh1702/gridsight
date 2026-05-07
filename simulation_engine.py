import logging
import uuid
import os
import json
from datetime import datetime
import pandas as pd
from data_utils import (
    load_meter_data,
    load_feeder_head_data,
    prepare_meter_series,
    compute_data_quality,
    set_simulation_overrides,
    clear_simulation_overrides,
)
from simulation_utils import (
    select_injection_window,
    apply_bypass,
    apply_tampering,
    apply_illegal_tapping_feeder,
    apply_missing_data,
    apply_noise,
    align_feeder_head_with_meters,
)
from fusion_engine import evaluate_meter
from residual_intelligence import compute_residuals, classify_residual_pattern
from probabilistic_fusion import build_agent_probabilities, fuse_probabilities
from context_features import build_context_features
from temporal_intelligence import compute_temporal_metrics
from feedback_learning import load_agent_reliability

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

SIMULATION_LOG_PATH = os.path.join("data", "simulation_runs.csv")


def _build_detection_timeline(
    residual_df: pd.DataFrame | None,
    agent_scores: dict,
    agent_probs: dict,
    physics: dict,
    context: dict,
    temporal: dict,
    data_quality: dict,
    reliability: dict,
) -> pd.DataFrame:
    if residual_df is None or residual_df.empty:
        return pd.DataFrame(columns=["date", "p_theft"])

    df = residual_df.copy()
    df['date'] = pd.to_datetime(df['timestamp']).dt.date
    dates = sorted(df['date'].unique())

    rows = []
    for date in dates:
        window = df[df['date'] <= date]
        residual_pattern = classify_residual_pattern(window)
        fusion = fuse_probabilities(
            agent_probs,
            residual_pattern,
            physics,
            agent_scores,
            context=context,
            reliability=reliability,
            temporal=temporal,
            data_quality=data_quality,
        )
        rows.append({"date": pd.to_datetime(date), "p_theft": fusion['p_theft']})

    return pd.DataFrame(rows)


def run_simulation(
    feeder_id: str,
    meter_ids: list[str],
    anomaly_type: str,
    severity: float,
    duration: pd.Timedelta,
    robustness: dict | None = None,
    physics_consistent: bool = False,
    mode: str = "scenario",
    log_run: bool = True,
) -> dict:
    run_id = uuid.uuid4().hex
    meter_ids = [mid for mid in meter_ids if mid]

    meter_original: dict[str, pd.DataFrame] = {}
    meter_modified: dict[str, pd.DataFrame] = {}

    for meter_id in meter_ids:
        df = load_meter_data(meter_id, prefer_processed=True)
        if df is None or df.empty:
            logger.warning("[simulation] Missing meter data for %s", meter_id)
            continue
        meter_original[meter_id] = df.copy()

    if not meter_original:
        return {
            "run_id": run_id,
            "status": "no_data",
            "message": "No meter data available for simulation.",
        }

    anchor_df = next(iter(meter_original.values()))
    start_ts, end_ts = select_injection_window(anchor_df, duration)

    robustness = robustness or {}
    missing_ratio = float(robustness.get('missing_ratio', 0.0))
    noise_level = float(robustness.get('noise_level', 0.0))

    for meter_id, df in meter_original.items():
        if anomaly_type == "bypass":
            modified = apply_bypass(df, severity, start_ts, end_ts)
        elif anomaly_type == "tampering":
            modified = apply_tampering(df, severity, start_ts, end_ts, seed=hash(meter_id) % 10_000)
        else:
            modified = df.copy()

        if missing_ratio > 0:
            modified = apply_missing_data(
                modified,
                missing_ratio,
                start_ts,
                end_ts,
                seed=hash((meter_id, "missing")) % 10_000,
            )

        if noise_level > 0:
            modified = apply_noise(
                modified,
                noise_level,
                start_ts,
                end_ts,
                seed=hash((meter_id, "noise")) % 10_000,
            )

        meter_modified[meter_id] = modified

    feeder_modified: dict[str, pd.DataFrame] = {}
    if physics_consistent:
        feeder_df = load_feeder_head_data(feeder_id, prefer_processed=True)
        if feeder_df is not None and not feeder_df.empty:
            feeder_modified[feeder_id] = align_feeder_head_with_meters(
                feeder_df,
                meter_original,
                meter_modified,
            )
    elif anomaly_type == "illegal tapping":
        feeder_df = load_feeder_head_data(feeder_id, prefer_processed=True)
        if feeder_df is not None and not feeder_df.empty:
            feeder_modified[feeder_id] = apply_illegal_tapping_feeder(
                feeder_df,
                severity,
                start_ts,
                end_ts,
                seed=hash(feeder_id) % 10_000,
            )

    results: dict[str, dict] = {}
    timeline = pd.DataFrame(columns=["date", "p_theft"])
    residuals = pd.DataFrame(columns=["timestamp", "residual_kwh"])

    try:
        set_simulation_overrides(meter_modified, feeder_modified)

        for meter_id in meter_ids:
            if meter_id in meter_modified:
                results[meter_id] = evaluate_meter(meter_id, log_result=False)

        if meter_ids:
            primary_id = meter_ids[0]
            residual_df = compute_residuals(primary_id)
            if residual_df is not None and not residual_df.empty:
                residuals = residual_df[['timestamp', 'residual_kwh']].copy()
            meter_df = prepare_meter_series(primary_id)
            data_quality = compute_data_quality(meter_df) if meter_df is not None else {}
            context = build_context_features(primary_id)
            temporal = compute_temporal_metrics(primary_id)
            reliability = load_agent_reliability()

            primary_result = results.get(primary_id, {})
            agent_scores = primary_result.get('agent_scores', {})
            agent_probs = primary_result.get('agent_probabilities', build_agent_probabilities(agent_scores))
            physics = primary_result.get('physics', {})

            timeline = _build_detection_timeline(
                residual_df,
                agent_scores,
                agent_probs,
                physics,
                context,
                temporal,
                data_quality,
                reliability,
            )
    finally:
        clear_simulation_overrides()

    display_window_start = start_ts - pd.Timedelta(days=1)
    display_window_end = end_ts + pd.Timedelta(days=1)
    before_after: dict[str, pd.DataFrame] = {}

    for meter_id, original in meter_original.items():
        modified = meter_modified.get(meter_id, original)
        orig = original.copy()
        mod = modified.copy()
        orig['timestamp'] = pd.to_datetime(orig['timestamp'])
        mod['timestamp'] = pd.to_datetime(mod['timestamp'])

        window_mask = (orig['timestamp'] >= display_window_start) & (orig['timestamp'] <= display_window_end)
        orig_window = orig[window_mask][['timestamp', 'kwh']].rename(columns={'kwh': 'before_kwh'})
        mod_window = mod[window_mask][['timestamp', 'kwh']].rename(columns={'kwh': 'after_kwh'})
        merged = orig_window.merge(mod_window, on='timestamp', how='left')
        before_after[meter_id] = merged

    summary = {}
    if meter_ids:
        primary_id = meter_ids[0]
        primary_result = results.get(primary_id, {})
        physics = primary_result.get('physics', {})
        energy = physics.get('energy_balance', {}) if isinstance(physics, dict) else {}
        econ = primary_result.get('economic', {})
        decision = primary_result.get('decision_details', {})
        theft_class = primary_result.get('theft_class', {})

        summary = {
            "primary_meter_id": primary_id,
            "p_theft": float(primary_result.get('p_theft', 0.0)),
            "decision": decision.get('decision', primary_result.get('decision')),
            "physics_gap_pct": float(energy.get('gap_pct', 0.0)),
            "projected_loss_30d": float(econ.get('projected_loss_30d_value', 0.0)),
            "roi": float(econ.get('roi', 0.0)),
            "classification": theft_class.get('class', 'unknown'),
        }

    result = {
        "run_id": run_id,
        "status": "ok",
        "scenario": {
            "feeder_id": feeder_id,
            "meter_ids": meter_ids,
            "anomaly_type": anomaly_type,
            "severity": severity,
            "duration_hours": duration.total_seconds() / 3600.0,
            "start_ts": start_ts.isoformat(),
            "end_ts": end_ts.isoformat(),
            "robustness": robustness,
            "physics_consistent": physics_consistent,
        },
        "results": results,
        "before_after": before_after,
        "timeline": timeline,
        "residuals": residuals,
        "summary": summary,
    }

    if log_run:
        log_simulation_run(result, mode=mode)

    return result


def log_simulation_run(result: dict, mode: str = "scenario") -> None:
    if not result or result.get("status") != "ok":
        return

    summary = result.get("summary", {})
    scenario = result.get("scenario", {})
    row = {
        "run_id": result.get("run_id"),
        "timestamp": datetime.utcnow().isoformat(),
        "mode": mode,
        "feeder_id": scenario.get("feeder_id"),
        "meter_ids": json.dumps(scenario.get("meter_ids", [])),
        "anomaly_type": scenario.get("anomaly_type"),
        "severity": scenario.get("severity"),
        "duration_hours": scenario.get("duration_hours"),
        "robustness": json.dumps(scenario.get("robustness", {})),
        "physics_consistent": scenario.get("physics_consistent"),
        "primary_meter_id": summary.get("primary_meter_id"),
        "p_theft": summary.get("p_theft"),
        "decision": summary.get("decision"),
        "physics_gap_pct": summary.get("physics_gap_pct"),
        "projected_loss_30d": summary.get("projected_loss_30d"),
        "roi": summary.get("roi"),
        "classification": summary.get("classification"),
    }

    df = pd.DataFrame([row])
    if os.path.exists(SIMULATION_LOG_PATH):
        df.to_csv(SIMULATION_LOG_PATH, mode="a", header=False, index=False)
    else:
        df.to_csv(SIMULATION_LOG_PATH, index=False)


def load_simulation_history(limit: int = 200) -> pd.DataFrame:
    if not os.path.exists(SIMULATION_LOG_PATH):
        return pd.DataFrame()
    df = pd.read_csv(SIMULATION_LOG_PATH)
    if df.empty:
        return df
    return df.tail(limit)


def run_scenario_comparison(
    feeder_id: str,
    meter_ids: list[str],
    anomaly_type: str,
    severity: float,
    duration: pd.Timedelta,
    robustness: dict | None = None,
) -> dict:
    baseline = run_simulation(
        feeder_id=feeder_id,
        meter_ids=meter_ids,
        anomaly_type="none",
        severity=0.0,
        duration=duration,
        robustness={},
        physics_consistent=False,
        mode="baseline",
    )
    injected = run_simulation(
        feeder_id=feeder_id,
        meter_ids=meter_ids,
        anomaly_type=anomaly_type,
        severity=severity,
        duration=duration,
        robustness=robustness,
        physics_consistent=False,
        mode="comparison",
    )

    return {
        "baseline": baseline,
        "injected": injected,
    }


def run_severity_sweep(
    feeder_id: str,
    meter_ids: list[str],
    anomaly_type: str,
    severities: list[float],
    duration: pd.Timedelta,
    robustness: dict | None = None,
) -> pd.DataFrame:
    rows = []
    for sev in severities:
        result = run_simulation(
            feeder_id=feeder_id,
            meter_ids=meter_ids,
            anomaly_type=anomaly_type,
            severity=sev,
            duration=duration,
            robustness=robustness,
            physics_consistent=False,
            mode="severity_sweep",
        )
        summary = result.get("summary", {})
        rows.append({
            "severity": sev,
            "p_theft": summary.get("p_theft", 0.0),
            "decision": summary.get("decision"),
            "physics_gap_pct": summary.get("physics_gap_pct", 0.0),
        })

    return pd.DataFrame(rows)


def run_physics_consistency_test(
    feeder_id: str,
    meter_ids: list[str],
    anomaly_type: str,
    severity: float,
    duration: pd.Timedelta,
    robustness: dict | None = None,
) -> dict:
    mismatch = run_simulation(
        feeder_id=feeder_id,
        meter_ids=meter_ids,
        anomaly_type=anomaly_type,
        severity=severity,
        duration=duration,
        robustness=robustness,
        physics_consistent=False,
        mode="physics_mismatch",
    )

    consistent = run_simulation(
        feeder_id=feeder_id,
        meter_ids=meter_ids,
        anomaly_type=anomaly_type,
        severity=severity,
        duration=duration,
        robustness=robustness,
        physics_consistent=True,
        mode="physics_consistent",
    )

    return {
        "mismatch": mismatch,
        "consistent": consistent,
    }


def run_robustness_test(
    feeder_id: str,
    meter_ids: list[str],
    anomaly_type: str,
    severity: float,
    duration: pd.Timedelta,
    missing_ratio: float,
    noise_level: float,
) -> dict:
    base = run_simulation(
        feeder_id=feeder_id,
        meter_ids=meter_ids,
        anomaly_type=anomaly_type,
        severity=severity,
        duration=duration,
        robustness={},
        physics_consistent=False,
        mode="robustness_baseline",
    )

    robust = run_simulation(
        feeder_id=feeder_id,
        meter_ids=meter_ids,
        anomaly_type=anomaly_type,
        severity=severity,
        duration=duration,
        robustness={"missing_ratio": missing_ratio, "noise_level": noise_level},
        physics_consistent=False,
        mode="robustness",
    )

    return {
        "baseline": base,
        "robust": robust,
    }
