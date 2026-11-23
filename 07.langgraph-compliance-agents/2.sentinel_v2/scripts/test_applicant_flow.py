"""
Test applicant_data flow through API and database
"""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

import httpx

API_URL = "http://localhost:8003"
API_KEY = os.getenv("SENTINEL_API_KEY", "test-key")

async def test():
    applicant_data = {
        "applicant_id": "TEST_FLOW_001",
        "applicant_name": "Test User",
        "race": "African American",
        "age": 35,
        "income": 45000,
        "credit_score": 620,
        "denied": True,
        "denial_reason": "credit_score_too_low",
    }

    debug_log = []

    async with httpx.AsyncClient(timeout=300.0) as client:
        # Step 1: Create investigation
        debug_log.append("\n=== STEP 1: CREATE INVESTIGATION ===")
        r1 = await client.post(
            f"{API_URL}/api/v1/investigations",
            json={
                "query": "Test investigation with applicant data",
                "date_from": "2026-01-01",
                "date_to": "2026-12-31",
                "applicant_data": applicant_data
            },
            headers={"X-API-Key": API_KEY, "X-Tenant-ID": "test-tenant"}
        )
        inv_data = r1.json()
        inv_id = inv_data["investigation_id"]
        debug_log.append(f"Created investigation: {inv_id}")
        debug_log.append(f"Response: {json.dumps(inv_data, indent=2)}")

        # Step 2: Fetch investigation from database
        debug_log.append("\n=== STEP 2: FETCH FROM DATABASE ===")
        r2 = await client.get(
            f"{API_URL}/api/v1/investigations/{inv_id}",
            headers={"X-API-Key": API_KEY, "X-Tenant-ID": "test-tenant"}
        )
        fetch_data = r2.json()
        debug_log.append(f"Fetched investigation: {json.dumps(fetch_data, indent=2)}")

        # Step 3: Execute synchronously WITHOUT sending applicant_data in request
        debug_log.append("\n=== STEP 3: EXECUTE SYNC (no request body) ===")
        r3 = await client.post(
            f"{API_URL}/api/v1/investigations/{inv_id}/execute-sync",
            json={},  # Empty body - applicant_data should come from database
            headers={"X-API-Key": API_KEY, "X-Tenant-ID": "test-tenant"},
            timeout=300.0
        )
        result = r3.json()
        debug_log.append(f"Status: {result.get('status')}")
        debug_log.append(f"Case Count: {result.get('case_count')}")
        debug_log.append(f"Verdict: {result.get('compliance_verdict')}")
        debug_log.append(f"Bias Detected: {result.get('bias_detected')}")

        # Write debug log
        log_file = Path(__file__).parent.parent / "applicant_data_flow.log"
        with open(log_file, "w") as f:
            f.write("\n".join(debug_log))

        print(f"[OK] Debug log written to {log_file}")
        print(f"\n[SUMMARY]")
        print(f"  case_count={result.get('case_count')}")
        print(f"  verdict={result.get('compliance_verdict')}")
        print(f"  bias={result.get('bias_detected')}")

asyncio.run(test())
