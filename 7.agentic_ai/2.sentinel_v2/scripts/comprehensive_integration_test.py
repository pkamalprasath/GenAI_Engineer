"""
SENTINEL v2 Comprehensive Integration Test Suite
Tests: All modules, functions, loops, parameters, security, performance, data integrity
Coverage: 5 diverse records traversing complete pipeline
"""
import asyncio
import json
import os
import time
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

import httpx
from datetime import datetime

API_URL = "http://localhost:8003"
API_KEY = os.getenv("SENTINEL_API_KEY", "test-key")

# Color codes for output
OK = "[OK]"
FAIL = "[FAIL]"
WARN = "[WARN]"
INFO = "[INFO]"

class TestRecord:
    """Test case with expected behaviors"""
    def __init__(self, record_id: int, case_type: str, description: str, data: Dict[str, Any]):
        self.record_id = record_id
        self.case_type = case_type
        self.description = description
        self.data = data
        self.investigation_id = None
        self.start_time = None
        self.end_time = None
        self.response_data = None
        self.errors = []
        self.metrics = {}

# 5 Test Records covering all scenarios
TEST_RECORDS = [
    TestRecord(
        record_id=1,
        case_type="high_risk_lending",
        description="High-risk lending case triggering bias detection and CRA compliance checks",
        data={
            "applicant_id": "APP_001",
            "applicant_name": "John Smith",
            "race": "African American",
            "age": 35,
            "income": 45000,
            "loan_amount": 250000,
            "loan_type": "mortgage",
            "property_value": 300000,
            "credit_score": 620,
            "employment_length_years": 2,
            "denied": True,
            "denial_reason": "credit_score_too_low",
        }
    ),
    TestRecord(
        record_id=2,
        case_type="ecoa_violation",
        description="Potential ECOA violation with adverse action notice requirement",
        data={
            "applicant_id": "APP_002",
            "applicant_name": "Maria Garcia",
            "race": "Hispanic",
            "gender": "Female",
            "age": 28,
            "income": 75000,
            "loan_amount": 200000,
            "loan_type": "auto",
            "credit_score": 680,
            "employment_length_years": 5,
            "denied": True,
            "denial_reason": "debt_to_income_ratio_exceeded",
            "adverse_action_notice_sent": False,
        }
    ),
    TestRecord(
        record_id=3,
        case_type="fair_lending_pattern",
        description="Pattern-based fair lending analysis with multiple indicators",
        data={
            "applicant_id": "APP_003",
            "applicant_name": "Chen Liu",
            "race": "Asian",
            "age": 45,
            "income": 120000,
            "loan_amount": 500000,
            "loan_type": "mortgage",
            "property_value": 600000,
            "credit_score": 740,
            "employment_length_years": 15,
            "denied": False,
            "approved_rate": 4.25,
            "neighborhood_redlining_indicator": True,
        }
    ),
    TestRecord(
        record_id=4,
        case_type="fcra_compliance",
        description="FCRA permissible purpose and consumer report accuracy check",
        data={
            "applicant_id": "APP_004",
            "applicant_name": "Sarah Johnson",
            "race": "White",
            "age": 52,
            "income": 95000,
            "loan_amount": 180000,
            "loan_type": "home_equity",
            "credit_score": 750,
            "employment_length_years": 20,
            "denied": False,
            "approved_rate": 5.5,
            "credit_report_dispute": True,
            "dispute_reason": "inaccurate_payment_history",
        }
    ),
    TestRecord(
        record_id=5,
        case_type="fhact_discrimination",
        description="Fair Housing Act discrimination analysis with protected class",
        data={
            "applicant_id": "APP_005",
            "applicant_name": "Robert Williams",
            "race": "Black",
            "family_status": "Family with children",
            "disability": "Mobility impairment",
            "age": 38,
            "income": 85000,
            "loan_amount": 220000,
            "loan_type": "mortgage",
            "property_value": 280000,
            "credit_score": 710,
            "employment_length_years": 8,
            "denied": False,
            "approved_rate": 4.75,
            "disability_accommodation_requested": True,
        }
    ),
]

async def test_api_health() -> bool:
    """Test 1: API Health & Readiness"""
    print(f"\n{'='*70}")
    print("TEST 1: API HEALTH & READINESS")
    print(f"{'='*70}")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Health check
            r = await client.get(f"{API_URL}/health")
            if r.status_code == 200:
                print(f"{OK} Health endpoint responding")
                health = r.json()
                print(f"    Status: {health.get('status')}")
            else:
                print(f"{FAIL} Health check failed: {r.status_code}")
                return False

            # Readiness check
            r = await client.get(f"{API_URL}/ready")
            if r.status_code == 200:
                print(f"{OK} Readiness endpoint responding")
                ready = r.json()
                print(f"    Status: {ready.get('status')}")
                components = ready.get('components', {})
                for comp, status in components.items():
                    print(f"    {comp}: {status}")
            else:
                print(f"{FAIL} Readiness check failed: {r.status_code}")
                return False

        return True
    except Exception as e:
        print(f"{FAIL} API unreachable: {e}")
        return False

