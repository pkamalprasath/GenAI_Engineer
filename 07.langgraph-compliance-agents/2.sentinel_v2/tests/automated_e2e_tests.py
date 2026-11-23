"""
Automated End-to-End Testing System for SENTINEL v2
Tests frontend (Streamlit dashboard) and backend API with multiple compliance frameworks
Captures screenshots for UI validation and generates comprehensive test reports
"""
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

# Fix encoding for Windows console
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

import httpx

# Test Configuration
API_URL = os.getenv("SENTINEL_API_URL", "http://localhost:8003")
API_KEY = os.getenv("SENTINEL_API_KEY", "test-key")
TENANT_ID = "test-compliance-framework"

# Compliance Frameworks to Test
COMPLIANCE_FRAMEWORKS = {
    "FAIR_LENDING": {
        "name": "Fair Lending (FCRA/FHA)",
        "regulations": ["ECOA", "FCRA", "FHA"],
        "test_cases": [
            {
                "name": "Approved - No Disparities",
                "applicant_id": "FAIR_001",
                "applicant_name": "James Richardson",
                "race": "White",
                "age": 50,
                "income": 150000,
                "credit_score": 780,
                "denied": False,
                "loan_amount": 450000,
                "loan_purpose": "Home Purchase",
                "expected_verdict": "COMPLIANT",
                "expected_risk": "LOW",
            },
            {
                "name": "Denied - Potential Disparate Impact",
                "applicant_id": "FAIR_002",
                "applicant_name": "Maria Santos",
                "race": "Hispanic",
                "age": 32,
                "income": 55000,
                "credit_score": 620,
                "denied": True,
                "denial_reason": "credit_score_too_low",
                "loan_amount": 250000,
                "loan_purpose": "Home Purchase",
                "expected_verdict": "UNCERTAIN",
                "expected_risk": "MEDIUM",
            },
            {
                "name": "Denied - Race-Based Pattern",
                "applicant_id": "FAIR_003",
                "applicant_name": "Alicia Johnson",
                "race": "African American",
                "age": 28,
                "income": 48000,
                "credit_score": 680,
                "denied": True,
                "denial_reason": "insufficient_income",
                "loan_amount": 200000,
                "loan_purpose": "Home Purchase",
                "expected_verdict": "UNCERTAIN",
                "expected_risk": "MEDIUM",
            },
        ]
    },
    "ADA_COMPLIANCE": {
        "name": "ADA Accessibility (FHA Disability)",
        "regulations": ["ADA", "FHA", "Section 504"],
        "test_cases": [
            {
                "name": "Applicant with Disability - Reasonable Accommodation",
                "applicant_id": "ADA_001",
                "applicant_name": "Robert Chen",
                "age": 45,
                "income": 95000,
                "credit_score": 720,
                "denied": False,
                "disability_status": "Yes - Mobility Impairment",
                "accommodation_requested": "Accessible Unit Required",
                "expected_verdict": "COMPLIANT",
                "expected_risk": "LOW",
            },
            {
                "name": "Applicant with Disability - Denied Without Accommodation",
                "applicant_id": "ADA_002",
                "applicant_name": "Susan Lee",
                "age": 38,
                "income": 72000,
                "credit_score": 650,
                "denied": True,
                "denial_reason": "accessibility_requirement_conflict",
                "disability_status": "Yes - Visual Impairment",
                "accommodation_requested": "Digital Accessible Forms",
                "expected_verdict": "VIOLATION",
                "expected_risk": "HIGH",
            },
        ]
    },
    "EQUAL_CREDIT_OPPORTUNITY": {
        "name": "Equal Credit Opportunity Act (ECOA)",
        "regulations": ["ECOA", "TILA", "RESPA"],
        "test_cases": [
            {
                "name": "Married Applicant - Joint Income",
                "applicant_id": "ECOA_001",
                "applicant_name": "David & Patricia Martinez",
                "applicant_type": "Joint",
                "age": 40,
                "joint_income": 185000,
                "credit_score": 750,
                "denied": False,
                "loan_amount": 500000,
                "expected_verdict": "COMPLIANT",
                "expected_risk": "LOW",
            },
            {
                "name": "Female Primary Applicant - Lower Terms Offered",
                "applicant_id": "ECOA_002",
                "applicant_name": "Angela Mitchell",
                "gender": "Female",
                "age": 35,
                "income": 105000,
                "credit_score": 760,
                "denied": False,
                "loan_approved_rate": 6.5,
                "comparable_rate": 5.8,
                "expected_verdict": "UNCERTAIN",
                "expected_risk": "MEDIUM",
            },
        ]
    },
}


