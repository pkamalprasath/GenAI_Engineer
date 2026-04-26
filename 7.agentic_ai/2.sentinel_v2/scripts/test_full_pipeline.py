"""
Test full pipeline with applicant_data
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
    applicant_data_list = [
        {
            "applicant_id": "APP_APPROVE_001",
            "applicant_name": "John Smith",
            "race": "White",
            "age": 45,
            "income": 120000,
            "credit_score": 750,
            "denied": False,
            "denial_reason": None,
        },
        {
            "applicant_id": "APP_DENY_001",
            "applicant_name": "Jane Doe",
            "race": "African American",
            "age": 35,
            "income": 45000,
            "credit_score": 620,
            "denied": True,
            "denial_reason": "credit_score_too_low",
        },
        {
            "applicant_id": "APP_DENY_002",
            "applicant_name": "Maria Garcia",
            "race": "Hispanic",
            "age": 28,
            "income": 35000,
            "credit_score": 580,
            "denied": True,
            "denial_reason": "insufficient_income",
        },
    ]

    results = []

    async with httpx.AsyncClient(timeout=300.0) as client:
        for applicant_data in applicant_data_list:
            print(f"\n{'='*60}")
            print(f"Testing: {applicant_data['applicant_id']} ({applicant_data['applicant_name']})")
            print(f"{'='*60}")

            # Step 1: Create investigation
            print("\n[STEP 1] Creating investigation with applicant_data...")
            r1 = await client.post(
                f"{API_URL}/api/v1/investigations",
                json={
                    "query": f"Compliance investigation for {applicant_data['applicant_name']}",
                    "date_from": "2026-01-01",
                    "date_to": "2026-12-31",
                    "applicant_data": applicant_data
                },
                headers={"X-API-Key": API_KEY, "X-Tenant-ID": "test-tenant"}
            )
            inv_data = r1.json()
            inv_id = inv_data["investigation_id"]
            print(f"[OK] Investigation created: {inv_id}")

            # Step 2: Execute synchronously
            print("\n[STEP 2] Executing investigation synchronously...")
            r2 = await client.post(
                f"{API_URL}/api/v1/investigations/{inv_id}/execute-sync",
                json={},
                headers={"X-API-Key": API_KEY, "X-Tenant-ID": "test-tenant"},
                timeout=300.0
            )

            result = r2.json()
            results.append({
                "applicant_id": applicant_data["applicant_id"],
                "investigation_id": inv_id,
                "status": result.get("status"),
                "case_count": result.get("case_count"),
                "compliance_verdict": result.get("compliance_verdict"),
                "bias_detected": result.get("bias_detected"),
                "regulatory_risk": result.get("regulatory_risk"),
                "has_report": bool(result.get("final_report")),
                "discovery_confidence": result.get("discovery_confidence"),
            })

            print(f"[DEBUG] Status: {result.get('status')}")
            print(f"[DEBUG] Case Count: {result.get('case_count')}")
            print(f"[DEBUG] Compliance Verdict: {result.get('compliance_verdict')}")
            print(f"[DEBUG] Bias Detected: {result.get('bias_detected')}")
            print(f"[DEBUG] Regulatory Risk: {result.get('regulatory_risk')}")
            print(f"[DEBUG] Report Generated: {bool(result.get('final_report'))}")

            await asyncio.sleep(1)

        # Print summary
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        for r in results:
            print(f"\n{r['applicant_id']}:")
            print(f"  Investigation: {r['investigation_id']}")
            print(f"  Status: {r['status']}")
            print(f"  Cases Found: {r['case_count']}")
            print(f"  Compliance: {r['compliance_verdict']}")
            print(f"  Bias: {r['bias_detected']}")
            print(f"  Risk Level: {r['regulatory_risk']}")
            print(f"  Report: {'YES' if r['has_report'] else 'NO'}")

asyncio.run(test())
