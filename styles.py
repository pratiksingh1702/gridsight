# styles.py

MAIN_CSS = """
<style>
    /* Premium Font */
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&family=Fraunces:opsz,wght@9..144,600&display=swap');

    html, body, [class*="css"] {
        font-family: 'Space Grotesk', sans-serif;
    }

    h1, h2, h3, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        font-family: 'Fraunces', serif;
        letter-spacing: 0.3px;
    }

    /* Light Mode Background */
    .stApp {
        background: radial-gradient(circle at 10% 20%, #FFF7ED 0%, #F8FAFC 45%, #EEF2FF 100%);
        color: #1E293B;
    }

    /* Soft Cards */
    .metric-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        box-shadow: 0 10px 20px -12px rgba(15, 23, 42, 0.18);
        border-radius: 14px;
        padding: 24px;
        text-align: center;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    
    .metric-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 18px 30px -12px rgba(15, 23, 42, 0.25);
        border-color: #0EA5A4;
    }

    .metric-value {
        font-size: 2.6rem;
        font-weight: 700;
        margin: 8px 0;
        color: #0F172A;
    }

    .metric-label {
        font-size: 0.85rem;
        color: #64748B;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1.4px;
    }

    /* Sidebar Styling - Light */
    section[data-testid="stSidebar"] {
        background-color: #FFFFFF !important;
        border-right: 1px solid #E2E8F0;
    }

    /* Custom Buttons - High Contrast */
    .stButton>button {
        background: #0F172A;
        color: white;
        border: none;
        border-radius: 10px;
        padding: 0.6rem 1.2rem;
        font-weight: 600;
        transition: all 0.2s ease;
    }

    .stButton>button:hover {
        background: #334155;
        color: white;
        box-shadow: 0 4px 12px rgba(15, 23, 42, 0.15);
    }

    /* Info Boxes - Softer colors for Light Mode */
    .info-box {
        background: #ECFDF5;
        border-left: 4px solid #0EA5A4;
        padding: 16px;
        border-radius: 6px 10px 10px 6px;
        margin: 16px 0;
    }

    .warning-box {
        background: #FFFBEB;
        border-left: 4px solid #F97316;
        padding: 16px;
        border-radius: 6px 10px 10px 6px;
        margin: 16px 0;
    }

    /* Legend styling */
    .legend-container {
        display:flex; 
        justify-content:space-around; 
        background:#FFFFFF; 
        padding:12px; 
        border-radius:10px; 
        border:1px solid #E2E8F0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }

    /* Darker table text for light mode */
    [data-testid="stTable"] td, [data-testid="stDataFrame"] td {
        color: #1E293B !important;
    }
</style>
"""

def metric_card(label, value, delta=None):
    delta_html = f"<div style='color:#10B981;font-size:0.8rem;font-weight:600;'>↑ {delta}</div>" if delta else ""
    return f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
        {delta_html}
    </div>
    """

def explanation_box(title, text, type="info"):
    cls = "info-box" if type == "info" else "warning-box"
    icon = "ℹ️" if type == "info" else "🚨"
    title_color = "#1E40AF" if type == "info" else "#9F1239"
    text_color = "#334155"
    return f"""
    <div class="{cls}">
        <b style="font-size:1.1rem; color:{title_color};">{icon} {title}</b><br/>
        <span style="font-size:0.95rem; color:{text_color}; line-height:1.5;">{text}</span>
    </div>
    """

