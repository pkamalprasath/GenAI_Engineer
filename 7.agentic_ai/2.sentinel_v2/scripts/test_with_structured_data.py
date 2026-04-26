"""
SENTINEL v2 Integration Test with Structured Applicant Data
Tests full pipeline with complete applicant information for comprehensive compliance analysis
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
        "query": "Investigate high-risk mortgage lending case with potential bias and CRA compliance concerns",
        "applicant_data": {
            "applicant_id": "APP_001",
            "applicant_name": "John Smith",
            "race": "African American",
            "gender": "Male",
            "age": 35,
            "income": 45000,
            "loan_amount": 250000,
            "loan_type": "mortgage",
            "property_value": 300000,
            "credit_score": 620,
            "employment_length_years": 2,
            "denied": True,
            "denial_reason": "credit_score_too_low",
            "debt_to_income_ratio": 0.85,
            "loan_purpose": "home_purchase",
            "property_type": "single_family",
            "down_payment_percent": 10,
            "other_applicants": []
        }
    },
    {
        "name": "ecoa_violation",
        "query": "Investigate potential ECOA violation with missing adverse action notice",
        "applicant_data": {
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
            "debt_to_income_ratio": 0.95,
            "loan_purpose": "vehicle_purchase",
            "vehicle_value": 180000,
            "down_payment_percent": 15,
            "other_applicants": [
                {
                    "name": "Carlos Garcia",
                    "race": "Hispanic",
                    "relationship": "spouse",
                    "income": 55000
                }
            ]
        }
    },
    {
        "name": "fair_lending_pattern",
        "query": "Analyze fair lending patterns with redlining indicators and approval rate disparities",
        "applicant_data": {
            "applicant_id": "APP_003",
            "applicant_name": "Chen Liu",
            "race": "Asian",
            "gender": "Male",
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
            "zip_code_median_income": 55000,
            "neighborhood_minority_percent": 65,
            "debt_to_income_ratio": 0.45,
            "loan_purpose": "home_purchase",
            "property_type": "single_family",
            "down_payment_percent": 25,
            "other_applicants": []
        }
    },
    {
        "name": "fcra_compliance",
        "query": "Verify FCRA compliance with credit report accuracy and permissible purpose",
        "applicant_data": {
            "applicant_id": "APP_004",
            "applicant_name": "Sarah Johnson",
            "race": "White",
            "gender": "Female",
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
            "num_tradelines": 12,
            "num_inquiries_90days": 2,
            "debt_to_income_ratio": 0.35,
            "loan_purpose": "debt_consolidation",
            "credit_bureau_pulled": ["Equifax", "Experian", "TransUnion"],
            "other_applicants": []
        }
    },
    {
        "name": "fhact_discrimination",
        "query": "Assess Fair Housing Act compliance with protected class considerations and accommodation",
        "applicant_data": {
            "applicant_id": "APP_005",
            "applicant_name": "Robert Williams",
            "race": "Black",
            "gender": "Male",
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
            "accommodation_type": "extended_closing_timeline",
            "num_children": 2,
            "debt_to_income_ratio": 0.55,
            "loan_purpose": "home_purchase",
            "property_type": "single_family",
            "down_payment_percent": 20,
            "other_applicants": []
        }
    },
]

async def create_investigation(client: httpx.AsyncClient, query: str, applicant_data: Dict[str, Any]) -> str:
    """Create investigation with structured applicant data"""
    response = await client.post(
        f"{API_URL}/api/v1/investigations",
        json={
            "query": query,
            "date_from": "2026-01-01",
            "date_to": "2026-04-25",
            "trigger_mode": "reactive",
            "domain": "finance",
            "applicant_data": applicant_data  # Send structured data
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
        raise Exception(f"Failed to create investigation: {response.status_code} - {response.text[:300]}")

async def execute_investigation(client: httpx.AsyncClient, investigation_id: str, applicant_data: Dict[str, Any]) -> Dict[str, Any]:
    """Execute investigation synchronously"""
    response = await client.post(
        f"{API_URL}/api/v1/investigations/{investigation_id}/execute-sync",
        json={"applicant_data": applicant_data},
        headers={
            "X-API-Key": API_KEY,
            "X-Tenant-ID": "test-tenant"
        }
    )
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to execute investigation: {response.status_code} - {response.text[:300]}")

async def main():
    print("="*80)
    print("SENTINEL v2 COMPREHENSIVE INTEGRATION TEST WITH STRUCTURED APPLICANT DATA")
    print("="*80)
    print(f"Started: {datetime.now().isoformat()}")
    print(f"Test Records: {len(test_records)}")
    print(f"Mode: Synchronous (blocking execution)")
    print(f"Data: Complete structured applicant information included")

    # Health check
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{API_URL}/health")
            if response.status_code != 200:
                print(f"{FAIL} API health check failed")
                return False
            print(f"{OK} API health check passed\n")
        except Exception as e:
            print(f"{FAIL} API unreachable: {e}")
            return False

    results = {
        "total": len(test_records),
        "successful": 0,
        "failed": 0,
        "warnings": 0,
        "records": []
    }

    async with httpx.AsyncClient(timeout=300.0) as client:  # 5 min timeout per investigation
        for record_data in test_records:
            record_name = record_data["name"]
            query = record_data["query"]
            applicant_data = record_data["applicant_data"]

            print(f"{'-'*80}")
            print(f"TEST: {record_name.upper()}")
            print(f"{'-'*80}")
            print(f"Applicant: {applicant_data.get('applicant_name')}")
            print(f"  Race: {applicant_data.get('race')}")
            print(f"  Age: {applicant_data.get('age')}")
            print(f"  Income: ${applicant_data.get('income'):,}")
            print(f"  Credit Score: {applicant_data.get('credit_score')}")
            print(f"  Loan Amount: ${applicant_data.get('loan_amount'):,}")
            print(f"  Status: {'DENIED' if applicant_data.get('denied') else 'APPROVED'}")

            try:
                # Step 1: Create investigation with structured data
                print(f"\n[...] Creating investigation with applicant data...")
                investigation_id = await create_investigation(client, query, applicant_data)
                print(f"{OK} Created: {investigation_id}")

                # Step 2: Execute synchronously
                print(f"[...] Executing investigation (analyzing compliance, bias, regulatory risk)...")
                result = await execute_investigation(client, investigation_id, applicant_data)

                status = result.get("status", "unknown")
                print(f"{OK} Execution completed: status={status}")

                # Step 3: Validate and display results
                print(f"\n[RESULTS]")

                # Compliance verdict
                verdict = result.get("compliance_verdict")
                if verdict:
                    icon = OK if verdict in ["PASS", "COMPLIANT"] else FAIL
                    print(f"  {icon} Compliance Verdict: {verdict}")
                else:
                    print(f"  {WARN} Compliance Verdict: NOT GENERATED")

                # Regulatory risk
                risk = result.get("regulatory_risk")
                if risk:
                    print(f"  {OK} Regulatory Risk: {risk}")
                else:
                    print(f"  {WARN} Regulatory Risk: NOT ASSESSED")

                # Bias detection
                bias = result.get("bias_detected")
                bias_conf = result.get("bias_confidence", 0.0)
                if bias is not None:
                    icon = FAIL if bias else OK
                    print(f"  {icon} Bias Detected: {bias} (confidence: {bias_conf:.2%})")
                else:
                    print(f"  {WARN} Bias Detection: NOT COMPLETED")

                # Report
                report = result.get("final_report")
                if report:
                    print(f"  {OK} Report Generated: {len(report)} characters")
                    print(f"      Preview: {report[:200]}...")
                else:
                    print(f"  {WARN} Report: NOT GENERATED")

                # HITL requirement
                hitl = result.get("hitl_required")
                if hitl:
                    print(f"  {WARN} HITL Required: {hitl}")

                # Confidence
                confidence = result.get("report_confidence", 0.0)
                print(f"  {OK} Confidence: {confidence:.2%}")

                # Evidence
                evidence_count = result.get("evidence_count", 0)
                print(f"  {OK} Evidence Items: {evidence_count}")

                # Errors
                error_log = result.get("error_log", [])
                if error_log:
                    print(f"  {FAIL} Errors: {len(error_log)}")
                    for err in error_log[:3]:
                        print(f"      - {err[:100]}")
                else:
                    print(f"  {OK} No Errors")

                # Overall result
                verdict_valid = verdict and verdict not in ["UNKNOWN", ""]
                report_valid = report and len(report) > 100
                risk_valid = risk and risk not in ["UNKNOWN", ""]

                if verdict_valid and report_valid and risk_valid:
                    results["successful"] += 1
                    status_icon = OK
                    status_text = "PASSED"
                elif error_log:
                    results["failed"] += 1
                    status_icon = FAIL
                    status_text = "FAILED"
                else:
                    results["warnings"] += 1
                    status_icon = WARN
                    status_text = "PASSED WITH WARNINGS"

                print(f"\n{status_icon} Overall: {status_text}")

                results["records"].append({
                    "name": record_name,
                    "investigation_id": investigation_id,
                    "status": status,
                    "compliance_verdict": verdict,
                    "regulatory_risk": risk,
                    "bias_detected": bias,
                    "bias_confidence": bias_conf,
                    "report_generated": bool(report),
                    "evidence_count": evidence_count,
                    "errors": error_log,
                    "overall": status_text
                })

            except Exception as e:
                results["failed"] += 1
                error_msg = str(e)[:300]
                print(f"{FAIL} Exception: {error_msg}")
                print(f"{FAIL} Overall: FAILED")
                results["records"].append({
                    "name": record_name,
                    "error": error_msg,
                    "status": "failed",
                    "overall": "FAILED"
                })

            print()

    # Summary
    print("="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Total Records:  {results['total']}")
    print(f"Successful:     {results['successful']}")
    print(f"With Warnings:  {results['warnings']}")
    print(f"Failed:         {results['failed']}")
    print(f"Pass Rate:      {(results['successful'] + results['warnings']) / results['total'] * 100:.1f}%")

    # Save results
    output_file = Path(__file__).parent.parent / "test_structured_results.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n{OK} Results saved to: {output_file}")

    print(f"\nCompleted: {datetime.now().isoformat()}")

    # Return success if no critical failures
    return results["failed"] == 0

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
