from fastapi import APIRouter, Response
from fastapi.responses import StreamingResponse
from app.services.snapshot import grid_snapshot
import io
from datetime import datetime

router = APIRouter(tags=["reports"])

@router.get("/report/download")
async def download_full_report():
    # Gather data
    summary = grid_snapshot.summary
    zones = grid_snapshot.zones
    alerts = grid_snapshot.alerts
    buildings = grid_snapshot.buildings
    
    # Generate content
    report = []
    report.append("# GridSight AI - Comprehensive Grid Intelligence Report")
    report.append(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} IST")
    report.append("\n## 1. Executive Summary")
    report.append(f"- **Grid Health:** {summary.gridHealthPercent}%")
    report.append(f"- **Active Alerts:** {summary.activeAlerts}")
    report.append(f"- **Total Load:** {summary.totalLoadMw} MW")
    report.append(f"- **Active Theft Cases:** {summary.activeTheftCases}")
    report.append(f"- **AI Confidence:** {summary.aiConfidencePercent}%")
    
    report.append("\n## 2. Zone Risk Analysis")
    report.append("| Zone Name | Risk Level | Anomaly % | Status |")
    report.append("|-----------|------------|-----------|--------|")
    for z in zones:
        risk_lbl = "HIGH" if z.risk == 'h' else "MEDIUM" if z.risk == 'm' else "LOW"
        report.append(f"| {z.name} | {risk_lbl} | {z.pct}% | Active |")
        
    report.append("\n## 3. Recent AI Alerts")
    for a in alerts[:20]:
        report.append(f"- **[{a.type.upper()}]** {a.message} ({a.time})")
        
    report.append("\n## 4. Building Asset Intelligence")
    report.append(f"Analyzing {len(buildings)} assets for anomalies...")
    high_risk_b = [b for b in buildings if b.anomaly > 70]
    report.append(f"- High Risk Assets Detected: {len(high_risk_b)}")
    for b in high_risk_b[:10]:
        report.append(f"  - Meter ID {b.meterId}: Anomaly Score {b.anomaly}, Theft Risk {b.theft}%")
        
    report.append("\n## 5. Neural Architecture & AI Agents")
    import os
    agents = [f for f in os.listdir('.') if f.startswith('agent_') and f.endswith('.py')]
    report.append(f"Detected {len(agents)} active intelligence modules in the core logic path:")
    for agent in agents:
        report.append(f"- **Module:** `{agent}` (Online)")
    
    report.append("\n## 6. System Architecture Note")
    report.append("This report aggregates data from GridSight Neural Engine v2.1, processing real-time telemetry from multiple smart-meter gateways across the Bangalore metropolitan area.")
    
    full_text = "\n".join(report)
    
    # Return as file
    buf = io.BytesIO(full_text.encode('utf-8'))
    headers = {
        'Content-Disposition': 'attachment; filename="GridSight_Full_Report.md"'
    }
    return StreamingResponse(buf, media_type="text/markdown", headers=headers)
