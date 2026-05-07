import streamlit as st
import pandas as pd
import numpy as np
import time
import os
import json
import ast
import folium
from streamlit_folium import folium_static, st_folium
import config
from dashboard_demand import render_demand_dashboard, get_transformer_data
from fusion_engine import evaluate_meter
from generate_case_file import generate_case_file
from data_utils import load_escalation_log
from simulation_engine import (
    run_simulation,
    run_scenario_comparison,
    run_severity_sweep,
    run_physics_consistency_test,
    run_robustness_test,
    load_simulation_history,
)
from styles import MAIN_CSS, metric_card, explanation_box

# Page Config
st.set_page_config(page_title="GridSight | AI Grid Guardian", layout="wide", initial_sidebar_state="expanded")

# Inject CSS
st.markdown(MAIN_CSS, unsafe_allow_html=True)

def _parse_json_field(value):
    if isinstance(value, dict):
        return value
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return {}
    try:
        return json.loads(value)
    except Exception:
        try:
            return ast.literal_eval(value)
        except Exception:
            return {}


def _render_risk_heatmap(df_log: pd.DataFrame):
    metadata_path = os.path.join("data", "feeder_metadata.csv")
    if not os.path.exists(metadata_path):
        st.warning("Feeder metadata missing. Heatmap unavailable.")
        return

    metadata = pd.read_csv(metadata_path)
    if metadata.empty:
        st.warning("Feeder metadata empty. Heatmap unavailable.")
        return

    feeder_risk = df_log.groupby('feeder_id')['p_theft'].mean().reset_index()
    feeder_geo = metadata.groupby('feeder_id').agg({
        'latitude': 'mean',
        'longitude': 'mean'
    }).reset_index()

    merged = feeder_geo.merge(feeder_risk, on='feeder_id', how='left').fillna(0.0)

    m = folium.Map(location=[12.9716, 77.5946], zoom_start=12, tiles='CartoDB positron')
    for _, row in merged.iterrows():
        risk = float(row['p_theft'])
        if risk >= 0.85:
            color = '#EF4444'
        elif risk >= 0.70:
            color = '#F59E0B'
        elif risk >= 0.55:
            color = '#EAB308'
        else:
            color = '#10B981'

        folium.CircleMarker(
            location=[row['latitude'], row['longitude']],
            radius=12,
            popup=f"Feeder: {row['feeder_id']}<br/>P(theft): {risk:.2f}",
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.7
        ).add_to(m)

    folium_static(m, width=700, height=420)


