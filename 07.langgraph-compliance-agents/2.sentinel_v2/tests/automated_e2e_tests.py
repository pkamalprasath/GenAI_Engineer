"""
Automated End-to-End Testing System for SENTINEL v2
Runs 7 scenario cases across 3 frameworks through the backend API and scores them.
Writes a text report, a JSON file and a Markdown scenario table to test_results/.
Requires the API running with PostgreSQL and Ollama (see README).
Run: python tests/automated_e2e_tests.py
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


def _normalise(label: Optional[str]) -> Optional[str]:
    """Compare labels case-insensitively and ignore surrounding whitespace."""
    if label is None:
        return None
    return str(label).strip().upper()


def score_case(
    test_case: Dict[str, Any],
    verdict: Optional[str],
    risk_level: Optional[str],
    report: Optional[str],
) -> Dict[str, Any]:
    """
    Score one scenario against its expected outcome.

    A case PASSES only if all of these hold:
      - a verdict was returned and it equals expected_verdict
      - a risk level was returned and it equals expected_risk
      - a non-empty final report was returned
    Anything else is FAILED, and the reasons are listed in "failure_reasons".

    (An earlier version marked a case PASSED whenever a verdict and a report
    existed, so wrong verdicts and wrong risk levels were counted as passes.)
    """
    expected_verdict = test_case.get("expected_verdict")
    expected_risk = test_case.get("expected_risk")

    verdict_match = verdict is not None and _normalise(verdict) == _normalise(expected_verdict)
    risk_match = risk_level is not None and _normalise(risk_level) == _normalise(expected_risk)
    report_generated = bool(report and str(report).strip())

    failure_reasons: List[str] = []
    if verdict is None:
        failure_reasons.append("no verdict returned")
    elif not verdict_match:
        failure_reasons.append(f"verdict {verdict} != expected {expected_verdict}")
    if risk_level is None:
        failure_reasons.append("no risk level returned")
    elif not risk_match:
        failure_reasons.append(f"risk {risk_level} != expected {expected_risk}")
    if not report_generated:
        failure_reasons.append("no report generated")

    return {
        "test_case_id": test_case.get("applicant_id"),
        "test_name": test_case.get("name"),
        "framework": test_case.get("framework"),
        "status": "PASSED" if not failure_reasons else "FAILED",
        "failure_reasons": failure_reasons,
        "verdict": verdict,
        "expected_verdict": expected_verdict,
        "verdict_match": verdict_match,
        "risk_level": risk_level,
        "expected_risk": expected_risk,
        "risk_match": risk_match,
        "report_generated": report_generated,
        "report_length": len(report) if report else 0,
        "report_preview": report[:200] if report else None,
        "error": None,
    }


def summarise(results: List[Dict[str, Any]]) -> Dict[str, int]:
    """Count outcomes. Only status == PASSED counts as a pass."""
    return {
        "total": len(results),
        "passed": sum(1 for r in results if r.get("status") == "PASSED"),
        "failed": sum(1 for r in results if r.get("status") == "FAILED"),
        "errors": sum(1 for r in results if r.get("status") == "ERROR"),
    }


def format_report(results: List[Dict[str, Any]]) -> str:
    """Plain-text report. Pass and fail come only from score_case()."""
    counts = summarise(results)
    rate = f"{100 * counts['passed'] / counts['total']:.0f}%" if counts["total"] else "n/a"
    lines = [
        "=" * 100,
        "SENTINEL v2 - END-TO-END SCENARIO REPORT",
        "=" * 100,
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Scenarios: {counts['total']}",
        f"Passed: {counts['passed']}",
        f"Failed: {counts['failed']}",
        f"Errors: {counts['errors']}",
        f"Pass rate: {counts['passed']}/{counts['total']} ({rate})",
        "A scenario passes only if verdict AND risk level match the expected values",
        "and a report was generated.",
        "",
    ]

    by_framework: Dict[str, List[Dict[str, Any]]] = {}
    for result in results:
        by_framework.setdefault(result.get("framework") or "Unknown", []).append(result)

    for framework, group in by_framework.items():
        passed = sum(1 for r in group if r.get("status") == "PASSED")
        lines.extend([
            "-" * 100,
            f"FRAMEWORK: {framework}  ({passed}/{len(group)} passed)",
            "-" * 100,
        ])
        for r in group:
            lines.append(f"[{r.get('status', 'ERROR'):6}] {r.get('test_case_id')!s:12} | {r.get('test_name')}")
            if r.get("status") == "ERROR":
                lines.append(f"   Error: {r.get('error')}")
            elif r.get("error"):
                lines.append(f"   Error: {r.get('error')}")
            else:
                lines.append(f"   Investigation: {r.get('investigation_id')}")
                lines.append(f"   Verdict: {r.get('verdict')} (expected {r.get('expected_verdict')})")
                lines.append(f"   Risk:    {r.get('risk_level')} (expected {r.get('expected_risk')})")
                lines.append(f"   Report:  {r.get('report_length', 0)} chars")
            for reason in r.get("failure_reasons") or []:
                lines.append(f"   Fail reason: {reason}")
            lines.append("")

    lines.append("=" * 100)
    return "\n".join(lines)


def format_markdown_table(results: List[Dict[str, Any]]) -> str:
    """Scenario table (scenario, expected, actual, pass/fail) for the README."""
    counts = summarise(results)
    rows = [
        "| Scenario | Expected verdict / risk | Actual verdict / risk | Result |",
        "|---|---|---|---|",
    ]
    for r in results:
        rows.append(
            f"| {r.get('test_case_id')} {r.get('test_name') or ''} "
            f"| {r.get('expected_verdict')} / {r.get('expected_risk')} "
            f"| {r.get('verdict')} / {r.get('risk_level')} "
            f"| {'pass' if r.get('status') == 'PASSED' else r.get('status', 'ERROR').lower()} |"
        )
    rows.append("")
    rows.append(f"Pass rate: {counts['passed']}/{counts['total']}")
    return "\n".join(rows) + "\n"


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

                scored = score_case(
                    test_case,
                    verdict=result.get("compliance_verdict"),
                    risk_level=result.get("regulatory_risk"),
                    report=result.get("final_report"),
                )
                scored["investigation_id"] = inv_id
                return scored

        except Exception as e:
            return {
                "test_case_id": test_case.get("applicant_id"),
                "test_name": test_case.get("name"),
                "framework": test_case.get("framework"),
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
            print(f"{result['status']} (verdict={result.get('verdict')}, risk={result.get('risk_level')})")

        self.test_results = results
        return results

    def generate_report(self) -> str:
        """Generate the text report (see format_report)."""
        return format_report(self.test_results)

    def save_report(self):
        """Save test report to file"""
        report = self.generate_report()
        report_file = self.report_dir / f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        report_file.write_text(report, encoding='utf-8')
        print(f"\n[REPORT] Saved to: {report_file}")
        print(report)

        # Also save JSON results and a Markdown scenario table for the README
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        json_file = self.report_dir / f"test_results_{stamp}.json"
        json_file.write_text(json.dumps(self.test_results, indent=2), encoding='utf-8')
        print(f"[RESULTS] Saved to: {json_file}")
        md_file = self.report_dir / f"scenario_table_{stamp}.md"
        md_file.write_text(format_markdown_table(self.test_results), encoding='utf-8')
        print(f"[TABLE] Saved to: {md_file}")


async def main() -> int:
    """Main test runner. Exit code is non-zero if any scenario did not pass."""
    runner = ComplianceTestRunner()
    await runner.run_all_tests()
    runner.save_report()
    counts = summarise(runner.test_results)
    return 0 if counts["total"] and counts["passed"] == counts["total"] else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
