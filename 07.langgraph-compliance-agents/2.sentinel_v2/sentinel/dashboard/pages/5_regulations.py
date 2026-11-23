"""
Regulation Library — browse, add, and remove regulation sections.
Compliance officers can add new laws or amendments without touching code.
"""
from __future__ import annotations

import os
import requests
import streamlit as st

from sentinel.dashboard.theme import CUSTOM_CSS, render_sidebar_nav

st.set_page_config(page_title="Regulations — SENTINEL", layout="wide", page_icon="📚")
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

API_URL = os.getenv("SENTINEL_API_URL", "http://localhost:8003")
API_KEY = os.getenv("SENTINEL_API_KEY", "sentinel-dev-key-change-in-production")
TENANT  = os.getenv("SENTINEL_TENANT_ID", "bank-acme")
HEADERS = {"X-API-Key": API_KEY, "X-Tenant-ID": TENANT}
DOMAINS = ["finance", "pharma", "generic"]


def _api(method: str, path: str, **kwargs):
    try:
        r = requests.request(method, f"{API_URL}{path}", headers=HEADERS, timeout=15, **kwargs)
        return r
    except requests.exceptions.ConnectionError:
        return None


with st.sidebar:
    st.markdown(
        '<div style="padding:20px 16px 10px;font-size:20px;font-weight:800;'
        'color:#ffffff;letter-spacing:-0.5px;font-family:Inter,sans-serif;">'
        '🛡️ SENTINEL</div>',
        unsafe_allow_html=True,
    )
    st.markdown("---")
    render_sidebar_nav(st, current="regulations")
    st.markdown("---")
    st.markdown(
        '<p style="color:#64748b;font-size:12px;padding:0 4px;">v2.0 · Regulation Library</p>',
        unsafe_allow_html=True,
    )

st.markdown(
    '<div class="page-header">'
    '<h1>📚 Regulation Library</h1>'
    '<p>Browse, add, and remove compliance regulation sections. '
    'New sections are immediately available to the legal agent — no restart required.</p>'
    '</div>',
    unsafe_allow_html=True,
)

# ── Domain filter ─────────────────────────────────────────────────────────────
col_filter, col_spacer = st.columns([2, 5])
with col_filter:
    domain_filter = st.selectbox("Filter by domain", ["All"] + DOMAINS, key="domain_filter")

# ── Fetch regulations ─────────────────────────────────────────────────────────
domain_param = "" if domain_filter == "All" else domain_filter
resp = _api("GET", f"/api/v1/regulations?domain={domain_param}")

if resp is None:
    st.error("Cannot reach SENTINEL API. Make sure the API server is running on port 8003.")
    st.stop()

if resp.status_code != 200:
    st.error(f"API error: {resp.status_code} — {resp.text[:200]}")
    st.stop()

regulations = resp.json()

# ── Metrics row ───────────────────────────────────────────────────────────────
domains_present = list({r["domain"] for r in regulations})
reg_names = list({r["regulation_name"] for r in regulations})

m1, m2, m3 = st.columns(3)
m1.metric("Total Sections", len(regulations))
m2.metric("Regulation Acts", len(reg_names))
m3.metric("Domains Covered", len(domains_present))

st.markdown("---")

# ── Regulation table ──────────────────────────────────────────────────────────
st.subheader("Current Regulation Library")

if not regulations:
    st.info("No regulations found. Add your first regulation below, or run `python scripts/ingest_regulations.py`.")
