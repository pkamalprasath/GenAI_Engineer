"""
Escalations page — Human-in-the-Loop review queue.
Compliance officers approve, modify, or reject AI-generated reports.
"""
import os
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_root))

from dotenv import load_dotenv
load_dotenv(_root / ".env", override=True)

import httpx
import streamlit as st

st.set_page_config(
    page_title="Escalations — SENTINEL",
    layout="wide",
    initial_sidebar_state="expanded",
)

from sentinel.dashboard.theme import CUSTOM_CSS, render_sidebar_nav

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

with st.sidebar:
    st.markdown(
        '<div style="padding:14px 12px 10px;">'
        '<div style="font-size:18px;font-weight:800;color:#f8fafc;letter-spacing:-0.4px;">SENTINEL</div>'
        '<div style="font-size:12px;color:#64748b;margin-top:3px;">AI Compliance Platform</div>'
        '</div>', unsafe_allow_html=True,
    )
    st.divider()
    render_sidebar_nav(st, "escalations")
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
    <h1>Escalation Queue</h1>
    <p>Investigations requiring human review before reports are finalized.</p>
</div>
""", unsafe_allow_html=True)

api_url   = st.session_state.get("api_url")   or os.getenv("SENTINEL_API_URL", "http://localhost:8003")
api_key   = st.session_state.get("api_key")   or os.getenv("SENTINEL_API_KEY", "")
tenant_id = st.session_state.get("tenant_id") or os.getenv("DEMO_TENANT_ID", "bank-acme")
HEADERS   = {"X-API-Key": api_key, "X-Tenant-ID": tenant_id}

DEMO_ESCALATIONS = [
    {
        "escalation_id": "ESC-001",
        "investigation_id": "INV-ABC123",
        "reason": "Bias confidence 0.82 below HITL threshold 0.85",
        "draft_report": (
            "## Compliance Investigation Report\n\n"
            "**Verdict:** REVIEW REQUIRED\n\n"
            "Investigation found 23% disparity in approval rates across zip code census tracts. "
            "Statistical significance confirmed (n=47, p<0.05).\n\n"
            "**Applicable Regulation:** ECOA Section 202.6\n\n"
            "**Recommended Action:** Legal review before regulatory response."
        ),
        "status": "pending",
        "created_at": "2025-04-20T10:30:00Z",
    },
    {
        "escalation_id": "ESC-002",
        "investigation_id": "INV-DEF456",
        "reason": "Regulatory risk: HIGH — ECOA potential violation detected",
        "draft_report": (
            "## Compliance Investigation Report\n\n"
            "**Verdict:** NON-COMPLIANT\n\n"
            "Fair lending analysis identified denial rate disparity for age group 65+ vs 25-45 cohort. "
            "Disparity: 31%.\n\n"
            "**Applicable Regulation:** Fair Housing Act, ECOA\n\n"
            "**Recommended Action:** Immediate remediation required."
        ),
        "status": "pending",
        "created_at": "2025-04-20T09:15:00Z",
    },
]

# ── Fetch escalations ──────────────────────────────────────────────────────────
using_demo = False
try:
    resp = httpx.get(f"{api_url}/api/v1/escalations", headers=HEADERS, timeout=5)
    if resp.status_code == 200:
        raw = resp.json()
        escalations = []
        for e in raw:
            reason = e.get("reason", "")
            report = e.get("draft_report", "")
            if "AuthenticationError" in reason or "AuthenticationError" in report:
                e = dict(e)
                e["reason"] = "Report generation encountered an LLM error — human review required"
                e["draft_report"] = (
                    "The automated report could not be generated due to an LLM authentication error. "
                    "Please review the raw investigation data and write your assessment below."
                )
            escalations.append(e)
    else:
        escalations = DEMO_ESCALATIONS
        using_demo = True
except Exception:
    escalations = DEMO_ESCALATIONS
    using_demo = True

if using_demo:
    st.info("Using demo data — connect API for live escalations")

pending = [e for e in escalations if e.get("status") == "pending"]

# Resolved count from analytics — API only returns pending_human records
total_investigations = 0
hitl_rate            = 0.0
try:
    ar = httpx.get(f"{api_url}/api/v1/analytics", params={"days": 90}, headers=HEADERS, timeout=5)
    if ar.status_code == 200:
        ad = ar.json()
        total_investigations = ad.get("total_investigations", 0)
        hitl_rate            = ad.get("hitl_rate", 0.0)
except Exception:
    pass

total_escalated = round(total_investigations * hitl_rate) if total_investigations else len(pending)
resolved_count  = max(0, total_escalated - len(pending))
res_rate        = resolved_count / max(total_escalated, 1) * 100

# ── KPI metrics ────────────────────────────────────────────────────────────────
col_m1, col_m2, col_m3, col_m4 = st.columns(4)
col_m1.metric("Pending Reviews",  len(pending))
col_m2.metric("Total Escalated",  total_escalated)
col_m3.metric("Resolved",         resolved_count)
col_m4.metric("Resolution Rate",  f"{res_rate:.0f}%")

st.markdown("---")

if not pending:
    st.success("No pending escalations — all investigations complete.")
    st.stop()

# ── Pagination ────────────────────────────────────────────────────────────────
PAGE_SIZE = 10
total_pages = max(1, (len(pending) + PAGE_SIZE - 1) // PAGE_SIZE)

col_pg1, col_pg2, col_pg3 = st.columns([2, 1, 2])
with col_pg2:
    page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1, label_visibility="collapsed")

with col_pg1:
    start_idx = (page - 1) * PAGE_SIZE
    end_idx   = min(start_idx + PAGE_SIZE, len(pending))
    st.markdown(
        f'<div style="color:#64748b;font-size:13px;padding-top:6px;">'
        f'Showing {start_idx+1}–{end_idx} of {len(pending)} pending</div>',
        unsafe_allow_html=True,
    )

page_items = pending[start_idx:end_idx]

# ── Action labels ──────────────────────────────────────────────────────────────
ACTION_LABELS = {
    "approve_draft":       "Approve as-is",
    "modify_response":     "Modify response",
    "close_investigation": "Close without report",
}

# ── Render each escalation ─────────────────────────────────────────────────────
for esc in page_items:
    esc_id  = esc.get("escalation_id", "ESC-???")
    inv_id  = esc.get("investigation_id", "")
    created = esc.get("created_at", "")[:10]
    reason  = esc.get("reason", "Requires human review")
    report  = esc.get("draft_report") or "No draft report available."

    with st.expander(f"{esc_id}  |  {created}", expanded=(page == 1 and page_items.index(esc) == 0)):

        # Reason banner
        st.markdown(
            f'<div style="background:#fffbeb;border:1px solid #fcd34d;border-radius:8px;'
            f'padding:10px 16px;margin-bottom:12px;font-size:14px;color:#92400e;">'
            f'<strong>Escalation Reason:</strong> {reason}</div>',
            unsafe_allow_html=True,
        )
        st.caption(f"Investigation ID: {inv_id}")
        st.divider()

        left, right = st.columns([3, 2], gap="large")

        # ── LEFT: Report viewer ────────────────────────────────────────────────
        with left:
            st.markdown("**AI Draft Report**")
            st.markdown(report)

        # ── RIGHT: Decision form ───────────────────────────────────────────────
        with right:
            st.markdown("**Your Decision**")
            action = st.radio(
                "Action",
                list(ACTION_LABELS.keys()),
                key=f"action_{esc_id}",
                format_func=lambda x: ACTION_LABELS[x],
            )
            reviewer_note = st.text_area(
                "Reviewer Comment (required)",
                key=f"note_{esc_id}",
                placeholder="Explain your decision for the audit log...",
                height=100,
            )
            reviewer_id = st.text_input(
                "Your ID",
                key=f"rid_{esc_id}",
                placeholder="e.g. compliance-officer-01",
            )

            if st.button("Submit Decision", key=f"btn_{esc_id}"):
                if not reviewer_note.strip() or not reviewer_id.strip():
                    st.error("Reviewer comment and ID are required")
                else:
                    payload = {
                        "response":    reviewer_note,
                        "action":      action,
                        "reviewer_id": reviewer_id,
                    }
                    with st.spinner("Submitting decision…"):
                        try:
                            r = httpx.post(
                                f"{api_url}/api/v1/escalations/{inv_id}/resolve",
                                json=payload,
                                headers=HEADERS,
                                timeout=15,
                            )
                            if r.status_code == 200:
                                st.success(f"Decision recorded — {ACTION_LABELS.get(action, action)}")
                                st.rerun()
                            else:
                                st.error(f"API error: {r.text[:200]}")
                        except Exception as exc:
                            st.error(f"Submit failed: {exc}")
