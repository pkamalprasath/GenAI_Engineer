"""SENTINEL Streamlit Dashboard — home page."""
import os
import sys
from pathlib import Path

_root = str(Path(__file__).resolve().parent.parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env", override=True)

st.set_page_config(
    page_title="SENTINEL — AI Compliance Platform",
    layout="wide",
    initial_sidebar_state="expanded",
)

from sentinel.dashboard.theme import CUSTOM_CSS, render_sidebar_nav
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        '<div style="padding:14px 12px 10px;">'
        '<div style="font-size:18px;font-weight:800;color:#f8fafc;'
        'letter-spacing:-0.4px;line-height:1.2;">SENTINEL</div>'
        '<div style="font-size:12px;color:#64748b;margin-top:3px;font-weight:400;">'
        'AI Compliance Platform</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.divider()

    st.session_state.api_url   = os.getenv("SENTINEL_API_URL", "http://localhost:8003")
    st.session_state.api_key   = os.getenv("SENTINEL_API_KEY", "")
    st.session_state.tenant_id = os.getenv("DEMO_TENANT_ID", "bank-acme")

    with st.expander("Connection", expanded=False):
        st.session_state.api_url   = st.text_input("API URL",  value=st.session_state.api_url)
        st.session_state.api_key   = st.text_input("API Key",  value=st.session_state.api_key, type="password")
        st.session_state.tenant_id = st.text_input("Tenant",   value=st.session_state.tenant_id)

    st.divider()
    render_sidebar_nav(st)
    st.divider()
    st.markdown(
        '<div style="padding:2px 4px 8px;">'
        '<div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;'
        'letter-spacing:0.8px;margin-bottom:5px;">Active Tenant</div>'
        f'<div style="font-size:14px;color:#e2e8f0;font-weight:600;">{st.session_state.tenant_id}</div>'
        '</div>',
        unsafe_allow_html=True,
    )

# ── API health ─────────────────────────────────────────────────────────────────
status_ok = False
try:
    r = httpx.get(f"{st.session_state.api_url}/health", timeout=3)
    status_ok = r.status_code == 200
except Exception:
    pass

# ── Page header ────────────────────────────────────────────────────────────────
dot   = "#10b981" if status_ok else "#ef4444"
btxt  = "#10b981" if status_ok else "#ef4444"
bbg   = "rgba(16,185,129,0.10)" if status_ok else "rgba(239,68,68,0.08)"
bbrd  = "rgba(16,185,129,0.25)" if status_ok else "rgba(239,68,68,0.25)"
badge = (
    f'<span style="display:inline-flex;align-items:center;gap:5px;font-size:13px;'
    f'font-weight:600;color:{btxt};background:{bbg};border:1px solid {bbrd};'
    f'border-radius:20px;padding:3px 12px;">'
    f'<span style="width:7px;height:7px;border-radius:50%;background:{dot};display:inline-block;"></span>'
    f'{"API Online" if status_ok else "API Offline"}</span>'
)
st.markdown(f"""
<div class="page-header">
  <h1>AI Compliance Investigation Platform</h1>
  <p>Autonomous multi-agent system for regulatory compliance, bias detection, and regulator-ready audit reporting.</p>
  <div style="margin-top:10px;display:flex;align-items:center;gap:10px;">
    {badge}
    <span style="font-size:13px;color:#94a3b8;">v1.0.0 &nbsp;·&nbsp; Tenant:
      <strong style="color:#475569;">{st.session_state.tenant_id}</strong></span>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Navigation cards — equal height, button inside card ────────────────────────
CARDS = [
    ("/investigate", "Investigation",
     "Submit compliance queries and watch the multi-agent pipeline analyse decisions in real time."),
    ("/provenance",  "Provenance",
     "Visualise AI decision chains and verify cryptographic integrity of provenance nodes."),
    ("/escalations", "Escalations",
     "Review cases flagged for human-in-the-loop approval, modification, or override."),
    ("/analytics",   "Analytics",
     "Explore bias patterns, cost breakdowns, and compliance trends across all investigations."),
]

cols = st.columns(4, gap="medium")
for col, (url, title, desc) in zip(cols, CARDS):
    with col:
        st.markdown(f"""
<a href="{url}" target="_self" style="text-decoration:none;">
  <div class="nav-card">
    <div class="nav-card-title">{title}</div>
    <div class="nav-card-desc">{desc}</div>
    <div class="nav-card-btn">Open {title} &rarr;</div>
  </div>
</a>
""", unsafe_allow_html=True)
