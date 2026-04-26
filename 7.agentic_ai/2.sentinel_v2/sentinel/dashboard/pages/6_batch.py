"""
SENTINEL — Batch Investigation Runner
Process 500+ decision records for automated compliance analysis
"""
import os
import sys
from pathlib import Path as _Path

from dotenv import load_dotenv

_root = _Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(_root / ".env", override=True)
sys.path.insert(0, str(_root))

import httpx
import streamlit as st
import asyncpg
import asyncio
import json

st.set_page_config(
    page_title="Batch Processing — SENTINEL",
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
  <h1>Batch Investigation Processing</h1>
  <p>Run compliance analysis on 500+ decision records from the database.</p>
</div>
""", unsafe_allow_html=True)

# ── Database Stats ─────────────────────────────────────────────────────────────
async def get_stats():
    db_url = os.getenv("DATABASE_URL")
    conn = await asyncpg.connect(db_url)

    total_records = await conn.fetchval("SELECT COUNT(*) FROM decision_records")
    total_investigations = await conn.fetchval("SELECT COUNT(*) FROM investigations")

    await conn.close()
    return total_records, total_investigations

try:
    total_recs, total_invs = asyncio.run(get_stats())
except:
    total_recs, total_invs = 0, 0

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Decision Records", total_recs)
with col2:
    st.metric("Investigations Created", total_invs)
with col3:
    st.metric("API Status", "Online" if _api_ok else "Offline")

st.markdown("---")

# ── Batch Control ──────────────────────────────────────────────────────────────
st.markdown("### Configure Batch Processing")

# Filtering options
col1, col2, col3 = st.columns(3)
with col1:
    domain = st.selectbox("Domain", ["Finance", "Healthcare", "Pharma", "Banking"], help="Business domain for investigation")
with col2:
    outcome_filter = st.selectbox("Outcome Filter", ["All", "Denied Only", "Approved Only"], help="Filter by application outcome")
with col3:
    date_from = st.date_input("From Date", value=None)
    date_to = st.date_input("To Date", value=None)

st.markdown("---")
st.markdown("### Processing Options")

col1, col2 = st.columns(2)

with col1:
    batch_size = st.slider("Batch Size (records per run)", min_value=5, max_value=100, value=20, step=5)
    limit = st.number_input("Max Records to Process", min_value=1, max_value=500, value=50, step=10)

with col2:
    st.markdown("<div style='padding-top:12px;'></div>", unsafe_allow_html=True)
    auto_mode = st.checkbox("Auto Mode (run all)", value=False, help="Automatically create investigations for all records")

st.markdown("---")

if st.button("Start Batch Processing", disabled=not _api_ok, use_container_width=True):
    st.info("Starting batch processing...")

    async def run_batch():
        db_url = os.getenv("DATABASE_URL")
        conn = await asyncpg.connect(db_url)

        # Build WHERE clause based on filters
        where_clauses = ["metadata IS NOT NULL"]
        params = [limit]
        param_count = 1

        if outcome_filter != "All":
            outcome_val = outcome_filter.split()[0].lower()  # "denied" or "approved"
            param_count += 1
            where_clauses.append(f"outcome = ${param_count}")
            params.append(outcome_val)

        if date_from:
            param_count += 1
            where_clauses.append(f"decision_timestamp >= ${param_count}")
            params.append(date_from)

        if date_to:
            param_count += 1
            where_clauses.append(f"decision_timestamp <= ${param_count}")
            params.append(date_to)

        where_clause = " AND ".join(where_clauses)

        # Get decision records with filters
        query = f"""
            SELECT id, case_id, outcome, decision_timestamp, metadata
            FROM decision_records
            WHERE {where_clause}
            ORDER BY decision_timestamp DESC
            LIMIT $1
        """
        records = await conn.fetch(query, *params)

        await conn.close()

        if not records:
            st.warning("No decision records found in database")
            return

        st.write(f"Found {len(records)} decision records to process\n")

        # Create progress bar
        progress_bar = st.progress(0)
        status_container = st.container()

        results_summary = {
            "created": 0,
            "completed": 0,
            "failed": 0,
            "pending": 0,
            "errors": []
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            for idx, record in enumerate(records):
                try:
                    # Parse metadata if it's a string
                    meta = record['metadata'] or {}
                    if isinstance(meta, str):
                        meta = json.loads(meta) if meta else {}

                    # Extract or create applicant data from metadata
                    # Convert credit score tier to numeric value
                    credit_tier = meta.get('credit_score_tier', 700)
                    credit_map = {'excellent': 750, 'good': 700, 'fair': 600, 'poor': 550}
                    credit_score = credit_map.get(credit_tier, credit_tier) if isinstance(credit_tier, str) else credit_tier

                    applicant_data = {
                        "case_id": record['case_id'],
                        "applicant_id": f"BATCH_{record['id']}",
                        "applicant_name": f"Applicant {record['case_id']}",
                        "age": meta.get('age_group', 35),
                        "income": meta.get('income', 75000),
                        "credit_score": credit_score,
                        "denied": record['outcome'] == 'denied',
                        "race": meta.get('race'),
                        "gender": meta.get('gender'),
                        "denial_reason": meta.get('denial_reason'),
                        "approved_rate": meta.get('approved_rate'),
                    }

                    # Step 1: Create investigation
                    resp = await client.post(
                        f"{api_url}/api/v1/investigations",
                        json={
                            "query": f"Batch processing decision {record['case_id']}",
                            "date_from": "2024-01-01",
                            "date_to": "2024-12-31",
                            "applicant_data": applicant_data
                        },
                        headers=HEADERS,
                    )

                    if resp.status_code == 202:
                        inv = resp.json()
                        inv_id = inv.get("investigation_id")

                        # Step 2: Execute the investigation synchronously
                        exec_resp = await client.post(
                            f"{api_url}/api/v1/investigations/{inv_id}/execute-sync",
                            json={},
                            headers=HEADERS,
                            timeout=60.0
                        )

                        if exec_resp.status_code == 200:
                            results_summary["created"] += 1
                            results_summary["completed"] += 1
                        else:
                            results_summary["created"] += 1
                            results_summary["pending"] += 1
                    else:
                        results_summary["failed"] += 1
                        error_msg = f"Status {resp.status_code}: {resp.text[:100]}"
                        if len(results_summary["errors"]) < 3:
                            results_summary["errors"].append(error_msg)

                except Exception as e:
                    results_summary["failed"] += 1
                    if len(results_summary["errors"]) < 3:
                        results_summary["errors"].append(str(e)[:100])

                # Update progress
                progress = (idx + 1) / len(records)
                progress_bar.progress(progress)

                if (idx + 1) % max(5, batch_size) == 0:
                    with status_container:
                        st.write(f"**Progress:** {idx + 1}/{len(records)} | Created: {results_summary['created']} | Failed: {results_summary['failed']}")

        if results_summary['created'] > 0:
            st.success(f"Batch processing complete!")

            # Show summary metrics
            st.markdown("### Batch Processing Summary")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Created", results_summary['created'])
            with col2:
                st.metric("Completed", results_summary['completed'])
            with col3:
                st.metric("Pending", results_summary['pending'])
            with col4:
                st.metric("Failed", results_summary['failed'])

            # Fetch and display verdict distribution
            st.markdown("### Verdict Distribution")
            try:
                import asyncpg
                async def get_verdict_stats():
                    db_url = os.getenv("DATABASE_URL")
                    conn = await asyncpg.connect(db_url)

                    verdicts = await conn.fetch("""
                        SELECT
                            state_snapshot->>'compliance_verdict' as verdict,
                            COUNT(*) as count
                        FROM investigations
                        WHERE applicant_data::text LIKE '%BATCH_%'
                        GROUP BY verdict
                        ORDER BY count DESC
                    """)

                    bias_count = await conn.fetchval("""
                        SELECT COUNT(*) FROM investigations
                        WHERE applicant_data::text LIKE '%BATCH_%'
                        AND state_snapshot->>'bias_detected' = 'true'
                    """)

                    await conn.close()
                    return verdicts, bias_count

                verdicts, bias_count = asyncio.run(get_verdict_stats())

                vcol1, vcol2, vcol3 = st.columns(3)
                for v in verdicts:
                    verdict = v['verdict'] or "Unknown"
                    count = v['count']
                    pct = (count / results_summary['created']) * 100
                    color = "#10b981" if verdict == "COMPLIANT" else "#f59e0b" if verdict == "UNCERTAIN" else "#ef4444"
                    vcol1.metric(verdict, f"{count} ({pct:.0f}%)")

                with vcol3:
                    st.metric("Bias Flagged", f"{bias_count} cases")

            except Exception as e:
                st.warning(f"Could not fetch verdict stats: {str(e)[:100]}")

            st.info("Go to **Results** page to view detailed investigation outcomes and reports")
        else:
            st.error(f"Batch processing failed - 0 investigations created\n\n**Errors:**")
            for error in results_summary['errors']:
                st.error(f" • {error}")

    try:
        asyncio.run(run_batch())
    except Exception as e:
        st.error(f"Batch processing failed: {str(e)[:200]}")

st.markdown("---")
st.markdown("""
### How It Works

1. **Database Records** — 500 synthetic decision records with approval/denial outcomes
2. **Batch Creation** — Creates investigations for each record with applicant data extracted from metadata
3. **Compliance Analysis** — Each investigation runs through the full compliance pipeline
4. **Results** — View aggregated results and bias patterns across all records

### Expected Results

- **500 investigations** created and processed
- **Approval vs. Denial patterns** analyzed
- **Bias detection** across demographics
- **Compliance verdicts** (COMPLIANT, UNCERTAIN, VIOLATION)
- **Regulatory risk** assessment for each decision
""")
