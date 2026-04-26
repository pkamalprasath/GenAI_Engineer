"""
SENTINEL v2 Diagnostic Test
Runs a single investigation and dumps full state to show what agents are producing
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
from datetime import datetime

API_URL = "http://localhost:8003"
API_KEY = os.getenv("SENTINEL_API_KEY", "test-key")

async def run_diagnostic():
    """Run single investigation and show all agent outputs"""

    print("="*80)
    print("SENTINEL v2 DIAGNOSTIC TEST - Single Record Full State Inspection")
    print("="*80)
    print(f"Started: {datetime.now().isoformat()}\n")

    applicant_data = {
        "applicant_id": "DIAG_001",
        "applicant_name": "Test Applicant",
        "race": "African American",
        "age": 35,
        "income": 45000,
        "loan_amount": 250000,
        "loan_type": "mortgage",
        "credit_score": 620,
        "employment_length_years": 2,
        "denied": True,
        "denial_reason": "credit_score_too_low",
        "debt_to_income_ratio": 0.85,
    }

    query = "Comprehensive compliance analysis of mortgage application for African American applicant with low credit score"

    async with httpx.AsyncClient(timeout=300.0) as client:
        # Create investigation
        print("[1/3] CREATING INVESTIGATION...")
        print(f"Query: {query}")
        print(f"Applicant: {applicant_data['applicant_name']} ({applicant_data['race']})")
        print(f"Applicant Data Fields: {list(applicant_data.keys())}")

        response = await client.post(
            f"{API_URL}/api/v1/investigations",
            json={
                "query": query,
                "date_from": "2026-01-01",
                "date_to": "2026-12-31",
                "trigger_mode": "reactive",
                "domain": "finance",
                "applicant_data": applicant_data
            },
            headers={
                "X-API-Key": API_KEY,
                "X-Tenant-ID": "test-tenant"
            }
        )

        if response.status_code not in (201, 202):
            print(f"[FAIL] Investigation creation failed: {response.status_code}")
            print(response.text)
            return

        inv_data = response.json()
        investigation_id = inv_data["investigation_id"]
        print(f"[OK] Investigation created: {investigation_id}\n")

        # Execute investigation
        print("[2/3] EXECUTING INVESTIGATION (synchronously)...")
        response = await client.post(
            f"{API_URL}/api/v1/investigations/{investigation_id}/execute-sync",
            json={"applicant_data": applicant_data},
            headers={
                "X-API-Key": API_KEY,
                "X-Tenant-ID": "test-tenant"
            },
            timeout=300.0
        )

        if response.status_code != 200:
            print(f"[FAIL] Execution failed: {response.status_code}")
            print(response.text[:500])
            return

        result = response.json()
        print(f"[OK] Execution completed\n")

        # Display comprehensive results
        print("[3/3] FULL STATE INSPECTION")
        print("="*80)

        print("\n[INVESTIGATION METADATA]")
        print(f"  Investigation ID: {result.get('investigation_id')}")
        print(f"  Status: {result.get('status')}")
        print(f"  Total Cost: ${result.get('total_cost_usd', 0):.6f}")

        print("\n[DISCOVERY AGENT OUTPUTS]")
        print(f"  Case Count: {result.get('case_count', 0)}")
        print(f"  Discovery Confidence: {result.get('discovery_confidence', 0):.2%}")
        print(f"  Relevant Cases: {result.get('relevant_case_ids', [])}")

        print("\n[LEGAL ANALYSIS OUTPUTS]")
        compliance_verdict = result.get('compliance_verdict')
        print(f"  Compliance Verdict: {compliance_verdict if compliance_verdict else '[NOT GENERATED]'}")
        regulatory_risk = result.get('regulatory_risk')
        print(f"  Regulatory Risk: {regulatory_risk if regulatory_risk else '[NOT ASSESSED]'}")
        regulations = result.get('applicable_regulations', [])
        print(f"  Applicable Regulations: {len(regulations)} found")
        if regulations:
            for i, reg in enumerate(regulations[:3], 1):
                print(f"    {i}. {reg}")
        citations = result.get('legal_citations', [])
        print(f"  Legal Citations: {len(citations)} found")

        print("\n[BIAS DETECTION OUTPUTS]")
        bias = result.get('bias_detected', False)
        bias_conf = result.get('bias_confidence', 0.0)
        print(f"  Bias Detected: {bias}")
        print(f"  Bias Confidence: {bias_conf:.2%}")
        dimensions = result.get('bias_dimensions_checked', [])
        print(f"  Dimensions Checked: {dimensions}")
        findings = result.get('statistical_findings', [])
        print(f"  Statistical Findings: {len(findings)} found")
        if findings:
            for i, finding in enumerate(findings[:3], 1):
                print(f"    {i}. {finding.get('dimension', 'unknown')}: {finding.get('finding', '...')[:80]}")

        print("\n[REPORT GENERATION OUTPUTS]")
        draft_report = result.get('draft_report')
        print(f"  Draft Report: {'[GENERATED] (' + str(len(draft_report)) + ' chars)' if draft_report else '[NOT GENERATED]'}")
        if draft_report:
            print(f"    Preview: {draft_report[:200]}...")

        final_report = result.get('final_report')
        print(f"  Final Report: {'[GENERATED] (' + str(len(final_report)) + ' chars)' if final_report else '[NOT GENERATED]'}")
        if final_report:
            print(f"    Preview: {final_report[:200]}...")

        report_conf = result.get('report_confidence', 0.0)
        print(f"  Report Confidence: {report_conf:.2%}")

        print("\n[INVESTIGATION OUTPUTS]")
        evidence = result.get('evidence_items', [])
        print(f"  Evidence Items: {len(evidence)} found")
        if evidence:
            for i, item in enumerate(evidence[:3], 1):
                print(f"    {i}. {item.get('description', '...')[:80]}")

        sufficient = result.get('investigation_sufficient')
        print(f"  Investigation Sufficient: {sufficient}")

        print("\n[ERROR TRACKING]")
        errors = result.get('error_log', [])
        print(f"  Errors: {len(errors)} found")
        if errors:
            for i, error in enumerate(errors[:5], 1):
                print(f"    {i}. {error[:120]}")

        print("\n[AGENT EVENTS]")
        messages = result.get('agent_events', [])
        print(f"  Total Messages: {len(messages)}")
        if messages:
            print("  Recent Events:")
            for i, msg in enumerate(messages[-10:], 1):
                msg_type = msg.get('event', 'unknown') if isinstance(msg, dict) else str(msg)[:50]
                print(f"    {i}. {msg_type}")

        print("\n[EXECUTION SUMMARY]")
        print(f"  HITL Required: {result.get('hitl_required', False)}")
        heartbeats = result.get('heartbeats', [])
        print(f"  Agent Heartbeats: {len(heartbeats)} recorded")

        # Save full state for inspection
        output_file = Path(__file__).parent.parent / "diagnostic_full_state.json"
        with open(output_file, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\n✅ Full state saved to: {output_file}")

        # Analysis
        print("\n" + "="*80)
        print("ANALYSIS")
        print("="*80)

        missing_outputs = []
        if not compliance_verdict:
            missing_outputs.append("compliance_verdict")
        if not regulatory_risk:
            missing_outputs.append("regulatory_risk")
        if not final_report:
            missing_outputs.append("final_report")
        if not bias:
            missing_outputs.append("bias_detected (no bias found)")

        if missing_outputs:
            print(f"\n[WARNING] MISSING OUTPUTS: {', '.join(missing_outputs)}")
            print("\nPossible Causes:")
            print("  1. Agents don't have prompts to use applicant_data field")
            print("  2. Graph exits early due to error or condition")
            print("  3. Agent logic needs enhancement to process structured data")
            print("  4. LLM responses not being properly parsed/stored")
        else:
            print("\n[OK] All expected outputs generated!")

        print(f"\nCompleted: {datetime.now().isoformat()}")

if __name__ == "__main__":
    asyncio.run(run_diagnostic())