def render_theft_dashboard():
    st.title("🔍 Anomaly Detective")
    st.markdown(explanation_box(
        "What is this?", 
        "This is our digital detective unit. It monitors every smart meter for suspicious patterns that suggest electricity is being stolen or the meter has been tampered with."
    ), unsafe_allow_html=True)
    
    # 1. Load Escalated Data
    log_path = os.path.join("data", "escalation_log.csv")
    if not os.path.exists(log_path):
        st.warning("Gathering initial evidence...")
        with st.spinner("Analyzing meters..."):
            for i in range(10):
                evaluate_meter(f"meter_{i:03d}")
    
    df_log = load_escalation_log(log_path)

    # Parse structured fields
    if 'agent_scores' in df_log.columns:
        df_log['agent_scores_parsed'] = df_log['agent_scores'].apply(_parse_json_field)
    else:
        df_log['agent_scores_parsed'] = [{} for _ in range(len(df_log))]

    if 'economic' in df_log.columns:
        df_log['economic_parsed'] = df_log['economic'].apply(_parse_json_field)
    else:
        df_log['economic_parsed'] = [{} for _ in range(len(df_log))]

    if 'decision_details' in df_log.columns:
        df_log['decision_parsed'] = df_log['decision_details'].apply(_parse_json_field)
    else:
        df_log['decision_parsed'] = [{} for _ in range(len(df_log))]

    if 'theft_class' in df_log.columns:
        df_log['theft_class_parsed'] = df_log['theft_class'].apply(_parse_json_field)
    else:
        df_log['theft_class_parsed'] = [{} for _ in range(len(df_log))]

    if 'p_theft' not in df_log.columns:
        df_log['p_theft'] = df_log['weighted_score'] / 100.0

    df_log['roi'] = df_log['economic_parsed'].apply(lambda x: x.get('roi', 0.0))
    df_log['priority_score'] = df_log['economic_parsed'].apply(lambda x: x.get('priority_score', 0.0))
    df_log['expected_value'] = df_log['economic_parsed'].apply(lambda x: x.get('expected_value', 0.0))
    df_log['projected_loss_30d'] = df_log['economic_parsed'].apply(lambda x: x.get('projected_loss_30d_value', 0.0))
    df_log['theft_class_label'] = df_log['theft_class_parsed'].apply(lambda x: x.get('class', 'unknown'))
    df_log['action_recommendation'] = df_log['decision_parsed'].apply(lambda x: x.get('action_recommendation', 'Monitor'))
    df_log['urgency'] = df_log['decision_parsed'].apply(lambda x: x.get('urgency', 'LOW'))

    if 'feeder_id' not in df_log.columns:
        metadata_path = os.path.join("data", "feeder_metadata.csv")
        if os.path.exists(metadata_path):
            metadata = pd.read_csv(metadata_path)
            df_log = df_log.merge(metadata[['meter_id', 'feeder_id']], on='meter_id', how='left')
    
    # Summary Metrics
    avg_p_theft = float(df_log['p_theft'].mean()) if not df_log.empty else 0.0

    c1, c2, c3 = st.columns(3)
    with c1: st.markdown(metric_card("Analyzed Meters", len(df_log)), unsafe_allow_html=True)
    with c2: st.markdown(metric_card("Theft Alerts", len(df_log[df_log['decision'] == "ESCALATE"])), unsafe_allow_html=True)
    with c3: st.markdown(metric_card("Avg P(Theft)", f"{avg_p_theft:.2f}"), unsafe_allow_html=True)
    
    st.divider()
    
    st.subheader("Feeder Risk Heatmap")
    _render_risk_heatmap(df_log)

    col_table, col_exp = st.columns([2, 1])
    
    with col_table:
        st.subheader("Prioritized Action Table")
        display_df = df_log.sort_values('expected_value', ascending=False)
        st.dataframe(
            display_df[[
                'meter_id', 'p_theft', 'expected_value', 'roi', 'priority_score', 'theft_class_label',
                'projected_loss_30d', 'action_recommendation', 'urgency'
            ]],
            use_container_width=True,
            column_config={
                "p_theft": st.column_config.ProgressColumn("P(Theft)", min_value=0, max_value=1, format="%.2f"),
                "expected_value": st.column_config.NumberColumn("Expected Value", format="INR %.0f"),
                "roi": st.column_config.NumberColumn("ROI", format="%.2f"),
                "priority_score": st.column_config.ProgressColumn("Priority", min_value=0, max_value=100, format="%.0f"),
                "projected_loss_30d": st.column_config.NumberColumn("Projected Loss (30d)", format="INR %.0f"),
                "urgency": st.column_config.TextColumn("Urgency")
            }
        )
    
    with col_exp:
        st.markdown(explanation_box(
            "How to read this?",
            "**P(Theft)**: Calibrated probability from all agents + residual + physics.<br/><br/>"
            "**Expected Value**: P(theft) x projected loss. Highest expected value goes first.",
            type="info"
        ), unsafe_allow_html=True)

    # Actions
    st.divider()
    st.subheader("Detailed Case Panel")
    if display_df.empty:
        st.info("No cases available yet.")
        return

    selected_id = st.selectbox("Select a meter to investigate", display_df['meter_id'].unique())

    if selected_id:
        with st.spinner("Refreshing case intelligence..."):
            live_res = evaluate_meter(selected_id, log_result=False)
        econ = live_res.get('economic', {})
        decision = live_res.get('decision_details', {})
        theft_class = live_res.get('theft_class', {})
        hierarchical = live_res.get('hierarchical_classification', {})
        residual = live_res.get('residual_pattern', {})
        physics = live_res.get('physics', {})

        st.write(f"### Case Summary: {selected_id}")
        m1, m2, m3, m4 = st.columns(4)
        with m1: st.metric("P(Theft)", f"{live_res.get('p_theft', 0.0):.2f}")
        with m2: st.metric("Confidence Interval", f"{live_res.get('p_theft_ci_low', 0.0):.2f} - {live_res.get('p_theft_ci_high', 0.0):.2f}")
        with m3: st.metric("Expected Value", f"INR {econ.get('expected_value', 0.0):.0f}")
        with m4: st.metric("Urgency", decision.get('urgency', 'LOW'))

        st.markdown(explanation_box(
            "Decision",
            f"{decision.get('action_recommendation', 'Monitor')}. Inspection schedule: {decision.get('inspection_schedule', 'N/A')}",
            type="info" if live_res.get('decision') == 'MONITOR' else "warning"
        ), unsafe_allow_html=True)

        st.write("### Contributing Factors")
        st.write(f"Residual pattern: {residual.get('type', 'unknown')} (conf {residual.get('confidence', 0.0):.2f})")
        balance = physics.get('energy_balance', {})
        st.write(
            f"Energy gap: {balance.get('gap_pct', 0.0):.2f}% | Phase imbalance: {physics.get('phase_imbalance', {}).get('is_imbalanced', False)} | "
            f"Physics confidence: {live_res.get('physics_confidence', 0.0):.2f}"
        )
        st.write(f"Uncertainty: {live_res.get('uncertainty', 0.0):.2f}")
        st.write(
            f"Hierarchical: {hierarchical.get('stage_1', 'unknown')} -> {hierarchical.get('stage_2', 'unknown')} | "
            f"Theft class: {theft_class.get('class', 'unknown')} (conf {theft_class.get('confidence', 0.0):.2f})"
        )

        scores = live_res.get('agent_scores', {})
        st.write("### Agent Scores")
        score_cols = st.columns(len(scores)) if scores else []
        for i, (agent, score) in enumerate(scores.items()):
            with score_cols[i]:
                st.markdown(f"**{agent.replace('_', ' ').title()}**")
                if score >= config.AGENT_FIRE_THRESHOLD:
                    st.error(f"{score:.0f}")
                else:
                    st.success(f"{score:.0f}")

        st.write("### Simulation: Projected Loss if Ignored")
        projected = econ.get('projected_loss_30d_value', 0.0)
        daily = projected / max(1, config.LOSS_PROJECTION_DAYS)
        sim_days = np.arange(1, config.LOSS_PROJECTION_DAYS + 1)
        sim_loss = np.cumsum(np.full_like(sim_days, daily, dtype=float))
        st.line_chart(pd.DataFrame({'Day': sim_days, 'Projected Loss': sim_loss}).set_index('Day'))

        if st.button("Generate Official Inspection Case File (PDF)"):
            pdf_path = generate_case_file(selected_id, live_res)
            st.success(f"File ready for field crew: {pdf_path}")
            st.balloons()

