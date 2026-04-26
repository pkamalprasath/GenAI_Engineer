"""Analytics page — bias patterns, cost metrics, investigation trends."""
import os
import sys
from pathlib import Path as _Path

_root = _Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_root))

from dotenv import load_dotenv
load_dotenv(_root / ".env", override=True)

import plotly.graph_objects as go
import httpx
import streamlit as st

st.set_page_config(
    page_title="Analytics — SENTINEL",
    layout="wide",
    initial_sidebar_state="expanded",
)

from sentinel.dashboard.theme import CUSTOM_CSS, PLOTLY_COLORS, plotly_layout, render_sidebar_nav

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

with st.sidebar:
    st.markdown(
        '<div style="padding:14px 12px 10px;">'
        '<div style="font-size:18px;font-weight:800;color:#f8fafc;letter-spacing:-0.4px;">SENTINEL</div>'
        '<div style="font-size:12px;color:#64748b;margin-top:3px;">AI Compliance Platform</div>'
        '</div>', unsafe_allow_html=True,
    )
    st.divider()
    render_sidebar_nav(st)
    st.divider()
    st.markdown(
        '<div style="padding:2px 4px 8px;">'
        '<div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;'
        'letter-spacing:0.8px;margin-bottom:5px;">Active Tenant</div>'
        f'<div style="font-size:14px;color:#e2e8f0;font-weight:600;">{os.getenv("DEMO_TENANT_ID","bank-acme")}</div>'
        '</div>', unsafe_allow_html=True,
    )

st.markdown("""
<div class="page-header">
    <h1>Analytics &amp; Insights</h1>
    <p>Bias patterns, cost metrics, and compliance trends across all investigations.</p>
</div>
""", unsafe_allow_html=True)

api_url = st.session_state.get("api_url") or os.getenv("SENTINEL_API_URL", "http://localhost:8003")
api_key = st.session_state.get("api_key") or os.getenv("SENTINEL_API_KEY", "")
tenant_id = st.session_state.get("tenant_id") or os.getenv("DEMO_TENANT_ID", "bank-acme")
HEADERS = {"X-API-Key": api_key, "X-Tenant-ID": tenant_id}

period = st.selectbox("Time Period", [7, 14, 30, 90], format_func=lambda x: f"Last {x} days")

# Demo analytics data — replaced by real API data when connected
DEMO_DATA = {
    "total_investigations": 47,
    "compliance_rate": 0.74,
    "bias_detection_rate": 0.32,
    "avg_cost_usd": 0.0187,
    "hitl_rate": 0.28,
}
DEMO_COSTS = {
    "discovery_agent": 0.0012,
    "investigation_agent": 0.0048,
    "legal_agent": 0.0061,
    "bias_detection_agent": 0.0038,
    "report_agent": 0.0142,
}
DEMO_BIAS = {"zip_code_census_tract": 0.23, "age_group": 0.11, "gender": 0.04}

live_data = False
try:
    resp = httpx.get(f"{api_url}/api/v1/analytics", params={"days": period}, headers=HEADERS, timeout=5)
    if resp.status_code == 200:
        analytics = resp.json()
        live_data = True
    else:
        analytics = DEMO_DATA
except Exception:
    analytics = DEMO_DATA
if not live_data:
    st.info("Showing demo data — connect API for live metrics")

# ── KPI cards ──────────────────────────────────────────────────────────────────
col1, col2, col3, col4, col5 = st.columns(5)
metrics = [
    (col1, "Total Investigations", analytics.get("total_investigations", 0), ""),
    (col2, "Compliance Rate", f"{analytics.get('compliance_rate',0)*100:.0f}%", ""),
    (col3, "Bias Detected", f"{analytics.get('bias_detection_rate',0)*100:.0f}%", ""),
    (col4, "Avg Cost/Investigation", f"${analytics.get('avg_cost_usd',0):.4f}", ""),
    (col5, "HITL Escalation Rate", f"{analytics.get('hitl_rate',0)*100:.0f}%", ""),
]
for col, label, value, delta in metrics:
    with col:
        st.metric(label, value)

st.divider()

# ── Cost breakdown by agent ────────────────────────────────────────────────────
col1, col2 = st.columns(2)
with col1:
    st.markdown("#### Cost by Agent")
    fig = go.Figure(go.Bar(
        x=list(DEMO_COSTS.keys()),
        y=list(DEMO_COSTS.values()),
        marker_color=PLOTLY_COLORS,
    ))
    fig.update_layout(**plotly_layout("USD per Investigation"))
    fig.update_xaxes(tickangle=30)
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.markdown("#### Bias Disparity by Dimension")
    dims = list(DEMO_BIAS.keys())
    vals = list(DEMO_BIAS.values())
    colors = ["#fc8181" if v > 0.15 else "#48bb78" for v in vals]
    fig2 = go.Figure(go.Bar(x=dims, y=vals, marker_color=colors))
    fig2.add_hline(y=0.15, line_dash="dash", line_color="#ed8936",
                   annotation_text="Alert threshold (15%)")
    fig2.update_layout(**plotly_layout("Approval Rate Disparity"))
    st.plotly_chart(fig2, use_container_width=True)

# ── Compliance trend ────────────────────────────────────────────────────────────
trend_label = "#### Compliance Trend" + ("" if live_data else " (Demo)")
st.markdown(trend_label)
weeks = ["Week 1", "Week 2", "Week 3", "Week 4"]
compliance = [0.68, 0.71, 0.74, 0.76]
violations = [0.32, 0.29, 0.26, 0.24]
fig3 = go.Figure()
fig3.add_trace(go.Scatter(x=weeks, y=compliance, name="Compliant", fill="tonexty",
                           line_color=PLOTLY_COLORS[1]))
fig3.add_trace(go.Scatter(x=weeks, y=violations, name="Violation/Uncertain",
                           fill="tozeroy", line_color=PLOTLY_COLORS[3]))
fig3.update_layout(**plotly_layout("Compliance Rate Over Time"))
st.plotly_chart(fig3, use_container_width=True)