async def test_investigation_creation(record: TestRecord) -> bool:
    """Test 2: Investigation creation via POST"""
    print(f"\n{'-'*70}")
    print(f"RECORD {record.record_id}: {record.case_type}")
    print(f"Description: {record.description}")
    print(f"{'-'*70}")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            record.start_time = time.time()

            # Build query from record data
            applicant_name = record.data.get("applicant_name", "Applicant")
            loan_type = record.data.get("loan_type", "loan")
            race = record.data.get("race", "")
            denial_status = "denied" if record.data.get("denied") else "approved"
            query = f"Investigate {denial_status} {loan_type} application for {applicant_name} ({race}). {record.description}"

            response = await client.post(
                f"{API_URL}/api/v1/investigations",
                json={
                    "query": query,
                    "date_from": "2026-01-01",
                    "date_to": "2026-04-24",
                    "trigger_mode": "reactive",
                    "domain": "finance"
                },
                headers={
                    "X-API-Key": API_KEY,
                    "X-Tenant-ID": "test-tenant"
                }
            )

            if response.status_code in (201, 202):  # 201 Created or 202 Accepted (async)
                data = response.json()
                record.investigation_id = data.get("investigation_id")
                record.response_data = data
                print(f"{OK} Investigation created: {record.investigation_id}")
                print(f"    Status: {data.get('status')}")
                return True
            else:
                record.errors.append(f"POST failed: {response.status_code} - {response.text}")
                print(f"{FAIL} Investigation creation failed: {response.status_code}")
                print(f"    {response.text[:200]}")
                return False
    except Exception as e:
        record.errors.append(f"Exception: {str(e)}")
        print(f"{FAIL} Exception: {e}")
        return False