else:
    # Group by regulation_name
    grouped: dict[str, list] = {}
    for r in regulations:
        grouped.setdefault(r["regulation_name"], []).append(r)

    for reg_name, sections in sorted(grouped.items()):
        full_name = sections[0]["full_name"]
        domain_tag = sections[0]["domain"]

        domain_color = {"finance": "#10b981", "pharma": "#3b82f6", "generic": "#f59e0b"}.get(domain_tag, "#94a3b8")

        with st.expander(f"**{reg_name}** — {full_name}  ·  {len(sections)} section(s)", expanded=False):
            st.markdown(
                f'<span class="badge" style="background:{domain_color}22;color:{domain_color};'
                f'border:1px solid {domain_color}55;border-radius:20px;padding:3px 11px;'
                f'font-size:12px;font-weight:600;">{domain_tag}</span>',
                unsafe_allow_html=True,
            )
            st.markdown("")

            for sec in sections:
                col_sec, col_del = st.columns([10, 1])
                with col_sec:
                    st.markdown(f"**{sec['section']}**")
                with col_del:
                    if st.button("", key=f"del_{sec['id']}", help="Remove this section"):
                        del_resp = _api("DELETE", f"/api/v1/regulations/{sec['id']}")
                        if del_resp and del_resp.status_code == 200:
                            st.success(f"Removed: {sec['section']}")
                            st.rerun()
                        else:
                            st.error("Delete failed")

st.markdown("---")

# ── Add new regulation form ───────────────────────────────────────────────────
st.subheader("Add New Regulation Section")
st.markdown(
    '<p style="color:#64748b;font-size:13px;margin-bottom:16px;">'
    'Paste any regulation text below. It will be embedded and available to the legal agent '
    'on the next investigation — no code change, no restart.</p>',
    unsafe_allow_html=True,
)

with st.form("add_regulation_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        reg_name  = st.text_input("Regulation name *", placeholder="e.g. GLBA")
        section   = st.text_input("Section *", placeholder="e.g. 15 U.S.C. § 6802")
        domain    = st.selectbox("Domain *", DOMAINS)
    with col2:
        full_name = st.text_input("Full name *", placeholder="e.g. Gramm-Leach-Bliley Act")

    content = st.text_area(
        "Section text *",
        height=200,
        placeholder="Paste the full text of the regulation section here...",
    )

    submitted = st.form_submit_button("Add Regulation", use_container_width=True)

if submitted:
    if not all([reg_name, full_name, section, content]):
        st.error("All fields marked * are required.")
    else:
        with st.spinner("Embedding and storing..."):
            add_resp = _api("POST", "/api/v1/regulations", json={
                "regulation_name": reg_name,
                "full_name": full_name,
                "section": section,
                "content": content,
                "domain": domain,
            })

        if add_resp is None:
            st.error("Cannot reach API.")
        elif add_resp.status_code == 201:
            result = add_resp.json()
            st.success(
                f"Added **{reg_name} — {section}**  "
                f"{'(embedded)' if result.get('embedded') else '(stored without embedding — check OpenAI key)'}"
            )
            st.rerun()
        elif add_resp.status_code == 409:
            st.warning(f"Already exists: {reg_name} — {section}")
        else:
            st.error(f"Error {add_resp.status_code}: {add_resp.text[:300]}")

st.markdown("---")

# ── Search test ───────────────────────────────────────────────────────────────
st.subheader("Search Test")
st.markdown(
    '<p style="color:#64748b;font-size:13px;margin-bottom:12px;">'
    'Test how the legal agent would find regulations for a given query.</p>',
    unsafe_allow_html=True,
)

test_query = st.text_input("Test query", placeholder="e.g. credit denial discrimination adverse action")
test_domain = st.selectbox("Domain", DOMAINS, key="test_domain")

if st.button("Search", use_container_width=False):
    if test_query:
        with st.spinner("Searching..."):
            search_resp = _api("GET", f"/api/v1/regulations/search?query={test_query}&domain={test_domain}&top_k=5")

        if search_resp is None:
            st.error("Cannot reach API.")
        elif search_resp.status_code == 200:
            results = search_resp.json()
            if results:
                for i, r in enumerate(results, 1):
                    with st.expander(f"{i}. {r.get('regulation_name')} — {r.get('section', '')[:80]}"):
                        st.markdown(f"**Score:** {r.get('score', 0):.3f}")
                        st.markdown(r.get("text", "")[:500])
            else:
                st.info("No results found. Try a different query or ingest more regulations.")
        else:
            st.error(f"Search error {search_resp.status_code}: {search_resp.text[:200]}")
