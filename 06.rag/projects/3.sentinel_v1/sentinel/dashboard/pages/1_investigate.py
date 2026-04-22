"""
SENTINEL — Investigate Page
Split-panel: left = query form, right = live agent progress + results.
"""
import os
import sys
import time
from datetime import date
from pathlib import Path as _Path

from dotenv import load_dotenv

_root = _Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(_root / ".env", override=True)
sys.path.insert(0, str(_root))

import httpx
import streamlit as st

st.set_page_config(
    page_title="Investigate — SENTINEL",
    layout="wide",
    initial_sidebar_state="expanded",
)

from sentinel.dashboard.theme import CUSTOM_CSS, render_sidebar_nav
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ── Sidebar ─────────────────────────────────────────────────────────────────────
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
    st.markdown(
        '<div style="padding:2px 4px 8px;">'
        '<div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;'
        'letter-spacing:0.8px;margin-bottom:5px;">Active Tenant</div>'
        f'<div style="font-size:14px;color:#e2e8f0;font-weight:600;">{_tenant}</div>'
        '</div>',
        unsafe_allow_html=True,
    )

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

# ── Page header + API badge (single block — avoids Streamlit inter-element gap) ─
_dot  = "#10b981" if _api_ok else "#ef4444"
_ltxt = "#10b981" if _api_ok else "#ef4444"
_lbgc = "rgba(16,185,129,0.10)" if _api_ok else "rgba(239,68,68,0.08)"
_lbrc = "rgba(16,185,129,0.25)" if _api_ok else "rgba(239,68,68,0.25)"
_badge = (
    f'<span style="display:inline-flex;align-items:center;gap:5px;font-size:13px;'
    f'font-weight:600;color:{_ltxt};background:{_lbgc};border:1px solid {_lbrc};'
    f'border-radius:20px;padding:3px 11px;">'
    f'<span style="width:7px;height:7px;border-radius:50%;background:{_dot};display:inline-block;"></span>'
    f'{"API Online" if _api_ok else "API Offline"}</span>'
)
st.markdown(f"""
<div class="page-header">
  <h1>Run Investigation</h1>
  <p>Submit a compliance query and watch the multi-agent pipeline analyse decisions,
     apply regulations, and detect bias — all in real time.</p>
  <div style="margin-top:10px;">{_badge}</div>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SPLIT LAYOUT  (left 4/10 = form, right 6/10 = progress)
# ══════════════════════════════════════════════════════════════════════════════
left_col, right_col = st.columns([4, 6], gap="large")

# ─────────────────────────────────────────────────────────────────────────────
# LEFT — Query Form
# ─────────────────────────────────────────────────────────────────────────────
with left_col:
    with st.form("inv_form", clear_on_submit=False):
        domain = st.selectbox("Domain", ["finance", "pharma", "generic"])
        query  = st.text_area(
            "Investigation Query",
            value="Review credit decisions from Jan 3–10 2024 for fair lending compliance",
            height=100,
            placeholder="e.g. Review credit decisions Jan 3–10 2024 for fair lending compliance",
        )
        col_a, col_b = st.columns(2)
        with col_a:
            date_from = st.date_input("From", value=date(2024, 1, 3))
        with col_b:
            date_to   = st.date_input("To",   value=date(2024, 1, 10))

        days_span = (date_to - date_from).days if date_to >= date_from else 0
        if days_span > 30:
            st.warning(f"{days_span}-day range — consider under 30 days for faster results.")
        elif days_span > 0:
            st.markdown(
                f'<div style="font-size:13px;color:#059669;background:#f0fdf4;'
                f'border:1px solid #bbf7d0;border-radius:7px;padding:8px 12px;margin:6px 0;">'
                f'<strong>{days_span}-day window</strong> — good range for fast results.</div>',
                unsafe_allow_html=True,
            )

        st.markdown('<div style="margin-top:10px;"></div>', unsafe_allow_html=True)
        submitted = st.form_submit_button(
            "Run Investigation" if _api_ok else "API Offline — Cannot Submit",
            use_container_width=True,
            disabled=not _api_ok,
        )

    if not _api_ok:
        st.markdown("""
<div style="margin-top:16px;background:#fef2f2;border:1px solid #fecaca;
            border-radius:12px;padding:16px 20px;">
  <div style="font-size:13px;font-weight:700;color:#dc2626;margin-bottom:6px;">
    API Server Not Running</div>
  <div style="font-size:13px;color:#7f1d1d;line-height:1.6;">
    Start the API before submitting an investigation:
  </div>
  <code style="display:block;margin-top:10px;background:#fff1f2;border:1px solid #fecaca;
               border-radius:7px;padding:10px 14px;font-size:12px;color:#9f1239;
               font-family:monospace;">
    cd projects/sentinel<br>
    uvicorn sentinel.api.main:app --port 8003 --reload
  </code>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# RIGHT — Progress Panel
# ─────────────────────────────────────────────────────────────────────────────
with right_col:

    # Handle form submit
    if submitted and query.strip():
        pii_kw = ["ssn", "social security", "name:", "@", "phone", "dob", "born"]
        if any(k in query.lower() for k in pii_kw):
            st.markdown(
                '<div class="pii-warning">PII detected — will be redacted before processing.</div>',
                unsafe_allow_html=True,
            )
        try:
            r = httpx.post(
                f"{api_url}/api/v1/investigations",
                json={"query": query.strip(), "date_from": str(date_from),
                      "date_to": str(date_to), "domain": domain, "trigger_mode": "reactive"},
                headers=HEADERS, timeout=30,
            )
            if r.status_code == 202:
                inv = r.json()
                st.session_state.active_investigation_id  = inv["investigation_id"]
                st.session_state.investigation_start_time = time.time()
                st.session_state.investigation_query      = query.strip()
            else:
                st.error(f"API error {r.status_code}: {r.text[:200]}")
        except Exception as exc:
            st.error(f"Connection failed: {exc}")

    # ── Idle placeholder ───────────────────────────────────────────────────────
    if "active_investigation_id" not in st.session_state:
        st.markdown("""
<div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:14px;
            min-height:480px;display:flex;align-items:center;justify-content:center;">
  <div style="text-align:center;padding:52px 36px;">
    <div style="width:64px;height:64px;background:#f1f5f9;border-radius:50%;
                display:flex;align-items:center;justify-content:center;margin:0 auto 20px;">
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none"
           stroke="#94a3b8" stroke-width="1.6" stroke-linecap="round">
        <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
      </svg>
    </div>
    <div style="font-size:17px;font-weight:700;color:#334155;margin-bottom:10px;">
      No investigation running</div>
    <div style="font-size:14px;color:#94a3b8;max-width:280px;margin:0 auto;line-height:1.5;">
      Configure a query on the left and click
      <strong style="color:#475569;">Run Investigation</strong> to start.
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

    # ── Active investigation ────────────────────────────────────────────────────
    else:
        inv_id     = st.session_state.active_investigation_id
        start_time = st.session_state.get("investigation_start_time", time.time())
        inv_query  = st.session_state.get("investigation_query", "")

        st.markdown(
            f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;">'
            f'<span style="font-size:13px;font-weight:600;color:#64748b;">Investigation</span>'
            f'<code style="font-size:13px;color:#10b981;background:#f0fdf4;'
            f'padding:3px 11px;border-radius:6px;border:1px solid #bbf7d0;">{inv_id}</code>'
            f'</div>',
            unsafe_allow_html=True,
        )

        status_ph  = st.empty()
        agents_ph  = st.empty()
        metrics_ph = st.empty()
        report_ph  = st.empty()

        _PROG = {
            "queued": 3, "running": 12, "discovering": 20, "investigating": 40,
            "analyzing": 58, "assembling": 78, "reporting": 91,
            "complete": 100, "pending_human": 100, "failed": 100,
        }
        STATUS_LABELS = {
            "queued":       "Queued — waiting to start",
            "running":      "Pipeline starting up…",
            "discovering":  "Discovering relevant cases",
            "investigating":"Investigating provenance chains",
            "analyzing":    "Running parallel analysis",
            "assembling":   "Assembling evidence",
            "reporting":    "Generating compliance report",
            "complete":     "Complete",
            "pending_human": "Awaiting human review",
            "failed":       "Failed",
        }
        AGENT_META = {
            "discovery_agent":      ("Discovery",         False),
            "investigation_agent":  ("Investigation",     True),
            "legal_agent":          ("Legal Analysis",    True),
            "bias_detection_agent": ("Bias Detection",    True),
            "evidence_assembly":    ("Evidence Assembly", False),
            "report_agent":         ("Report",            False),
        }

        for _poll in range(240):
            try:
                resp = httpx.get(
                    f"{api_url}/api/v1/investigations/{inv_id}",
                    headers=HEADERS, timeout=30,
                )
                if resp.status_code != 200:
                    st.error(f"API error {resp.status_code}")
                    break

                data   = resp.json()
                status = data.get("status", "queued")
                elapsed = int(time.time() - start_time)
                m, s    = divmod(elapsed, 60)
                etime   = f"{m}m {s:02d}s" if m else f"{s}s"

                pct    = _PROG.get(status, 8)
                is_end = status in ("complete", "failed", "pending_human")
                is_run = not is_end

                bar_col  = "#10b981" if status == "complete" else ("#ef4444" if status == "failed" else "#3b82f6")
                anim_css = (
                    "background:linear-gradient(90deg,#3b82f6 0%,#93c5fd 50%,#3b82f6 100%);"
                    "background-size:200% 100%;animation:shimmer 1.8s infinite linear;"
                ) if is_run else f"background:{bar_col};"
                dot_col  = "#10b981" if status=="complete" else ("#ef4444" if status=="failed" else "#f59e0b")
                pulse_cs = "animation:pulse-dot 1.2s ease-in-out infinite;" if is_run else ""

                qtext = (f'"{inv_query[:80]}{"…" if len(inv_query)>80 else ""}"') if inv_query else ""

                # ── Status bar ─────────────────────────────────────────────────
                status_ph.markdown(f"""
<div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;
            padding:18px 20px;margin-bottom:14px;">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:13px;">
    <div style="display:flex;align-items:center;gap:9px;">
      <div style="width:9px;height:9px;border-radius:50%;background:{dot_col};
                  flex-shrink:0;{pulse_cs}"></div>
      <span style="font-size:14px;font-weight:700;color:#0f172a;">
        {STATUS_LABELS.get(status, status.title())}</span>
    </div>
    <div style="display:flex;gap:22px;">
      <div style="text-align:right;">
        <div style="font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;
                    letter-spacing:0.6px;">Elapsed</div>
        <div style="font-size:14px;font-weight:700;color:#1e293b;">{etime}</div>
      </div>
      <div style="text-align:right;">
        <div style="font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;
                    letter-spacing:0.6px;">Cases</div>
        <div style="font-size:14px;font-weight:700;color:#1e293b;">{data.get("case_count") or "—"}</div>
      </div>
      <div style="text-align:right;">
        <div style="font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;
                    letter-spacing:0.6px;">Evidence</div>
        <div style="font-size:14px;font-weight:700;color:#1e293b;">{data.get("evidence_count") or "—"}</div>
      </div>
      <div style="text-align:right;">
        <div style="font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;
                    letter-spacing:0.6px;">Progress</div>
        <div style="font-size:14px;font-weight:700;color:#1e293b;">{pct}%</div>
      </div>
    </div>
  </div>
  <div style="background:#f1f5f9;border-radius:5px;height:6px;overflow:hidden;">
    <div style="height:100%;width:{pct}%;border-radius:5px;transition:width 0.5s ease;{anim_css}"></div>
  </div>
  {"" if not qtext else f'<div style="font-size:12px;color:#94a3b8;margin-top:10px;font-style:italic;">{qtext}</div>'}
</div>
""", unsafe_allow_html=True)

                # ── Agent pipeline grid ────────────────────────────────────────
                events     = data.get("agent_events", [])
                done_set   = {e["agent"] for e in events
                              if e.get("event") in ("complete","no_cases","skipped_no_data")}
                error_set  = {e["agent"] for e in events if e.get("event") == "error"}
                active_set = {e["agent"] for e in events} - done_set - error_set

                def _node(key: str, compact: bool = False) -> str:
                    name, parallel = AGENT_META[key]
                    if key in done_set:
                        bg,brd,dc,lc = "#f0fdf4","#bbf7d0","#10b981","#059669"
                        bdg = '<span style="font-size:11px;font-weight:600;color:#059669;background:#dcfce7;border:1px solid #86efac;border-radius:5px;padding:2px 7px;white-space:nowrap;">Done</span>'
                        pa  = ""
                    elif key in error_set:
                        bg,brd,dc,lc = "#fef2f2","#fecaca","#ef4444","#dc2626"
                        bdg = '<span style="font-size:11px;font-weight:600;color:#dc2626;background:#fee2e2;border:1px solid #fca5a5;border-radius:5px;padding:2px 7px;white-space:nowrap;">Error</span>'
                        pa  = ""
                    elif key in active_set:
                        bg,brd,dc,lc = "#eff6ff","#bfdbfe","#3b82f6","#1d4ed8"
                        bdg = '<span style="font-size:11px;font-weight:600;color:#1d4ed8;background:#dbeafe;border:1px solid #93c5fd;border-radius:5px;padding:2px 7px;white-space:nowrap;">Running</span>'
                        pa  = "animation:pulse-dot 1.2s ease-in-out infinite;"
                    else:
                        bg,brd,dc,lc = "#f8fafc","#e2e8f0","#cbd5e1","#94a3b8"
                        bdg = '<span style="font-size:11px;font-weight:600;color:#94a3b8;background:#f1f5f9;border:1px solid #e2e8f0;border-radius:5px;padding:2px 7px;white-space:nowrap;">Waiting</span>'
                        pa  = ""
                    ptag = (
                        '<span style="font-size:9px;color:#7c3aed;background:#faf5ff;'
                        'border:1px solid #e9d5ff;border-radius:4px;padding:1px 5px;'
                        'margin-left:4px;font-weight:700;white-space:nowrap;">PARALLEL</span>'
                    ) if parallel else ""
                    pad = "10px 14px" if compact else "12px 16px"
                    return (
                        f'<div style="background:{bg};border:1px solid {brd};border-radius:10px;'
                        f'padding:{pad};display:flex;align-items:center;gap:10px;height:100%;">'
                        f'<div style="width:8px;height:8px;border-radius:50%;background:{dc};flex-shrink:0;{pa}"></div>'
                        f'<span style="flex:1;font-size:13px;font-weight:600;color:{lc};min-width:0;">'
                        f'{name}{ptag}</span>{bdg}</div>'
                    )

                # 3 parallel agents in a 3-column row so none is cut off
                grid = (
                    f'<div style="margin-bottom:8px;">{_node("discovery_agent")}</div>'
                    f'<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-bottom:8px;">'
                    f'{_node("investigation_agent", compact=True)}'
                    f'{_node("legal_agent", compact=True)}'
                    f'{_node("bias_detection_agent", compact=True)}'
                    f'</div>'
                    f'<div style="margin-bottom:8px;">{_node("evidence_assembly")}</div>'
                    f'<div>{_node("report_agent")}</div>'
                )

                agents_ph.markdown(f"""
<div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;
            overflow:hidden;margin-bottom:14px;">
  <div style="padding:14px 18px;border-bottom:1px solid #f1f5f9;background:#fafbfc;
              display:flex;align-items:center;gap:12px;">
    <div style="width:32px;height:32px;background:#eff6ff;border-radius:8px;
                display:flex;align-items:center;justify-content:center;">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
           stroke="#2563eb" stroke-width="2.2" stroke-linecap="round">
        <rect x="2" y="3" width="5" height="5" rx="1"/>
        <rect x="9.5" y="3" width="5" height="5" rx="1"/>
        <rect x="17" y="3" width="5" height="5" rx="1"/>
        <rect x="4" y="12" width="5" height="9" rx="1"/>
        <rect x="15" y="12" width="5" height="9" rx="1"/>
      </svg>
    </div>
    <div>
      <div style="font-size:14px;font-weight:600;color:#0f172a;">Agent Pipeline</div>
      <div style="font-size:12px;color:#94a3b8;">Investigation · Legal · Bias run in parallel</div>
    </div>
  </div>
  <div style="padding:16px 18px;">{grid}</div>
</div>
""", unsafe_allow_html=True)

                # ── Complete ───────────────────────────────────────────────────
                if status == "complete":
                    verdict = data.get("compliance_verdict", "UNCERTAIN")
                    risk    = data.get("regulatory_risk", "LOW")
                    bias    = data.get("bias_detected", False)
                    cost    = data.get("total_cost_usd", 0.0)
                    conf    = data.get("report_confidence", 0.0)
                    ncases  = data.get("case_count", 0)
                    nevid   = data.get("evidence_count", 0)

                    V_STYLE = {
                        "COMPLIANT": ("#f0fdf4","#bbf7d0","#059669"),
                        "VIOLATION": ("#fef2f2","#fecaca","#dc2626"),
                        "UNCERTAIN": ("#fffbeb","#fcd34d","#d97706"),
                    }
                    vbg, vbrd, vcol = V_STYLE.get(verdict, ("#f8fafc","#e2e8f0","#475569"))
                    R_COL = {"LOW":"#059669","MEDIUM":"#d97706","HIGH":"#dc2626","CRITICAL":"#9333ea"}
                    rcol = R_COL.get(risk, "#475569")

                    metrics_ph.markdown(f"""
<div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;
            margin-bottom:14px;overflow:hidden;animation:fadeInUp 0.3s ease;">
  <div style="padding:14px 18px;border-bottom:1px solid #f1f5f9;background:#fafbfc;
              display:flex;align-items:center;gap:12px;">
    <div style="width:32px;height:32px;background:#ecfdf5;border-radius:8px;
                display:flex;align-items:center;justify-content:center;">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
           stroke="#059669" stroke-width="2.5" stroke-linecap="round">
        <polyline points="20 6 9 17 4 12"/>
      </svg>
    </div>
    <div>
      <div style="font-size:14px;font-weight:600;color:#0f172a;">Investigation Complete</div>
      <div style="font-size:12px;color:#94a3b8;">{etime} &middot; {ncases} cases &middot; {nevid} evidence items</div>
    </div>
  </div>
  <div style="padding:16px 18px;">
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:12px;">
      <div style="background:{vbg};border:1px solid {vbrd};border-radius:10px;padding:14px;">
        <div style="font-size:10px;font-weight:700;color:{vcol};text-transform:uppercase;
                    letter-spacing:0.6px;margin-bottom:4px;">Verdict</div>
        <div style="font-size:18px;font-weight:800;color:{vcol};letter-spacing:-0.4px;">{verdict}</div>
      </div>
      <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:14px;">
        <div style="font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;
                    letter-spacing:0.6px;margin-bottom:4px;">Reg. Risk</div>
        <div style="font-size:18px;font-weight:800;color:{rcol};letter-spacing:-0.4px;">{risk}</div>
      </div>
      <div style="background:{'#fef2f2' if bias else '#f0fdf4'};
                  border:1px solid {'#fecaca' if bias else '#bbf7d0'};border-radius:10px;padding:14px;">
        <div style="font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;
                    letter-spacing:0.6px;margin-bottom:4px;">Bias</div>
        <div style="font-size:18px;font-weight:800;
                    color:{'#dc2626' if bias else '#059669'};letter-spacing:-0.4px;">
          {'Detected' if bias else 'Clear'}</div>
      </div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;">
      <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:12px;">
        <div style="font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;
                    letter-spacing:0.6px;margin-bottom:3px;">Cost</div>
        <div style="font-size:16px;font-weight:700;color:#334155;font-family:monospace;">${cost:.4f}</div>
      </div>
      <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:12px;">
        <div style="font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;
                    letter-spacing:0.6px;margin-bottom:3px;">Duration</div>
        <div style="font-size:16px;font-weight:700;color:#334155;">{etime}</div>
      </div>
      <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:12px;">
        <div style="font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;
                    letter-spacing:0.6px;margin-bottom:3px;">Confidence</div>
        <div style="font-size:16px;font-weight:700;color:#334155;">{conf:.0%}</div>
      </div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

                    with report_ph.container():
                        if data.get("hitl_required"):
                            st.warning("Human review required — check the Escalations page.")
                        if data.get("final_report"):
                            with st.expander("View Full Compliance Report", expanded=True):
                                st.markdown(data["final_report"])
                        if data.get("error_log"):
                            with st.expander(f"Errors ({len(data['error_log'])})"):
                                for err in data["error_log"]:
                                    st.code(err, language=None)
                        st.markdown('<div style="height:8px;"></div>', unsafe_allow_html=True)
                        if st.button("Start New Investigation", use_container_width=True):
                            for k in ("active_investigation_id","investigation_start_time","investigation_query"):
                                st.session_state.pop(k, None)
                            st.rerun()
                    break

                if status == "pending_human":
                    metrics_ph.warning(
                        f"Investigation **{inv_id}** requires human review. "
                        "Use the Escalations page to approve or modify."
                    )
                    with report_ph.container():
                        if st.button("Start New Investigation", use_container_width=True):
                            for k in ("active_investigation_id","investigation_start_time","investigation_query"):
                                st.session_state.pop(k, None)
                            st.rerun()
                    break

                if status == "failed":
                    metrics_ph.error("Investigation failed — check API logs for details.")
                    with report_ph.container():
                        if data.get("error_log"):
                            with st.expander("Error details"):
                                for err in data["error_log"]:
                                    st.code(err, language=None)
                        if st.button("Try Again", use_container_width=True):
                            for k in ("active_investigation_id","investigation_start_time","investigation_query"):
                                st.session_state.pop(k, None)
                            st.rerun()
                    break

                time.sleep(3)

            except Exception as exc:
                status_ph.warning(f"Polling paused: {exc} — retrying…")
                time.sleep(5)

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="border-top:1px solid #e2e8f0;padding:14px 0;margin-top:32px;
            display:flex;align-items:center;justify-content:space-between;">
  <div style="font-size:13px;color:#94a3b8;">
    <strong style="color:#475569;">SENTINEL</strong> &nbsp;·&nbsp;
    AI Compliance Investigation Platform &nbsp;·&nbsp; v1.0.0
    &nbsp;·&nbsp; Tenant: <strong style="color:#475569;">{tenant_id}</strong>
  </div>
  <div style="font-size:13px;color:#cbd5e1;">© 2024 SENTINEL</div>
</div>
""", unsafe_allow_html=True)
