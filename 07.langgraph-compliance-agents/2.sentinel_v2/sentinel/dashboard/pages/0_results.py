"""
SENTINEL — View Completed Investigation Results
"""
import os
import sys
from pathlib import Path as _Path

from dotenv import load_dotenv

_root = _Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(_root / ".env", override=True)
sys.path.insert(0, str(_root))

import asyncio
import asyncpg
import httpx
import streamlit as st
import json

st.set_page_config(
    page_title="Results — SENTINEL",
    layout="wide",
    initial_sidebar_state="expanded",
)

from sentinel.dashboard.theme import CUSTOM_CSS, render_sidebar_nav
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ── Sidebar ────────────────────────────────────────────────────────────────────
_tenant = os.getenv("DEMO_TENANT_ID", "bank-acme")
with st.sidebar:
    st.markdown(
        '<div style="padding:14px 12px 10px;">'
        '<div style="font-size:18px;font-weight:800;color:#f8fafc;letter-spacing:-0.4px;">SENTINEL</div>'
        '<div style="font-size:12px;color:#64748b;margin-top:2px;">AI Compliance Platform</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.divider()
    render_sidebar_nav(st)
    st.divider()

# ── Credentials ────────────────────────────────────────────────────────────────
api_url   = os.getenv("SENTINEL_API_URL", "http://localhost:8003")
api_key   = os.getenv("SENTINEL_API_KEY", "")
tenant_id = os.getenv("DEMO_TENANT_ID", "bank-acme")
HEADERS   = {"X-API-Key": api_key, "X-Tenant-ID": tenant_id}

try:
    _h = httpx.get(f"{api_url}/health", timeout=2)
    _api_ok = _h.status_code == 200
except Exception:
    _api_ok = False

# ── Page header ────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="page-header">
  <h1>Investigation Results</h1>
  <p>View results of completed compliance investigations with applicant data.</p>
</div>
""", unsafe_allow_html=True)

# ── Get investigation ID from user input ──────────────────────────────────────
st.markdown("### View Completed Investigation Results")

col1, col2 = st.columns([3, 1])
with col1:
    inv_id_input = st.text_input(
        "Investigation ID",
        placeholder="e.g., INV-780BC4BD45D1",
        help="Paste investigation ID from database or URL"
    )
with col2:
    st.markdown("<div style='padding-top:28px;'></div>", unsafe_allow_html=True)
    fetch_btn = st.button("Fetch Results", use_container_width=True)

# ── Or show recent completed investigations in TABLE FORMAT ──────────────────────
st.markdown("### Recent Investigation Results")

# Get list of recent completed investigations
try:
    async def get_recent_investigations():
        db_url = os.getenv("DATABASE_URL")
        conn = await asyncpg.connect(db_url)

        rows = await conn.fetch("""
            SELECT investigation_id, applicant_data, state_snapshot, status, created_at
            FROM investigations
            WHERE applicant_data IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 20
        """)

        await conn.close()
        return rows

    recent = asyncio.run(get_recent_investigations())

    # Display as table using DataFrame
    table_data = []

    for row in recent:
        try:
            inv_id = row['investigation_id']

            # Parse applicant data
            app_data = row['applicant_data']
            if isinstance(app_data, str):
                app_data = json.loads(app_data)
            applicant_name = app_data.get('applicant_name') or app_data.get('case_id') or 'Unknown'

            # Parse state snapshot — handle both dict and string (JSON) formats
            state = row['state_snapshot']
            if state is None:
                state = {}
            elif isinstance(state, str):
                try:
                    state = json.loads(state)
                except:
                    state = {}

            # Extract verdict and risk with proper fallbacks
            verdict = state.get('compliance_verdict') if state.get('compliance_verdict') else 'Pending'
            risk = state.get('regulatory_risk') if state.get('regulatory_risk') else 'N/A'
            bias = "YES" if state.get('bias_detected', False) else "NO"
            status = row['status']

            table_data.append({
                "ID": inv_id[:16],
                "Applicant": applicant_name,
                "Verdict": verdict,
                "Risk": risk,
                "Bias": bias,
                "Status": status
            })
        except Exception as e:
            # Skip rows with parsing errors but don't fail
            st.write(f"Debug: Error parsing row {inv_id}: {str(e)[:100]}" if 'inv_id' in locals() else "")

    # Display as table
    import pandas as pd
    if table_data:
        df = pd.DataFrame(table_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No investigations found")

    # Action buttons below table
    st.markdown("### Quick Actions")
    if recent:
        # Get investigation IDs only
        inv_ids = [r['investigation_id'] for r in recent]
        default_inv_id = inv_ids[0]

        # Select by Investigation ID only (no name truncation)
        selected_inv_full_id = st.selectbox(
            "Select Investigation",
            inv_ids,
            format_func=lambda x: x,
            key="inv_select_dropdown",
            index=0
        )

        st.divider()

        # Three action buttons in a row
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("View Full Report", use_container_width=True, key="btn_view_report"):
                st.session_state.selected_inv_id = selected_inv_full_id
                st.rerun()

        with col2:
            if st.button("View Provenance", use_container_width=True, key="btn_view_prov"):
                # Navigate to Provenance page with pre-filled ID
                st.session_state.provenance_inv_id = selected_inv_full_id
                st.switch_page("pages/2_provenance.py")

        with col3:
            if st.button("Send to Escalation", use_container_width=True, key="btn_escalate"):
                st.session_state.escalation_inv_id = selected_inv_full_id
                st.switch_page("pages/3_escalations.py")

except Exception as e:
    st.error(f"Could not load investigations: {str(e)[:200]}")

# ── Display selected investigation details ─────────────────────────────────────
inv_id_to_fetch = None

if "selected_inv_id" in st.session_state:
    inv_id_to_fetch = st.session_state.selected_inv_id
elif inv_id_input.strip() and fetch_btn:
    inv_id_to_fetch = inv_id_input.strip()

if inv_id_to_fetch:
    st.markdown("---")
    st.markdown(f"### Results for {inv_id_to_fetch}")

    try:
        resp = httpx.get(
            f"{api_url}/api/v1/investigations/{inv_id_to_fetch}",
            headers=HEADERS,
            timeout=10,
        )

        if resp.status_code == 200:
            inv = resp.json()

            # Check if investigation is queued - auto-execute it
            if inv.get('status') == 'queued':
                st.info("Executing queued investigation...")
                try:
                    exec_resp = httpx.post(
                        f"{api_url}/api/v1/investigations/{inv_id_to_fetch}/execute-sync",
                        json={},
                        headers=HEADERS,
                        timeout=60,
                    )
                    if exec_resp.status_code == 200:
                        st.success("Investigation executed successfully!")
                        inv = exec_resp.json()
                    else:
                        st.error(f"Failed to execute: {exec_resp.text[:200]}")
                except Exception as e:
                    st.error(f"Execution failed: {str(e)[:200]}")

            # Applicant Info
            if inv.get('applicant_data'):
                st.markdown("#### Applicant Information")
                app_data = inv['applicant_data']
                if isinstance(app_data, str):
                    app_data = json.loads(app_data)

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Name", app_data.get('applicant_name', 'N/A'))
                with col2:
                    st.metric("Age", app_data.get('age', 'N/A'))
                with col3:
                    st.metric("Race", app_data.get('race', 'N/A'))
                with col4:
                    st.metric("Income", f"${app_data.get('income', 0):,.0f}" if app_data.get('income') else 'N/A')

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Credit Score", app_data.get('credit_score', 'N/A'))
                with col2:
                    denied = app_data.get('denied', False)
                    st.metric("Denied?", "Yes" if denied else "No")
                with col3:
                    denial = app_data.get('denial_reason', 'N/A')
                    st.metric("Denial Reason", denial if denied else "N/A")
                with col4:
                    st.metric("Gender", app_data.get('gender', 'N/A'))

            # Compliance Results (from state_snapshot)
            st.markdown("#### Compliance Analysis Results")

            state = inv.get('state_snapshot') or {}
            if isinstance(state, str):
                state = json.loads(state)

            verdict = state.get('compliance_verdict', 'N/A')
            risk = state.get('regulatory_risk', 'N/A')
            bias = state.get('bias_detected', False)
            regulations = state.get('applicable_regulations', [])
            report = state.get('final_report', '')

            col1, col2, col3 = st.columns(3)
            with col1:
                verdict_color = "#10b981" if verdict == "COMPLIANT" else "#f59e0b" if verdict == "UNCERTAIN" else "#ef4444"
                st.markdown(f"<div style='text-align:center;'><div style='font-size:14px;color:#64748b;margin-bottom:8px;'>VERDICT</div><div style='font-size:24px;font-weight:700;color:{verdict_color};'>{verdict}</div></div>", unsafe_allow_html=True)
            with col2:
                risk_color = "#10b981" if risk == "LOW" else "#f59e0b" if risk == "MEDIUM" else "#ef4444"
                st.markdown(f"<div style='text-align:center;'><div style='font-size:14px;color:#64748b;margin-bottom:8px;'>RISK</div><div style='font-size:24px;font-weight:700;color:{risk_color};'>{risk}</div></div>", unsafe_allow_html=True)
            with col3:
                bias_color = "#ef4444" if bias else "#10b981"
                st.markdown(f"<div style='text-align:center;'><div style='font-size:14px;color:#64748b;margin-bottom:8px;'>BIAS DETECTED</div><div style='font-size:24px;font-weight:700;color:{bias_color};'>{'YES' if bias else 'NO'}</div></div>", unsafe_allow_html=True)

            # Applicable Regulations
            if regulations:
                st.markdown("#### Applicable Regulations")
                st.write(", ".join(regulations) if isinstance(regulations, list) else str(regulations))

            # Final Report
            if report:
                st.markdown("#### Compliance Report")
                report_text = report if isinstance(report, str) else json.dumps(report)
                st.markdown(f"""
<div style='background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:16px;line-height:1.6;color:#334155;font-size:14px;'>
{report_text.replace(chr(10), '<br/>')}
</div>
                """, unsafe_allow_html=True)

        else:
            st.error(f"Investigation not found: {resp.status_code}")

    except Exception as exc:
        st.error(f"Failed to fetch investigation: {exc}")
