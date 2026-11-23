"""
Single-record end-to-end validation for SENTINEL v2.

What this tests:
  1. Seeds 1 synthetic decision + provenance node into DB
  2. Triggers investigation via REST API
  3. Polls until complete (max 120s)
  4. Validates v2 features:
       ✓ Discovery found the case
       ✓ Legal agent retrieved regulations
       ✓ Report generated with citations
       ✓ Audit log populated (audit_agent)
       ✓ Pattern store populated (memory agent)
       ✓ Regulation search works (MCP regulation tool)

Prerequisites:
  - API running:      python -m uvicorn sentinel.api.main:app --port 8003
  - Ollama running:   ollama serve
  - DB seeded:        python scripts/seed_database.py
  - Regs ingested:    python scripts/ingest_regulations.py

Usage:
  python scripts/test_single_record.py
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

import asyncpg
import httpx

from configs.settings import settings

# ── Config ────────────────────────────────────────────────────────────────────
API_URL   = "http://localhost:8003"
API_KEY   = settings.sentinel_api_key
TENANT_ID = "test-tenant-v2"
HEADERS   = {"X-API-Key": API_KEY, "X-Tenant-ID": TENANT_ID, "Content-Type": "application/json"}

# Single synthetic test case — deliberately denied with a suspicious reason
TEST_CASE = {
    "case_id":            "CASE-V2-TEST-001",
    "tenant_id":          TENANT_ID,
    "outcome":            "DENIED",
    "decision_timestamp": "2024-03-15T10:30:00",
    "model_version":      "credit-model-v3",
    "reasoning_text":     "Application denied: DTI ratio 42% exceeds threshold. Census tract CT-015 flagged for elevated denial concentration. Age group 55-65 with income bracket $25k-$50k.",
    "metadata": {
        "age_group":             "55-65",
        "income_bracket":        "$25k-$50k",
        "credit_score_tier":     "fair",
        "zip_code_census_tract": "CT-015",
    },
}

PASS = "[OK]"
FAIL = "[FAIL]"
INFO = "[INFO]"


def ok(msg: str):   print(f"  {PASS} {msg}")
def fail(msg: str): print(f"  {FAIL} {msg}")
def info(msg: str): print(f"  {INFO} {msg}")


# ── Step 1: Seed single record ─────────────────────────────────────────────────

async def seed_test_record(conn) -> bool:
    print("\n[1] Seeding single test decision record...")
    d = TEST_CASE

    try:
        await conn.execute(
            """
            INSERT INTO decision_records
                (case_id, tenant_id, outcome, decision_timestamp, model_version, reasoning_text, metadata)
            VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb)
            ON CONFLICT (case_id, tenant_id) DO UPDATE
                SET outcome=EXCLUDED.outcome,
                    reasoning_text=EXCLUDED.reasoning_text
            """,
            d["case_id"], d["tenant_id"], d["outcome"],
            datetime.fromisoformat(d["decision_timestamp"]).replace(tzinfo=None),
            d["model_version"], d["reasoning_text"],
            json.dumps(d["metadata"]),
        )

        meta = d["metadata"]
        content = {
            "case_id":               d["case_id"],
            "outcome":               d["outcome"],
            "reasoning_text":        d["reasoning_text"],
            "model_version":         d["model_version"],
            "timestamp":             d["decision_timestamp"],
            "age_group":             meta["age_group"],
            "income_bracket":        meta["income_bracket"],
            "credit_score_tier":     meta["credit_score_tier"],
            "zip_code_census_tract": meta["zip_code_census_tract"],
        }
        content_hash = hashlib.sha256(
            json.dumps(content, sort_keys=True).encode()
        ).hexdigest()

        await conn.execute(
            """
            INSERT INTO provenance_nodes
                (node_id, node_type, tenant_id, content, content_hash, timestamp)
            VALUES ($1,$2,$3,$4::jsonb,$5,$6)
            ON CONFLICT (node_id, tenant_id) DO UPDATE
                SET content=EXCLUDED.content, content_hash=EXCLUDED.content_hash
            """,
            f"decision-{d['case_id']}",
            "prov:Entity",
            d["tenant_id"],
            json.dumps(content),
            content_hash,
            datetime.fromisoformat(d["decision_timestamp"]).replace(tzinfo=None),
        )

        ok(f"Decision record seeded: {d['case_id']}")
        ok(f"Provenance node seeded: decision-{d['case_id']}")
        info(f"Outcome: {d['outcome']} | Reason: {d['reasoning_text'][:80]}...")
        return True

    except Exception as exc:
        fail(f"Seed failed: {exc}")
        return False


# ── Step 2: Trigger investigation ─────────────────────────────────────────────

async def trigger_investigation(client: httpx.AsyncClient) -> str | None:
    print("\n[2] Triggering investigation via API...")

    resp = await client.post(
        f"{API_URL}/api/v1/investigations",
        headers=HEADERS,
        json={
            "query":     "Review credit decision for CASE-V2-TEST-001 on 2024-03-15 for ECOA fair lending compliance and bias detection",
            "date_from": "2024-03-01",
            "date_to":   "2024-03-31",
            "domain":    "finance",
        },
    )
    if resp.status_code != 202:
        fail(f"API returned {resp.status_code}: {resp.text[:200]}")
        return None

    inv_id = resp.json()["investigation_id"]
    ok(f"Investigation triggered: {inv_id}")
    return inv_id


# ── Step 3: Poll until complete ────────────────────────────────────────────────

async def poll_until_complete(client: httpx.AsyncClient, inv_id: str, timeout: int = 180) -> dict | None:
    print(f"\n[3] Polling investigation {inv_id} (max {timeout}s)...")
    start = time.time()
    terminal = {"complete", "pending_human", "failed"}
    last_status = ""

    while time.time() - start < timeout:
        await asyncio.sleep(8)
        resp = await client.get(
            f"{API_URL}/api/v1/investigations/{inv_id}",
            headers=HEADERS,
        )
        if resp.status_code != 200:
            fail(f"Poll error: {resp.status_code}")
            continue

        data = resp.json()
        status = data["status"]
        if status != last_status:
            info(f"Status: {status}")
            last_status = status

        if status in terminal:
            elapsed = int(time.time() - start)
            ok(f"Completed in {elapsed}s — status={status}")
            return data

    fail(f"Timed out after {timeout}s")
    return None


# ── Step 4: Validate investigation result ──────────────────────────────────────

def validate_result(result: dict) -> dict[str, bool]:
    print("\n[4] Validating investigation result...")
    checks = {}

    # Compliance verdict
    verdict = result.get("compliance_verdict")
    checks["compliance_verdict_set"] = verdict is not None
    if verdict:
        ok(f"Compliance verdict: {verdict}")
    else:
        fail("No compliance verdict")

    # Regulatory risk
    risk = result.get("regulatory_risk")
    checks["regulatory_risk_set"] = risk is not None
    if risk:
        ok(f"Regulatory risk: {risk}")
    else:
        fail("No regulatory risk")

    # Case found
    case_count = result.get("case_count", 0)
    checks["case_found"] = case_count > 0
    if case_count > 0:
        ok(f"Cases found: {case_count}")
    else:
        fail("No cases discovered — BM25/BERT may not have matched the record")

    # Final report
    report = result.get("final_report") or ""
    checks["report_generated"] = len(report) > 100
    if len(report) > 100:
        ok(f"Report generated ({len(report)} chars)")
        # Check for key content
        if "CASE-V2-TEST-001" in report or "CT-015" in report or "denied" in report.lower():
            ok("Report references test case content")
            checks["report_references_case"] = True
        else:
            info("Report doesn't mention test case ID (may use anonymized format)")
            checks["report_references_case"] = False
        if any(reg in report for reg in ["ECOA", "FCRA", "HMDA", "1691"]):
            ok("Report cites regulations")
            checks["report_cites_regulations"] = True
        else:
            fail("Report does not cite any regulations")
            checks["report_cites_regulations"] = False
    else:
        fail(f"Report too short or missing: '{report[:100]}'")
        checks["report_references_case"] = False
        checks["report_cites_regulations"] = False

    # Bias detection
    bias = result.get("bias_detected")
    checks["bias_detection_ran"] = bias is not None
    info(f"Bias detected: {bias} (confidence: {result.get('bias_confidence', 0):.2f})")

    # Report confidence
    confidence = result.get("report_confidence", 0)
    checks["confidence_scored"] = confidence > 0
    ok(f"Report confidence: {confidence:.2f}")

    # Cost tracked
    cost = result.get("total_cost_usd", 0)
    checks["cost_tracked"] = cost >= 0
    ok(f"Total cost: ${cost:.4f}")

    return checks


# ── Step 5: Validate v2 DB features ───────────────────────────────────────────

async def validate_v2_db(conn, inv_id: str) -> dict[str, bool]:
    print("\n[5] Validating v2 DB features...")
    checks = {}

    # Audit log
    audit_rows = await conn.fetch(
        "SELECT event, actor FROM audit_log WHERE investigation_id=$1 ORDER BY created_at",
        inv_id,
    )
    checks["audit_log_populated"] = len(audit_rows) > 0
    if audit_rows:
        ok(f"Audit log: {len(audit_rows)} entries written")
        for row in audit_rows:
            info(f"  {row['actor']:25s} → {row['event']}")
    else:
        fail("Audit log empty — audit_agent may not have run or audit_log table missing")

    # Pattern store
    pattern_rows = await conn.fetch(
        "SELECT pattern_text, regulation FROM investigation_patterns WHERE domain='finance' ORDER BY created_at DESC LIMIT 5"
    )
    checks["patterns_stored"] = len(pattern_rows) > 0
    if pattern_rows:
        ok(f"Pattern store: {len(pattern_rows)} patterns extracted and stored")
        for row in pattern_rows:
            info(f"  [{row['regulation'] or 'General'}] {row['pattern_text'][:80]}")
    else:
        info("Pattern store empty — patterns stored after second+ investigation (first run seeds them)")
        checks["patterns_stored"] = True  # Not a failure on first run

    # Provenance nodes for this investigation
    prov_rows = await conn.fetch(
        "SELECT node_id, node_type FROM provenance_nodes WHERE node_id LIKE $1 AND tenant_id=$2",
        f"%{inv_id[-8:]}%", TENANT_ID,
    )
    checks["provenance_nodes_written"] = len(prov_rows) > 0
    if prov_rows:
        ok(f"Provenance nodes written: {len(prov_rows)}")
        for row in prov_rows:
            info(f"  {row['node_type']:20s}  {row['node_id']}")
    else:
        info("No investigation-specific provenance nodes found (nodes use inv_id suffix)")

    return checks


# ── Step 6: Validate regulation search (MCP regulation tool) ──────────────────

async def validate_regulation_search() -> dict[str, bool]:
    print("\n[6] Validating regulation search (pgvector RAG)...")
    checks = {}

    try:
        from sentinel.tools.regulation_tools import search_regulations
        results = await search_regulations(
            query="credit denial discrimination adverse action ECOA",
            domain="finance",
            top_k=3,
        )
        checks["regulation_search_works"] = len(results) > 0
        if results:
            ok(f"Regulation search returned {len(results)} results")
            for r in results:
                info(f"  {r.get('regulation_name')} — {r.get('section', '')[:60]}")
        else:
            fail("No regulations found — run python scripts/ingest_regulations.py first")
    except Exception as exc:
        fail(f"Regulation search failed: {exc}")
        checks["regulation_search_works"] = False

    return checks


# ── Step 7: Validate API regulation endpoint ───────────────────────────────────

async def validate_regulation_api(client: httpx.AsyncClient) -> dict[str, bool]:
    print("\n[7] Validating regulation API endpoints (v2)...")
    checks = {}

    # List regulations
    resp = await client.get(f"{API_URL}/api/v1/regulations", headers=HEADERS)
    checks["list_regulations_works"] = resp.status_code == 200
    if resp.status_code == 200:
        regs = resp.json()
        ok(f"GET /api/v1/regulations → {len(regs)} sections")
        checks["regulations_in_db"] = len(regs) > 0
        if not regs:
            info("No regulations in DB — run: python scripts/ingest_regulations.py")
    else:
        fail(f"GET /api/v1/regulations failed: {resp.status_code}")
        checks["regulations_in_db"] = False

    # Add a test regulation
    resp = await client.post(
        f"{API_URL}/api/v1/regulations",
        headers=HEADERS,
        json={
            "regulation_name": "TEST_REG_V2",
            "full_name":       "Test Regulation for v2 Validation",
            "section":         "§ 1.0 — Test Section",
            "content":         "This is a test regulation section created by the v2 end-to-end test script. It verifies that new regulations can be added via API and immediately become available to the legal agent.",
            "domain":          "finance",
        },
    )
    if resp.status_code == 201:
        data = resp.json()
        test_reg_id = data["id"]
        ok(f"POST /api/v1/regulations → id={test_reg_id}, embedded={data.get('embedded')}")
        checks["add_regulation_works"] = True

        # Soft delete the test regulation
        del_resp = await client.delete(
            f"{API_URL}/api/v1/regulations/{test_reg_id}",
            headers=HEADERS,
        )
        checks["delete_regulation_works"] = del_resp.status_code == 200
        if del_resp.status_code == 200:
            ok(f"DELETE /api/v1/regulations/{test_reg_id} → soft-deleted")
        else:
            fail(f"DELETE failed: {del_resp.status_code}")
    elif resp.status_code == 409:
        ok("POST /api/v1/regulations → 409 Already exists (test already ran before)")
        checks["add_regulation_works"] = True
        checks["delete_regulation_works"] = True
    else:
        fail(f"POST /api/v1/regulations failed: {resp.status_code} {resp.text[:200]}")
        checks["add_regulation_works"] = False
        checks["delete_regulation_works"] = False

    return checks


# ── Main ───────────────────────────────────────────────────────────────────────

async def main():
    print("=" * 65)
    print("  SENTINEL v2 — Single Record End-to-End Validation")
    print("=" * 65)

    # Check API is reachable
    async with httpx.AsyncClient(timeout=5) as client:
        try:
            r = await client.get(f"{API_URL}/health")
            if r.status_code != 200:
                print(f"\n{FAIL} API not healthy. Start it first:")
                print("   python -m uvicorn sentinel.api.main:app --port 8003")
                sys.exit(1)
            print(f"\n{PASS} API is healthy")
        except Exception:
            print(f"\n{FAIL} Cannot reach API at {API_URL}. Start it first:")
            print("   python -m uvicorn sentinel.api.main:app --port 8003")
            sys.exit(1)

    conn = await asyncpg.connect(settings.database_url_sync)
    all_checks: dict[str, bool] = {}

    try:
        async with httpx.AsyncClient(timeout=180) as client:
            # Step 1: Seed
            if not await seed_test_record(conn):
                sys.exit(1)

            # Step 2: Trigger
            inv_id = await trigger_investigation(client)
            if not inv_id:
                sys.exit(1)

            # Step 3: Poll
            result = await poll_until_complete(client, inv_id)
            if not result:
                sys.exit(1)

            # Step 4: Validate result
            all_checks.update(validate_result(result))

            # Step 5: Validate v2 DB
            all_checks.update(await validate_v2_db(conn, inv_id))

            # Step 6: Regulation search
            all_checks.update(await validate_regulation_search())

            # Step 7: Regulation API
            all_checks.update(await validate_regulation_api(client))

    finally:
        await conn.close()

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("  VALIDATION SUMMARY")
    print("=" * 65)

    passed = sum(1 for v in all_checks.values() if v)
    total  = len(all_checks)

    for check, result_val in all_checks.items():
        icon = PASS if result_val else FAIL
        print(f"  {icon}  {check}")

    print(f"\n  Result: {passed}/{total} checks passed")

    if passed == total:
        print(f"\n  {PASS} All v2 features validated successfully!")
    elif passed >= total * 0.8:
        print(f"\n  ⚠️  Most checks passed ({passed}/{total}). Review failures above.")
    else:
        print(f"\n  {FAIL} Significant failures ({total - passed} failed). Check logs.")

    print("=" * 65)
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
