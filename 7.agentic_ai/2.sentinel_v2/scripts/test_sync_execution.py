"""
SENTINEL v2 Synchronous Execution Test
Tests full pipeline: Create investigation → Execute sync → Validate results
"""
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

import httpx
from datetime import datetime

API_URL = "http://localhost:8003"
API_KEY = os.getenv("SENTINEL_API_KEY", "test-key")

# Color codes
OK = "[OK]"
FAIL = "[FAIL]"
WARN = "[WARN]"

test_records = [
    {
        "name": "high_risk_lending",
        "query": "Investigate denied mortgage application for John Smith (African American). High-risk lending case triggering bias detection and CRA compliance checks"
    },
    {
        "name": "ecoa_violation",
        "query": "Investigate denied auto loan for Maria Garcia (Hispanic). Potential ECOA violation with adverse action notice requirement"
    },
    {
        "name": "fair_lending_pattern",
        "query": "Investigate approved mortgage for Chen Liu (Asian). Pattern-based fair lending analysis with multiple indicators and neighborhood redlining"
    },
    {
        "name": "fcra_compliance",
        "query": "Investigate approved home equity for Sarah Johnson (White). FCRA permissible purpose and consumer report accuracy check"
    },
    {
        "name": "fhact_discrimination",
        "query": "Investigate approved mortgage for Robert Williams (Black). Fair Housing Act discrimination analysis with protected class and disability accommodation"
    },
]

async def create_investigation(client: httpx.AsyncClient, query: str) -> str:
    """Create investigation and return ID"""
    response = await client.post(
        f"{API_URL}/api/v1/investigations",
        json={
            "query": query,
            "date_from": "2026-01-01",
            "date_to": "2026-04-25",
            "trigger_mode": "reactive",
            "domain": "finance"
        },
        headers={
            "X-API-Key": API_KEY,
            "X-Tenant-ID": "test-tenant"
        }
    )
    if response.status_code in (201, 202):
        data = response.json()
        return data.get("investigation_id")
    else:
        raise Exception(f"Failed to create investigation: {response.status_code} - {response.text[:200]}")

async def execute_investigation(client: httpx.AsyncClient, investigation_id: str) -> Dict[str, Any]:
    """Execute investigation synchronously"""
    response = await client.post(
        f"{API_URL}/api/v1/investigations/{investigation_id}/execute-sync",
        headers={
            "X-API-Key": API_KEY,
            "X-Tenant-ID": "test-tenant"
        }
    )
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to execute investigation: {response.status_code} - {response.text[:200]}")

async def main():
    print("="*70)
    print("SENTINEL v2 SYNCHRONOUS EXECUTION TEST")
    print("="*70)
    print(f"Started: {datetime.now().isoformat()}")
    print(f"Test Records: {len(test_records)}")
    print(f"Mode: Synchronous (blocking execution)")

    # Health check
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{API_URL}/health")
            if response.status_code != 200:
                print(f"{FAIL} API health check failed")
                return False
            print(f"{OK} API health check passed")
        except Exception as e:
            print(f"{FAIL} API unreachable: {e}")
            return False

    results = {
        "total": len(test_records),
        "successful": 0,
        "failed": 0,
        "records": []
    }

    async with httpx.AsyncClient(timeout=300.0) as client:  # 5 min timeout per investigation
        for record_data in test_records:
            record_name = record_data["name"]
            query = record_data["query"]

            print(f"\n{'-'*70}")
            print(f"TEST: {record_name}")
            print(f"Query: {query[:100]}...")
            print(f"{'-'*70}")

            try:
                # Step 1: Create investigation
                print(f"[...] Creating investigation...")
                investigation_id = await create_investigation(client, query)
                print(f"{OK} Created: {investigation_id}")

                # Step 2: Execute synchronously
                print(f"[...] Executing investigation (this may take 1-5 minutes)...")
                result = await execute_investigation(client, investigation_id)

                status = result.get("status", "unknown")
                print(f"{OK} Execution completed: status={status}")

                # Step 3: Validate results
                print(f"[...] Validating results...")
                validation_passed = True
                checks = {}

                # Check required fields
                if result.get("compliance_verdict"):
                    checks["compliance_verdict"] = "PASS"
                else:
                    checks["compliance_verdict"] = "FAIL"
                    validation_passed = False

                if result.get("regulatory_risk"):
                    checks["regulatory_risk"] = "PASS"
                else:
                    checks["regulatory_risk"] = "WARN"

                if result.get("final_report") or result.get("agent_events"):
                    checks["report_generated"] = "PASS"
                else:
                    checks["report_generated"] = "WARN"
                    validation_passed = False

                # Check error log
                error_log = result.get("error_log", [])
                if not error_log:
                    checks["no_errors"] = "PASS"
                else:
                    checks["no_errors"] = "WARN"
                    print(f"  Errors: {error_log[:2]}")

                # Print validation results
                for check_name, check_status in checks.items():
                    icon = OK if check_status == "PASS" else WARN
                    print(f"  {icon} {check_name}: {check_status}")

                if validation_passed:
                    results["successful"] += 1
                    print(f"{OK} Record PASSED")
                else:
                    results["failed"] += 1
                    print(f"{WARN} Record PASSED with warnings")

                results["records"].append({
                    "name": record_name,
                    "investigation_id": investigation_id,
                    "status": status,
                    "validation_passed": validation_passed,
                    "checks": checks
                })

            except Exception as e:
                results["failed"] += 1
                print(f"{FAIL} Exception: {str(e)[:200]}")
                results["records"].append({
                    "name": record_name,
                    "error": str(e)[:200],
                    "status": "failed"
                })

    # Summary
    print(f"\n{'='*70}")
    print("TEST SUMMARY")
    print(f"{'='*70}")
    print(f"Total: {results['total']}")
    print(f"Successful: {results['successful']}")
    print(f"Failed: {results['failed']}")

    # Save results
    output_file = Path(__file__).parent.parent / "test_sync_results.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"{OK} Results saved to: {output_file}")

    print(f"\nCompleted: {datetime.now().isoformat()}")
    return results["failed"] == 0

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