def render_simulation_lab():
    st.title("Simulation Lab")
    st.markdown(explanation_box(
        "What is this?",
        "Use this lab to inject realistic anomalies and run the full detection pipeline on controlled scenarios.",
        type="info"
    ), unsafe_allow_html=True)

    metadata_path = os.path.join("data", "feeder_metadata.csv")
    if not os.path.exists(metadata_path):
        st.warning("Feeder metadata missing. Simulation lab unavailable.")
        return

    metadata = pd.read_csv(metadata_path)
    if metadata.empty:
        st.warning("Feeder metadata empty. Simulation lab unavailable.")
        return

    defaults = {
        "sim_selected_meters": [],
        "sim_result": None,
        "sim_comparison": None,
        "sim_sweep": None,
        "sim_physics_test": None,
        "sim_robustness": None,
        "sim_transformer": "(none)",
        "sim_feeder_id": None,
        "sim_anomaly_type": "bypass",
        "sim_severity": 0.6,
        "sim_duration_value": 24,
        "sim_duration_unit": "hours",
        "sim_missing_enabled": False,
        "sim_missing_ratio": 0.08,
        "sim_noise_enabled": False,
        "sim_noise_level": 0.05,
        "sim_dirty": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    def _mark_dirty():
        st.session_state["sim_dirty"] = True
        st.session_state["sim_result"] = None
        st.session_state["sim_comparison"] = None
        st.session_state["sim_sweep"] = None
        st.session_state["sim_physics_test"] = None
        st.session_state["sim_robustness"] = None

    transformers = get_transformer_data()
    transformer_options = ["(none)"] + transformers['id'].tolist()
    feeder_ids = sorted(metadata['feeder_id'].unique().tolist())

    if st.session_state["sim_feeder_id"] is None and feeder_ids:
        st.session_state["sim_feeder_id"] = feeder_ids[0]

    scenario_tab, comparison_tab, analysis_tab = st.tabs(["Scenario", "Comparison", "Analysis"])

    with scenario_tab:
        col_controls, col_map = st.columns([1, 1])

        with col_controls:
            st.subheader("Scenario Builder")
            with st.form("sim_scenario_form", clear_on_submit=False):
                selected_transformer = st.selectbox(
                    "Select transformer",
                    transformer_options,
                    index=transformer_options.index(st.session_state["sim_transformer"])
                    if st.session_state["sim_transformer"] in transformer_options else 0,
                )

                if selected_transformer != "(none)":
                    feeder_id = transformers[transformers['id'] == selected_transformer].iloc[0]['feeder']
                    st.caption(f"Feeder locked to {feeder_id}")
                else:
                    feeder_id = st.selectbox(
                        "Select feeder",
                        feeder_ids,
                        index=feeder_ids.index(st.session_state["sim_feeder_id"])
                        if st.session_state["sim_feeder_id"] in feeder_ids else 0,
                    )

                meter_options = metadata[metadata['feeder_id'] == feeder_id]['meter_id'].tolist()
                default_meters = [m for m in st.session_state["sim_selected_meters"] if m in meter_options]
                selected_meters = st.multiselect(
                    "Select meter(s)",
                    meter_options,
                    default=default_meters,
                )

                anomaly_type = st.selectbox(
                    "Anomaly type",
                    ["bypass", "tampering", "illegal tapping"],
                    index=["bypass", "tampering", "illegal tapping"].index(st.session_state["sim_anomaly_type"]),
                )

                severity = st.slider("Severity", 0.1, 0.9, float(st.session_state["sim_severity"]), 0.05)

                duration_value = st.number_input(
                    "Duration",
                    min_value=1,
                    max_value=168,
                    value=int(st.session_state["sim_duration_value"]),
                    step=1,
                )
                duration_unit = st.selectbox(
                    "Duration unit",
                    ["hours", "days"],
                    index=["hours", "days"].index(st.session_state["sim_duration_unit"]),
                )

                st.markdown("**Robustness Controls**")
                missing_enabled = st.checkbox("Inject missing data", value=st.session_state["sim_missing_enabled"])
                missing_ratio = 0.0
                if missing_enabled:
                    missing_ratio = st.slider("Missing ratio", 0.01, 0.3, float(st.session_state["sim_missing_ratio"]), 0.01)

                noise_enabled = st.checkbox("Add noise", value=st.session_state["sim_noise_enabled"])
                noise_level = 0.0
                if noise_enabled:
                    noise_level = st.slider("Noise level", 0.01, 0.3, float(st.session_state["sim_noise_level"]), 0.01)

                run_col, reset_col = st.columns(2)
                run_clicked = run_col.form_submit_button("Run Simulation", type="primary")
                reset_clicked = reset_col.form_submit_button("Reset Simulation")

            st.session_state["sim_transformer"] = selected_transformer
            st.session_state["sim_feeder_id"] = feeder_id
            st.session_state["sim_selected_meters"] = selected_meters
            st.session_state["sim_anomaly_type"] = anomaly_type
            st.session_state["sim_severity"] = severity
            st.session_state["sim_duration_value"] = duration_value
            st.session_state["sim_duration_unit"] = duration_unit
            st.session_state["sim_missing_enabled"] = missing_enabled
            if missing_enabled:
                st.session_state["sim_missing_ratio"] = missing_ratio
            st.session_state["sim_noise_enabled"] = noise_enabled
            if noise_enabled:
                st.session_state["sim_noise_level"] = noise_level

            duration = pd.Timedelta(hours=duration_value) if duration_unit == "hours" else pd.Timedelta(days=duration_value)
            robustness = {
                "missing_ratio": missing_ratio if missing_enabled else 0.0,
                "noise_level": noise_level if noise_enabled else 0.0,
            }

            if run_clicked:
                if not selected_meters:
                    st.warning("Select at least one meter to simulate.")
                else:
                    result = run_simulation(
                        feeder_id=feeder_id,
                        meter_ids=selected_meters,
                        anomaly_type=anomaly_type,
                        severity=severity,
                        duration=duration,
                        robustness=robustness,
                    )
                    st.session_state["sim_result"] = result
                    st.session_state["sim_dirty"] = False

            if reset_clicked:
                st.session_state["sim_result"] = None
                st.session_state["sim_selected_meters"] = []
                st.session_state["sim_dirty"] = True

        with col_map:
            st.subheader("Meter Map")
            map_df = metadata[metadata['feeder_id'] == feeder_id].copy()
            if map_df.empty:
                st.info("No meters found for the selected feeder.")
                return
            map_center = [map_df['latitude'].mean(), map_df['longitude'].mean()]
            sim_map = folium.Map(location=map_center, zoom_start=12, tiles='CartoDB positron')

            selected_set = set(st.session_state["sim_selected_meters"])
            for _, row in map_df.iterrows():
                color = '#EF4444' if row['meter_id'] in selected_set else '#3B82F6'
                folium.CircleMarker(
                    location=[row['latitude'], row['longitude']],
                    radius=8,
                    tooltip=row['meter_id'],
                    popup=f"{row['meter_id']} ({row['feeder_id']})",
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.7
                ).add_to(sim_map)

            map_state = st_folium(sim_map, width=700, height=450)
            if map_state and map_state.get("last_object_clicked_tooltip"):
                clicked_meter = map_state["last_object_clicked_tooltip"]
                if clicked_meter in meter_options:
                    updated = list(st.session_state["sim_selected_meters"])
                    if clicked_meter in updated:
                        updated.remove(clicked_meter)
                    else:
                        updated.append(clicked_meter)
                    st.session_state["sim_selected_meters"] = updated
                    _mark_dirty()

            result = st.session_state.get("sim_result")
            if result and result.get("status") == "ok" and not st.session_state.get("sim_dirty"):
                st.divider()
                st.subheader("Decision Summary")

                scenario = result.get("scenario", {})
                meter_ids = scenario.get("meter_ids", [])
                if not meter_ids:
                    return

                primary_id = st.selectbox("Select meter to inspect", meter_ids, index=0)
                meter_result = result["results"].get(primary_id, {})
                decision = meter_result.get("decision_details", {})
                econ = meter_result.get("economic", {})
                theft_class = meter_result.get("theft_class", {})
                physics = meter_result.get("physics", {})
                energy = physics.get("energy_balance", {})

                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.metric("P(Theft)", f"{meter_result.get('p_theft', 0.0):.2f}")
                with c2:
                    st.metric("Decision", decision.get('decision', meter_result.get('decision', 'NA')))
                with c3:
                    st.metric("Projected Loss (30d)", f"INR {econ.get('projected_loss_30d_value', 0.0):.0f}")
                with c4:
                    st.metric("Physics Gap %", f"{energy.get('gap_pct', 0.0):.2f}")

                st.markdown(explanation_box(
                    "Recommended Action",
                    decision.get('action_recommendation', 'Monitor'),
                    type="warning" if decision.get('decision') == 'ESCALATE' else "info"
                ), unsafe_allow_html=True)

                st.write("### Before vs After")
                before_after = result["before_after"].get(primary_id)
                if before_after is not None and not before_after.empty:
                    st.line_chart(before_after.set_index('timestamp')[['before_kwh', 'after_kwh']])
                else:
                    st.info("No time series available for visualization.")

    with comparison_tab:
        st.subheader("Scenario Comparison")
        feeder_id = st.session_state.get("sim_feeder_id")
        meter_ids = st.session_state.get("sim_selected_meters", [])
        anomaly_type = st.session_state.get("sim_anomaly_type")
        severity = float(st.session_state.get("sim_severity", 0.6))
        duration_value = st.session_state.get("sim_duration_value", 24)
        duration_unit = st.session_state.get("sim_duration_unit", "hours")
        duration = pd.Timedelta(hours=duration_value) if duration_unit == "hours" else pd.Timedelta(days=duration_value)

        robustness = {
            "missing_ratio": float(st.session_state.get("sim_missing_ratio", 0.0)) if st.session_state.get("sim_missing_enabled") else 0.0,
            "noise_level": float(st.session_state.get("sim_noise_level", 0.0)) if st.session_state.get("sim_noise_enabled") else 0.0,
        }

        if st.session_state.get("sim_dirty"):
            st.warning("Scenario inputs changed. Click Run Simulation in Scenario tab before running comparison.")

        with st.form("sim_comparison_form", clear_on_submit=False):
            run_comparison = st.form_submit_button("Run Comparison", type="primary")

        if run_comparison:
            if not feeder_id or not meter_ids:
                st.warning("Select feeder and meters in the Scenario tab first.")
            elif st.session_state.get("sim_dirty"):
                st.warning("Scenario is not finalized. Run Simulation in Scenario tab first.")
            else:
                with st.spinner("Running baseline vs injected comparison..."):
                    comparison = run_scenario_comparison(
                        feeder_id=feeder_id,
                        meter_ids=meter_ids,
                        anomaly_type=anomaly_type,
                        severity=severity,
                        duration=duration,
                        robustness=robustness,
                    )
                st.session_state["sim_comparison"] = comparison

        comparison = st.session_state.get("sim_comparison")
        if comparison:
            baseline = comparison.get("baseline", {}).get("summary", {})
            injected = comparison.get("injected", {}).get("summary", {})

            col_base, col_inj = st.columns(2)
            with col_base:
                st.markdown("**Baseline**")
                st.metric("P(Theft)", f"{baseline.get('p_theft', 0.0):.2f}")
                st.metric("Physics Gap %", f"{baseline.get('physics_gap_pct', 0.0):.2f}")
                st.metric("Projected Loss (30d)", f"INR {baseline.get('projected_loss_30d', 0.0):.0f}")
            with col_inj:
                st.markdown("**Injected**")
                st.metric("P(Theft)", f"{injected.get('p_theft', 0.0):.2f}")
                st.metric("Physics Gap %", f"{injected.get('physics_gap_pct', 0.0):.2f}")
                st.metric("Projected Loss (30d)", f"INR {injected.get('projected_loss_30d', 0.0):.0f}")

            delta = (injected.get('p_theft', 0.0) or 0.0) - (baseline.get('p_theft', 0.0) or 0.0)
            st.info(f"Change in P(Theft): {delta:.2f}")

    with analysis_tab:
        st.subheader("Validation Analysis")
        feeder_id = st.session_state.get("sim_feeder_id")
        meter_ids = st.session_state.get("sim_selected_meters", [])
        anomaly_type = st.session_state.get("sim_anomaly_type")
        severity = float(st.session_state.get("sim_severity", 0.6))
        duration_value = st.session_state.get("sim_duration_value", 24)
        duration_unit = st.session_state.get("sim_duration_unit", "hours")
        duration = pd.Timedelta(hours=duration_value) if duration_unit == "hours" else pd.Timedelta(days=duration_value)

        if st.session_state.get("sim_dirty"):
            st.warning("Scenario inputs changed. Click Run Simulation in Scenario tab before running analysis tests.")

        st.markdown("**Severity Sweep**")
        with st.form("sim_sweep_form", clear_on_submit=False):
            sweep_steps = st.slider("Severity steps", 3, 9, 5)
            min_sev, max_sev = st.slider("Severity range", 0.1, 0.9, (0.2, 0.8))
            run_sweep = st.form_submit_button("Run Severity Sweep", type="primary")

        if run_sweep:
            if not feeder_id or not meter_ids:
                st.warning("Select feeder and meters in the Scenario tab first.")
            elif st.session_state.get("sim_dirty"):
                st.warning("Scenario is not finalized. Run Simulation in Scenario tab first.")
            else:
                severities = np.linspace(min_sev, max_sev, sweep_steps).round(2).tolist()
                with st.spinner("Running severity sweep..."):
                    sweep_df = run_severity_sweep(
                        feeder_id=feeder_id,
                        meter_ids=meter_ids,
                        anomaly_type=anomaly_type,
                        severities=severities,
                        duration=duration,
                    )
                st.session_state["sim_sweep"] = sweep_df

        sweep_df = st.session_state.get("sim_sweep")
        if isinstance(sweep_df, pd.DataFrame) and not sweep_df.empty:
            st.line_chart(sweep_df.set_index('severity')['p_theft'])

        st.markdown("**Physics Consistency Test**")
        with st.form("sim_physics_form", clear_on_submit=False):
            run_physics = st.form_submit_button("Run Physics Consistency Test", type="primary")

        if run_physics:
            if not feeder_id or not meter_ids:
                st.warning("Select feeder and meters in the Scenario tab first.")
            elif st.session_state.get("sim_dirty"):
                st.warning("Scenario is not finalized. Run Simulation in Scenario tab first.")
            else:
                with st.spinner("Running physics consistency test..."):
                    test = run_physics_consistency_test(
                        feeder_id=feeder_id,
                        meter_ids=meter_ids,
                        anomaly_type=anomaly_type,
                        severity=severity,
                        duration=duration,
                    )
                st.session_state["sim_physics_test"] = test

        physics_test = st.session_state.get("sim_physics_test")
        if physics_test:
            mismatch = physics_test.get("mismatch", {}).get("summary", {})
            consistent = physics_test.get("consistent", {}).get("summary", {})
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**With mismatch**")
                st.metric("P(Theft)", f"{mismatch.get('p_theft', 0.0):.2f}")
                st.metric("Physics Gap %", f"{mismatch.get('physics_gap_pct', 0.0):.2f}")
            with c2:
                st.markdown("**Physics consistent**")
                st.metric("P(Theft)", f"{consistent.get('p_theft', 0.0):.2f}")
                st.metric("Physics Gap %", f"{consistent.get('physics_gap_pct', 0.0):.2f}")

        st.markdown("**Signal Alignment**")
        sim_result = st.session_state.get("sim_result")
        if sim_result and sim_result.get("status") == "ok":
            residuals = sim_result.get("residuals")
            timeline = sim_result.get("timeline")
            summary = sim_result.get("summary", {})
            physics_gap = summary.get("physics_gap_pct", 0.0)

            if isinstance(residuals, pd.DataFrame) and not residuals.empty and isinstance(timeline, pd.DataFrame) and not timeline.empty:
                residuals = residuals.copy()
                residuals['date'] = pd.to_datetime(residuals['timestamp']).dt.date
                daily_resid = residuals.groupby('date')['residual_kwh'].sum().reset_index()
                daily_resid['date'] = pd.to_datetime(daily_resid['date'])
                aligned = timeline.merge(daily_resid, on='date', how='left')
                aligned['physics_gap_pct'] = physics_gap

                st.line_chart(aligned.set_index('date')[['residual_kwh', 'physics_gap_pct', 'p_theft']])
                corr_resid = aligned[['residual_kwh', 'p_theft']].corr().iloc[0, 1]
                corr_phys = aligned[['physics_gap_pct', 'p_theft']].corr().iloc[0, 1]
                if pd.isna(corr_resid):
                    corr_resid = 0.0
                if pd.isna(corr_phys):
                    corr_phys = 0.0
                st.caption(f"Residual vs P(Theft) corr: {corr_resid:.2f} | Physics gap vs P(Theft) corr: {corr_phys:.2f}")
            else:
                st.info("Run a scenario to view signal alignment.")

        st.markdown("**Robustness Test**")
        with st.form("sim_robustness_form", clear_on_submit=False):
            run_robustness = st.form_submit_button("Run Robustness Test", type="primary")

        if run_robustness:
            if not feeder_id or not meter_ids:
                st.warning("Select feeder and meters in the Scenario tab first.")
            elif st.session_state.get("sim_dirty"):
                st.warning("Scenario is not finalized. Run Simulation in Scenario tab first.")
            else:
                with st.spinner("Running robustness test..."):
                    robustness = run_robustness_test(
                        feeder_id=feeder_id,
                        meter_ids=meter_ids,
                        anomaly_type=anomaly_type,
                        severity=severity,
                        duration=duration,
                        missing_ratio=float(st.session_state.get("sim_missing_ratio", 0.0)) if st.session_state.get("sim_missing_enabled") else 0.0,
                        noise_level=float(st.session_state.get("sim_noise_level", 0.0)) if st.session_state.get("sim_noise_enabled") else 0.0,
                    )
                st.session_state["sim_robustness"] = robustness

        robustness = st.session_state.get("sim_robustness")
        if robustness:
            base = robustness.get("baseline", {}).get("summary", {})
            robust = robustness.get("robust", {}).get("summary", {})
            st.metric("Baseline P(Theft)", f"{base.get('p_theft', 0.0):.2f}")
            st.metric("Robust P(Theft)", f"{robust.get('p_theft', 0.0):.2f}")
            st.info(f"Delta P(Theft): {(robust.get('p_theft', 0.0) - base.get('p_theft', 0.0)):.2f}")

        st.markdown("**Simulation History**")
        history = load_simulation_history(limit=200)
        if history is not None and not history.empty:
            st.dataframe(history, use_container_width=True)
        else:
            st.info("No simulation history available yet.")

def render_demo_mode():
    st.title("🎬 Live Investigation Demo")
    st.markdown(explanation_box(
        "Vacation Scenario", 
        "Watch how the AI handles a tricky case: A family goes on holiday. Their power drops to zero. Is it theft? Let's see the 'Detectives' in action."
    ), unsafe_allow_html=True)
    
    if st.button("Start AI Analysis"):
        agents = ["Digital Break Detector", "Peer Group Expert", "Physics Rules Engine", "Signature Matcher", "Grid Auditor"]
        results = [
            ("CLEAN", 5, "No sudden hardware break detected."),
            ("CLEAN", 12, "Neighbors are also low. Likely a holiday area."),
            ("FLAG", 60, "Usage is zero. (Suspicious, but common for holidays)"),
            ("CLEAN", 10, "No bypass pattern found."),
            ("CLEAN", 5, "The Grid energy balance is perfect.")
        ]
        
        current_score = 0
        score_placeholder = st.empty()
        
        for i, (name, res, note) in enumerate(results):
            with st.status(f"Detective {i+1}: {name} is analyzing...", expanded=True):
                time.sleep(1)
                if res == "FLAG":
                    st.error(f"Found Clue: {note}")
                else:
                    st.success(f"Clear: {note}")
                
                # Animate score
                current_score = (current_score * i + (60 if res == "FLAG" else 10)) / (i + 1)
                score_placeholder.metric("Current Consensus", f"{current_score:.1f}%")
            
        st.divider()
        if current_score < 75:
            st.success("### ✅ RESULT: NO THEFT DETECTED")
            st.write("GridSight correctly identified this as 'Normal Life Variability'. No inspector needed.")
        else:
            st.error("### 🚨 RESULT: ESCALATE TO FIELD")

def main():
    # Sidebar
    st.sidebar.markdown(f"""
        <div style="text-align:center; padding: 20px 0;">
            <h1 style="color:#00D1FF; margin:0; font-size:2rem; letter-spacing:2px;">GRIDSIGHT</h1>
            <p style="color:#94A3B8; font-size:0.8rem;">AI GRID GUARDIAN v1.0</p>
        </div>
    """, unsafe_allow_html=True)
    
    st.sidebar.markdown(explanation_box("System Status", "🟢 All Agents Online<br/>📡 200 Meters Live", "info"), unsafe_allow_html=True)
    
    demo_mode = st.sidebar.toggle("Enable Demo Simulation", value=False)
    
    if not demo_mode:
        tab1, tab2, tab3 = st.tabs(["⚡ Demand & Risk", "🔍 Theft Detective", "Simulation Lab"])
        with tab1:
            render_demand_dashboard()
        with tab2:
            render_theft_dashboard()
        with tab3:
            render_simulation_lab()
    else:
        render_demo_mode()
        
    st.sidebar.divider()
    st.sidebar.info("Assume the role of a BESCOM Supervisor. Use the tabs to manage the Bangalore grid.")

if __name__ == "__main__":
    main()

