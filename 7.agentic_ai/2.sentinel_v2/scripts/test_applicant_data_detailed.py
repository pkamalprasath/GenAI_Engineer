"""
Detailed diagnostic test for applicant_data flow
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
        "applicant_id": "DETAILED_TEST_001",
        "applicant_name": "Test User",
        "race": "African American",
        "age": 35,
        "income": 45000,
        "credit_score": 620,
        "denied": True,
        "denial_reason": "credit_score_too_low",
    }

    async with httpx.AsyncClient(timeout=300.0) as client:
        print("\n=== STEP 1: Create Investigation with applicant_data ===")

        request_body = {
            "query": "Test investigation with applicant data",
            "date_from": "2026-01-01",
            "date_to": "2026-12-31",
            "applicant_data": applicant_data
        }

        print(f"[DEBUG] Request body type: {type(request_body)}")
        print(f"[DEBUG] applicant_data in request: {request_body.get('applicant_data')}")
        print(f"[DEBUG] JSON being sent:")
        print(json.dumps(request_body, indent=2))

        r1 = await client.post(
            f"{API_URL}/api/v1/investigations",
            json=request_body,
            headers={"X-API-Key": API_KEY, "X-Tenant-ID": "test-tenant"}
        )

        print(f"\n[DEBUG] Response status: {r1.status_code}")
        inv_data = r1.json()
        inv_id = inv_data["investigation_id"]
        print(f"[DEBUG] Created investigation: {inv_id}")
        print(f"[DEBUG] Response:\n{json.dumps(inv_data, indent=2)}")

        # Wait a moment
        await asyncio.sleep(2)

        print("\n=== STEP 2: Fetch From Database ===")
        r2 = await client.get(
            f"{API_URL}/api/v1/investigations/{inv_id}",
            headers={"X-API-Key": API_KEY, "X-Tenant-ID": "test-tenant"}
        )

        fetch_data = r2.json()
        print(f"[DEBUG] Fetched investigation: {json.dumps(fetch_data, indent=2)}")

asyncio.run(test())