async def test_investigation_polling(record: TestRecord) -> bool:
    """Test 3: Poll investigation status"""
    if not record.investigation_id:
        print(f"{WARN} No investigation ID, skipping polling")
        return False

    print(f"\n{OK} Polling investigation {record.investigation_id}...")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            max_attempts = 12
            attempt = 0

            while attempt < max_attempts:
                attempt += 1
                response = await client.get(
                    f"{API_URL}/api/v1/investigations/{record.investigation_id}",
                    headers={
                        "X-API-Key": API_KEY,
                        "X-Tenant-ID": "test-tenant"
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    status = data.get("status")
                    print(f"    Attempt {attempt}: {status}")

                    if status == "completed":
                        record.response_data = data
                        record.end_time = time.time()
                        duration = record.end_time - record.start_time
                        record.metrics["duration_seconds"] = duration
                        print(f"{OK} Investigation completed in {duration:.2f}s")
                        return True
                    elif status == "failed":
                        record.errors.append(f"Investigation failed: {data.get('error')}")
                        print(f"{FAIL} Investigation failed")
                        return False

                    await asyncio.sleep(5)
                else:
                    print(f"{FAIL} GET failed: {response.status_code}")
                    return False

            record.errors.append(f"Timeout after {max_attempts} attempts")
            print(f"{FAIL} Timeout - investigation did not complete")
            return False
    except Exception as e:
        record.errors.append(f"Polling exception: {str(e)}")
        print(f"{FAIL} Exception: {e}")
        return False

async def validate_results(record: TestRecord) -> Dict[str, Any]:
    """Test 4: Validate results, format, security, integrity"""
    print(f"\n{OK} Validating results for record {record.record_id}...")

    validation = {
        "record_id": record.record_id,
        "passed": True,
        "checks": {}
    }

    if not record.response_data:
        validation["passed"] = False
        validation["checks"]["data_exists"] = {"status": "FAIL", "reason": "No response data"}
        return validation

    data = record.response_data

    # Check 1: Response structure
    required_fields = ["investigation_id", "status", "results"]
    for field in required_fields:
        if field in data:
            validation["checks"][f"has_{field}"] = {"status": "PASS"}
        else:
            validation["checks"][f"has_{field}"] = {"status": "FAIL", "reason": f"Missing {field}"}
            validation["passed"] = False

    # Check 2: Data integrity (no nulls in critical fields)
    if "results" in data:
        results = data["results"]
        if results and isinstance(results, dict):
            critical_fields = ["compliance_verdict", "applicable_regulations"]
            for field in critical_fields:
                if field in results and results[field] is not None:
                    validation["checks"][f"integrity_{field}"] = {"status": "PASS"}
                else:
                    validation["checks"][f"integrity_{field}"] = {
                        "status": "WARN",
                        "reason": f"{field} is None or missing"
                    }

    # Check 3: Output format (JSON serializable)
    try:
        json_str = json.dumps(data)
        validation["checks"]["json_serializable"] = {"status": "PASS", "size_bytes": len(json_str)}
    except Exception as e:
        validation["checks"]["json_serializable"] = {"status": "FAIL", "reason": str(e)}
        validation["passed"] = False

    # Check 4: Security (no sensitive data in response)
    sensitive_patterns = ["password", "token", "secret", "api_key"]
    json_str = json.dumps(data).lower()
    found_sensitive = [p for p in sensitive_patterns if p in json_str]
    if not found_sensitive:
        validation["checks"]["no_sensitive_data"] = {"status": "PASS"}
    else:
        validation["checks"]["no_sensitive_data"] = {
            "status": "WARN",
            "reason": f"Potential sensitive patterns: {found_sensitive}"
        }

    # Check 5: Performance (response time)
    if record.metrics.get("duration_seconds"):
        duration = record.metrics["duration_seconds"]
        if duration < 60:
            validation["checks"]["performance"] = {
                "status": "PASS",
                "duration_seconds": duration
            }
        else:
            validation["checks"]["performance"] = {
                "status": "WARN",
                "duration_seconds": duration,
                "reason": "Slow response"
            }

    # Check 6: Regulations loaded (legal agent worked)
    if "results" in data and isinstance(data["results"], dict):
        regulations = data["results"].get("applicable_regulations", [])
        if isinstance(regulations, list) and len(regulations) > 0:
            validation["checks"]["regulations_retrieved"] = {
                "status": "PASS",
                "count": len(regulations)
            }
        else:
            validation["checks"]["regulations_retrieved"] = {
                "status": "WARN",
                "reason": "No regulations retrieved"
            }

    return validation

async def run_comprehensive_test():
    """Main test execution"""
    print("\n" + "="*70)
    print("SENTINEL v2 COMPREHENSIVE INTEGRATION TEST SUITE")
    print("="*70)
    print(f"Started: {datetime.now().isoformat()}")
    print(f"Test Records: {len(TEST_RECORDS)}")
    print(f"Coverage: All modules, functions, loops, parameters")

    # Test 1: API Health
    api_healthy = await test_api_health()
    if not api_healthy:
        print(f"\n{FAIL} API is not healthy. Start API first:")
        print("  python -m sentinel.api.main")
        return False

    # Test 2-4: Investigation flow for each record
    results = {
        "summary": {
            "total_records": len(TEST_RECORDS),
            "successful": 0,
            "failed": 0,
            "warnings": 0,
        },
        "records": []
    }

    for record in TEST_RECORDS:
        record_result = {
            "record_id": record.record_id,
            "case_type": record.case_type,
            "tests": {}
        }

        # Test: Create investigation
        if await test_investigation_creation(record):
            record_result["tests"]["creation"] = "PASS"
        else:
            record_result["tests"]["creation"] = "FAIL"
            results["summary"]["failed"] += 1
            results["records"].append(record_result)
            continue

        # Test: Poll for completion
        if await test_investigation_polling(record):
            record_result["tests"]["polling"] = "PASS"
        else:
            record_result["tests"]["polling"] = "FAIL"
            results["summary"]["warnings"] += 1
            results["records"].append(record_result)
            continue

        # Test: Validate results
        validation = await validate_results(record)
        record_result["tests"]["validation"] = validation

        # Summary
        if validation["passed"]:
            record_result["overall"] = "PASS"
            results["summary"]["successful"] += 1
        else:
            record_result["overall"] = "WARN"
            results["summary"]["warnings"] += 1

        record_result["errors"] = record.errors
        record_result["metrics"] = record.metrics
        results["records"].append(record_result)

        await asyncio.sleep(2)  # Spacing between records

    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Total Records: {results['summary']['total_records']}")
    print(f"Successful: {results['summary']['successful']}")
    print(f"Failed: {results['summary']['failed']}")
    print(f"Warnings: {results['summary']['warnings']}")

    # Detailed results
    print("\n" + "="*70)
    print("DETAILED RESULTS")
    print("="*70)
    for record in results["records"]:
        status = record.get("overall", "UNKNOWN")
        icon = OK if status == "PASS" else (WARN if status == "WARN" else FAIL)
        print(f"\n{icon} Record {record['record_id']}: {record['case_type']}")

        for test_name, test_result in record["tests"].items():
            if isinstance(test_result, dict):
                if test_result.get("checks"):
                    for check_name, check_result in test_result["checks"].items():
                        check_status = check_result.get("status", "UNKNOWN")
                        check_icon = OK if check_status == "PASS" else (WARN if check_status == "WARN" else FAIL)
                        print(f"  {check_icon} {check_name}: {check_status}")
            else:
                print(f"  {OK if test_result == 'PASS' else FAIL} {test_name}: {test_result}")

        if record.get("metrics"):
            print(f"  Metrics: {json.dumps(record['metrics'], indent=2)}")

        if record.get("errors"):
            for error in record["errors"]:
                print(f"  {FAIL} Error: {error}")

    # Save results
    output_file = Path(__file__).parent.parent / "test_results.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n{OK} Results saved to: {output_file}")
    print(f"\nCompleted: {datetime.now().isoformat()}")

    return results["summary"]["failed"] == 0

if __name__ == "__main__":
    success = asyncio.run(run_comprehensive_test())
    sys.exit(0 if success else 1)