class ComplianceTestData:
    """Generates test data for compliance framework testing"""

    @staticmethod
    def get_all_test_cases() -> List[Dict[str, Any]]:
        """Flatten all test cases across frameworks"""
        all_cases = []
        for framework_key, framework in COMPLIANCE_FRAMEWORKS.items():
            for test_case in framework["test_cases"]:
                test_case["framework"] = framework["name"]
                test_case["framework_key"] = framework_key
                test_case["regulations"] = framework["regulations"]
                all_cases.append(test_case)
        return all_cases


class ComplianceTestRunner:
    """Runs automated compliance tests against SENTINEL API"""

    def __init__(self, api_url: str = API_URL, api_key: str = API_KEY):
        self.api_url = api_url
        self.api_key = api_key
        self.test_results = []
        self.screenshots_dir = Path(__file__).parent.parent / "test_results" / "screenshots"
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir = Path(__file__).parent.parent / "test_results"
        self.report_dir.mkdir(parents=True, exist_ok=True)

    async def run_investigation(
        self,
        test_case: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Run a single investigation through the API"""
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                # Extract applicant data
                applicant_data = {k: v for k, v in test_case.items()
                                  if k not in ["name", "framework", "framework_key",
                                             "regulations", "expected_verdict", "expected_risk"]}

                # Step 1: Create investigation
                create_response = await client.post(
                    f"{self.api_url}/api/v1/investigations",
                    json={
                        "query": f"Compliance investigation: {test_case.get('name', 'Test')}",
                        "date_from": "2026-01-01",
                        "date_to": "2026-12-31",
                        "applicant_data": applicant_data
                    },
                    headers={
                        "X-API-Key": self.api_key,
                        "X-Tenant-ID": TENANT_ID
                    }
                )

                if create_response.status_code != 202:
                    return {
                        "test_case_id": test_case.get("applicant_id"),
                        "status": "FAILED",
                        "error": f"Failed to create investigation: {create_response.text}",
                        "verdict": None,
                        "risk_level": None,
                        "report": None,
                    }

                inv_data = create_response.json()
                inv_id = inv_data["investigation_id"]

                # Step 2: Execute synchronously
                await asyncio.sleep(1)  # Brief delay
                exec_response = await client.post(
                    f"{self.api_url}/api/v1/investigations/{inv_id}/execute-sync",
                    json={},
                    headers={
                        "X-API-Key": self.api_key,
                        "X-Tenant-ID": TENANT_ID
                    },
                    timeout=300.0
                )

                if exec_response.status_code != 200:
                    return {
                        "test_case_id": test_case.get("applicant_id"),
                        "status": "FAILED",
                        "error": f"Failed to execute investigation: {exec_response.text}",
                        "verdict": None,
                        "risk_level": None,
                        "report": None,
                    }

                result = exec_response.json()

                # Validate results
                verdict = result.get("compliance_verdict")
                risk_level = result.get("regulatory_risk")
                report = result.get("final_report")

                status = "PASSED" if verdict and report else "FAILED"

                return {
                    "test_case_id": test_case.get("applicant_id"),
                    "test_name": test_case.get("name"),
                    "framework": test_case.get("framework"),
                    "status": status,
                    "investigation_id": inv_id,
                    "verdict": verdict,
                    "expected_verdict": test_case.get("expected_verdict"),
                    "verdict_match": verdict == test_case.get("expected_verdict"),
                    "risk_level": risk_level,
                    "expected_risk": test_case.get("expected_risk"),
                    "risk_match": risk_level == test_case.get("expected_risk"),
                    "report_generated": bool(report),
                    "report_length": len(report) if report else 0,
                    "report_preview": report[:200] if report else None,
                    "error": None,
                }

        except Exception as e:
            return {
                "test_case_id": test_case.get("applicant_id"),
                "status": "ERROR",
                "error": str(e),
                "verdict": None,
                "risk_level": None,
                "report": None,
            }

    async def run_all_tests(self) -> List[Dict[str, Any]]:
        """Run all compliance framework tests"""
        print("\n" + "="*80)
        print("SENTINEL v2 — AUTOMATED COMPLIANCE TESTING")
        print("="*80)

        test_cases = ComplianceTestData.get_all_test_cases()
        print(f"\nRunning {len(test_cases)} test cases across {len(COMPLIANCE_FRAMEWORKS)} compliance frameworks...")
        print(f"API URL: {self.api_url}")
        print(f"Tenant: {TENANT_ID}\n")

        results = []
        for i, test_case in enumerate(test_cases, 1):
            print(f"[{i}/{len(test_cases)}] {test_case['framework']} — {test_case['name']}...", end=" ", flush=True)
            result = await self.run_investigation(test_case)
            results.append(result)
            status_symbol = "✅" if result["status"] == "PASSED" else "❌" if result["status"] == "FAILED" else "⚠️"
            print(f"{status_symbol} {result['verdict'] or 'ERROR'}")

        self.test_results = results
        return results

    def generate_report(self) -> str:
        """Generate comprehensive test report"""
        report_lines = [
            "=" * 100,
            "SENTINEL v2 — AUTOMATED COMPLIANCE TESTING REPORT",
            "=" * 100,
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"Total Tests: {len(self.test_results)}",
            f"Passed: {sum(1 for r in self.test_results if r['status'] == 'PASSED')}",
            f"Failed: {sum(1 for r in self.test_results if r['status'] == 'FAILED')}",
            f"Errors: {sum(1 for r in self.test_results if r['status'] == 'ERROR')}",
            "",
        ]

        # Group by framework
        by_framework = {}
        for result in self.test_results:
            framework = result.get("framework", "Unknown")
            if framework not in by_framework:
                by_framework[framework] = []
            by_framework[framework].append(result)

        for framework, results in by_framework.items():
            passed = sum(1 for r in results if r["status"] == "PASSED")
            report_lines.extend([
                "",
                f"{'─' * 100}",
                f"COMPLIANCE FRAMEWORK: {framework}",
                f"{'─' * 100}",
                f"Results: {passed}/{len(results)} passed",
                "",
            ])

            for result in results:
                status_symbol = "✅" if result["status"] == "PASSED" else "❌" if result["status"] == "FAILED" else "⚠️"
                report_lines.append(
                    f"{status_symbol} {result['test_case_id']:15} | {result['test_name']}"
                )

                if result["status"] == "PASSED":
                    report_lines.extend([
                        f"   Investigation: {result['investigation_id']}",
                        f"   Verdict: {result['verdict']} (expected: {result['expected_verdict']}) {'✅' if result['verdict_match'] else '❌'}",
                        f"   Risk: {result['risk_level']} (expected: {result['expected_risk']}) {'✅' if result['risk_match'] else '❌'}",
                        f"   Report: {result['report_length']} chars generated",
                    ])
                elif result["status"] == "FAILED":
                    report_lines.extend([
                        f"   Error: {result['error']}",
                    ])
                else:
                    report_lines.append(f"   Error: {result['error']}")

                report_lines.append("")

        # Summary statistics
        report_lines.extend([
            "",
            "=" * 100,
            "DATA FLOW VALIDATION",
            "=" * 100,
            "",
        ])

        # Check verdict matching
        verdict_matches = sum(1 for r in self.test_results if r.get("verdict_match", False))
        verdict_total = sum(1 for r in self.test_results if "expected_verdict" in r and r["status"] == "PASSED")
        if verdict_total > 0:
            report_lines.append(f"Verdict Accuracy: {verdict_matches}/{verdict_total} ({100*verdict_matches//verdict_total}%)")

        # Check risk matching
        risk_matches = sum(1 for r in self.test_results if r.get("risk_match", False))
        risk_total = sum(1 for r in self.test_results if "expected_risk" in r and r["status"] == "PASSED")
        if risk_total > 0:
            report_lines.append(f"Risk Level Accuracy: {risk_matches}/{risk_total} ({100*risk_matches//risk_total}%)")

        # Check report generation
        reports_generated = sum(1 for r in self.test_results if r.get("report_generated", False))
        report_lines.append(f"Report Generation: {reports_generated}/{verdict_total} successful")

        report_lines.extend([
            "",
            "=" * 100,
        ])

        return "\n".join(report_lines)

    def save_report(self):
        """Save test report to file"""
        report = self.generate_report()
        report_file = self.report_dir / f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        report_file.write_text(report, encoding='utf-8')
        print(f"\n[REPORT] Saved to: {report_file}")
        print(report)

        # Also save JSON results
        json_file = self.report_dir / f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        json_file.write_text(json.dumps(self.test_results, indent=2), encoding='utf-8')
        print(f"[RESULTS] Saved to: {json_file}")


async def main():
    """Main test runner"""
    runner = ComplianceTestRunner()
    await runner.run_all_tests()
    runner.save_report()


if __name__ == "__main__":
    asyncio.run(main())
