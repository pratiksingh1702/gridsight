import streamlit as st
import os
from data_utils import load_escalation_log
import config
from update_weights import update_agent_weights

# Page Config for Mobile
st.set_page_config(page_title="GridSight Field Inspector", layout="centered")

# Custom CSS for 375px look
st.markdown("""
    <style>
    .main { max-width: 375px; margin: 0 auto; }
    </style>
    """, unsafe_allow_html=True)

def render_field_app():
    st.title("📋 Field Inspector")
    st.subheader("Assigned Cases")
    
    # 1. Load Escalated Meters
    log_path = os.path.join("data", "escalation_log.csv")
    if not os.path.exists(log_path):
        st.info("No escalated cases assigned.")
        return
        
    df = load_escalation_log(log_path)
    escalated = df[df['decision'] == "ESCALATE"]
    
    if len(escalated) == 0:
        st.info("No active escalations.")
        return
        
    selected_case = st.selectbox("Select Case", escalated['meter_id'].unique())
    
    if selected_case:
        st.divider()
        st.write(f"**Case ID:** {selected_case}")
        
        # Link to PDF
        case_files = [f for f in os.listdir("case_files") if f.startswith(f"meter_{selected_case}")]
        if case_files:
            st.success(f"PDF Case File: {case_files[0]}")
            # In a real app, use st.download_button
        else:
            st.warning("PDF not yet generated for this case.")
            
        # Checklist
        st.write("---")
        st.write("**Field Checklist**")
        st.checkbox("Physical seal intact")
        st.checkbox("No bypass wiring detected")
        st.checkbox("Voltage terminals normal")
        st.checkbox("Occupancy verified")
        
        # Outcome
        st.write("---")
        outcome = st.selectbox("Final Outcome", ["Select...", "Confirmed Theft", "Tampering Detected", "Clean / No Issue"])
        
        if st.button("Submit Report"):
            if outcome != "Select...":
                mapped = "tampered" if outcome in ["Confirmed Theft", "Tampering Detected"] else "clean"
                update_agent_weights(selected_case, mapped)
                st.success("Report submitted successfully! Learning loop updated.")
            else:
                st.error("Please select an outcome.")

if __name__ == "__main__":
    render_field_app()
