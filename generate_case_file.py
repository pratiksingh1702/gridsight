import os
import json
import pandas as pd
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Image, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import logging
from datetime import datetime
import config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def _parse_field(value):
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    try:
        return json.loads(value)
    except Exception:
        return {}


def generate_case_file(meter_id: str, fusion_result: dict = None):
    """
    Generates a PDF Inspection Case File for an escalated meter.
    """
    if fusion_result is None:
        from fusion_engine import evaluate_meter
        fusion_result = evaluate_meter(meter_id)
        
    logger.info(f"[{meter_id}] Generating PDF Case File...")
    
    os.makedirs("case_files", exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    pdf_path = os.path.join("case_files", f"meter_{meter_id}_{date_str}.pdf")
    
    # 1. Load Metadata
    metadata = pd.read_csv(os.path.join("data", "feeder_metadata.csv"))
    m_meta = metadata[metadata['meter_id'] == meter_id].iloc[0]
    
    # 2. Generate Plot
    plot_path = os.path.join("case_files", f"plot_{meter_id}.png")
    df = pd.read_csv(os.path.join("data", "processed", "meter_readings", f"{meter_id}.csv"))
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    daily_kwh = df.groupby(df['timestamp'].dt.date)['kwh'].sum()
    
    plt.figure(figsize=(8, 4))
    plt.plot(daily_kwh.index, daily_kwh.values, label="Target Meter", color='red')
    # Dummy peer median for plot
    plt.plot(daily_kwh.index, daily_kwh.values * 1.5 + 2, label="Peer Median", color='blue', alpha=0.5)
    plt.title(f"Consumption Trend: {meter_id}")
    plt.xlabel("Date")
    plt.ylabel("Daily kWh")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig(plot_path)
    plt.close()
    
    # 3. Create PDF
    doc = SimpleDocTemplate(pdf_path, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []
    
    # Header
    elements.append(Paragraph(f"<b>GridSight Inspection Case File</b>", styles['Title']))
    elements.append(Paragraph(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
    elements.append(Spacer(1, 12))
    
    # Section 1: Meter Info
    elements.append(Paragraph("<b>1. Consumer Information</b>", styles['Heading2']))
    info_data = [
        ["Meter ID", meter_id],
        ["Consumer Name", m_meta['name']],
        ["Address", m_meta['address']],
        ["Feeder ID", m_meta['feeder_id']],
        ["Tariff Category", m_meta['type'].upper()]
    ]
    t1 = Table(info_data, colWidths=[150, 300])
    t1.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.grey)]))
    elements.append(t1)
    elements.append(Spacer(1, 12))
    
    # Section 2: Consumption Graph
    elements.append(Paragraph("<b>2. Consumption Analysis (Last 90 Days)</b>", styles['Heading2']))
    elements.append(Image(plot_path, width=400, height=200))
    elements.append(Spacer(1, 12))
    
    # Section 3: Agent Evidence
    elements.append(Paragraph("<b>3. Detection Evidence</b>", styles['Heading2']))
    agent_scores = _parse_field(fusion_result.get('agent_scores'))
    evidence_data = [["Agent", "Score", "Status"]]
    for agent, score in agent_scores.items():
        status = "FIRING" if score >= config.AGENT_FIRE_THRESHOLD else "CLEAN"
        evidence_data.append([agent.replace("_", " ").title(), f"{score:.1f}", status])
        
    t2 = Table(evidence_data, colWidths=[150, 100, 100])
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey)
    ]))
    elements.append(t2)
    elements.append(Spacer(1, 12))
    
    # Section 4: Checklist
    elements.append(Paragraph("<b>4. Field Inspection Checklist</b>", styles['Heading2']))
    checklist = [
        "[] Verify physical meter seal integrity.",
        "[] Check for external bypass wiring (LT line tapping).",
        "[] Inspect meter for magnet placement marks.",
        "[] Test voltage at meter terminals vs nearby poles.",
        "[] Confirm occupancy status with neighbours."
    ]
    for item in checklist:
        elements.append(Paragraph(item, styles['Normal']))
    elements.append(Spacer(1, 12))
    
    # Section 5: Summary
    elements.append(Paragraph("<b>5. Composite Risk Summary</b>", styles['Heading2']))
    theft_class = _parse_field(fusion_result.get('theft_class'))
    economic = _parse_field(fusion_result.get('economic'))
    decision_details = _parse_field(fusion_result.get('decision_details'))

    summary_data = [
        ["P(Theft)", f"{float(fusion_result.get('p_theft', 0.0)):.2f}"],
        ["Theft Class", theft_class.get('class', 'unknown')],
        ["Expected Value", f"INR {economic.get('expected_value', 0.0):.0f}"],
        ["Projected 30d Loss", f"INR {economic.get('projected_loss_30d_value', 0.0):.0f}"],
        ["ROI", f"{economic.get('roi', 0.0):.2f}"],
        ["Decision", decision_details.get('decision', fusion_result.get('decision'))],
        ["Urgency", decision_details.get('urgency', 'NA')]
    ]
    t3 = Table(summary_data, colWidths=[150, 150])
    t3.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.grey)]))
    elements.append(t3)
    
    # Build
    doc.build(elements)
    logger.info(f"PDF generated: {pdf_path}")
    
    # Cleanup plot
    if os.path.exists(plot_path):
        os.remove(plot_path)
        
    return pdf_path

if __name__ == "__main__":
    # Smoke test
    dummy_res = {
        "weighted_score": 84.5,
        "decision": "ESCALATE",
        "agent_scores": {"cusum": 80, "peer": 75, "rules": 0, "patterns": 90, "feeder_balance": 0, "isolation_forest": 0}
    }
    generate_case_file("meter_000", dummy_res)
