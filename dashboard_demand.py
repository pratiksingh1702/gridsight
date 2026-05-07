import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import folium_static
import plotly.graph_objects as go
import os
import warnings
from styles import explanation_box, metric_card

# Suppress iframe sandbox warnings
warnings.filterwarnings('ignore')
import config
from risk_zone import classify_risk

def get_transformer_data():
    """Simulates/Loads transformer locations and capacities."""
    data = [
        {"id": "DT_001", "name": "Indiranagar T1", "lat": 12.9716, "lon": 77.5946, "cap": 500, "feeder": "Feeder_1"},
        {"id": "DT_002", "name": "Rajajinagar T7", "lat": 12.9800, "lon": 77.5500, "cap": 400, "feeder": "Feeder_2"},
        {"id": "DT_003", "name": "Koramangala T3", "lat": 12.9300, "lon": 77.6100, "cap": 600, "feeder": "Feeder_3"},
        {"id": "DT_004", "name": "Whitefield T2", "lat": 12.9600, "lon": 77.7500, "cap": 800, "feeder": "Feeder_4"},
        {"id": "DT_005", "name": "Jayanagar T5", "lat": 12.9200, "lon": 77.5800, "cap": 450, "feeder": "Feeder_5"},
    ]
    return pd.DataFrame(data)

def render_demand_dashboard():
    st.title("⚡ Grid Health & Demand")
    st.markdown(explanation_box(
        "What am I looking at?", 
        "This map shows the 'Health' of Bangalore's electricity transformers. Think of transformers like water pipes—if too much water (electricity) flows through, they burst. We use AI to predict this 24 hours in advance."
    ), unsafe_allow_html=True)
    
    # Map
    df_dt = get_transformer_data()
    
    col_map, col_info = st.columns([2, 1])
    
    with col_map:
        st.subheader("📍 Transformer Risk Map")
        m = folium.Map(
            location=[12.9716, 77.5946], 
            zoom_start=12,
            tiles='CartoDB positron',
            prefer_canvas=True
        )
        
        for _, row in df_dt.iterrows():
            # Simulate a peak for risk zoning
            sim_peak = row['cap'] * np.random.uniform(0.5, 1.1)
            zone = classify_risk(sim_peak, row['cap'])
            color = {"GREEN": "#10B981", "YELLOW": "#FBBF24", "ORANGE": "#F59E0B", "RED": "#E11D48"}[zone]
            
            folium.CircleMarker(
                location=[row['lat'], row['lon']],
                radius=12,
                popup=f"DT: {row['id']} - {row['name']}<br>Status: {zone}",
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.7
            ).add_to(m)
        
        folium_static(m, width=700, height=500)
        
        # Legend
        st.markdown("""
            <div class="legend-container">
                <span style="color:#065F46; font-weight:600;">🟢 < 70% (Safe)</span>
                <span style="color:#92400E; font-weight:600;">🟡 70-85% (Warning)</span>
                <span style="color:#92400E; font-weight:600;">🟠 85-95% (High)</span>
                <span style="color:#9F1239; font-weight:600;">🔴 > 95% (Critical)</span>
            </div>
        """, unsafe_allow_html=True)
        
    with col_info:
        st.subheader("📊 Transformer Detail")
        selected_dt = st.selectbox("Select a location to inspect", df_dt['id'])
        
        if selected_dt:
            dt_info = df_dt[df_dt['id'] == selected_dt].iloc[0]
            st.markdown(metric_card("Rated Capacity", f"{dt_info['cap']} kW"), unsafe_allow_html=True)
            
            st.markdown(explanation_box(
                "Why this location?",
                f"We are monitoring **{dt_info['name']}**. It serves approximately 200 households. If it fails, all 200 lose power instantly.",
                type="info"
            ), unsafe_allow_html=True)

            # Forecast Plot
            st.write("### 📈 24h AI Prediction")
            time_range = pd.date_range(start="2026-05-03 00:00", periods=96, freq="15min")
            base = dt_info['cap'] * 0.6
            p50 = base + base * 0.2 * np.sin(np.linspace(0, 2*np.pi, 96)) + np.random.normal(0, 5, 96)
            p10 = p50 * 0.85
            p90 = p50 * 1.15
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=time_range, y=p90, fill=None, mode='lines', line_color='rgba(0,209,255,0.1)', name='Worst Case (P90)'))
            fig.add_trace(go.Scatter(x=time_range, y=p10, fill='tonexty', mode='lines', line_color='rgba(0,209,255,0.1)', name='Best Case (P10)'))
            fig.add_trace(go.Scatter(x=time_range, y=p50, mode='lines', line_color='#00D1FF', name='Expected Load'))
            
            fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color="#94A3B8"),
                height=300,
                margin=dict(l=0, r=0, t=0, b=0),
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)')
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Recommendation
            peak_val = p50.max()
            zone = classify_risk(peak_val, dt_info['cap'])
            rec_text = {
                "GREEN": "System stable. No action required.",
                "YELLOW": "Monitor closely. High load expected during evening peak.",
                "ORANGE": "Urgent: Prepare to transfer 15% load to backup transformer.",
                "RED": "CRITICAL: Overload imminent. Activate automatic load shedding."
            }[zone]
            
            st.markdown(explanation_box(
                "Recommendation", 
                rec_text, 
                type="info" if zone in ["GREEN", "YELLOW"] else "warning"
            ), unsafe_allow_html=True)

if __name__ == "__main__":
    render_demand_dashboard()

