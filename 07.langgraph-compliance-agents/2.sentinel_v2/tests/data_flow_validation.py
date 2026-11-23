"""
Data Flow Validation Tests for SENTINEL v2
Validates that data flows correctly through the entire system:
API → Database → Graph → Agents → Results
"""
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import httpx

from configs.settings import settings

# Test Configuration
API_URL = settings.active_domain if hasattr(settings, 'active_domain') else "http://localhost:8003"
API_KEY = "test-key"
TENANT_ID = "data-flow-test"


class DataFlowValidator:
    """Validates data flow through SENTINEL system"""

    def __init__(self):
        self.test_results = []
        self.db_engine = None

    async def init_db(self):
        """Initialize database connection"""
        self.db_engine = create_async_engine(settings.database_url, echo=False)

    async def close_db(self):
        """Close database connection"""
        if self.db_engine:
            await self.db_engine.dispose()

    async def check_api_connectivity(self) -> Dict[str, Any]:
        """Test API connectivity"""
        test = {
            "name": "API Connectivity",
            "status": "PASSED",
            "details": {},
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    "http://localhost:8003/health",
                    headers={"X-API-Key": API_KEY, "X-Tenant-ID": TENANT_ID}
                )
                test["details"]["status_code"] = response.status_code
                test["details"]["response"] = response.json()

                if response.status_code == 200:
                    test["status"] = "PASSED"
                else:
                    test["status"] = "FAILED"
        except Exception as e:
            test["status"] = "FAILED"
            test["details"]["error"] = str(e)

        return test

    async def check_database_connectivity(self) -> Dict[str, Any]:
        """Test database connectivity"""
        test = {
            "name": "Database Connectivity",
            "status": "PASSED",
            "details": {},
        }

        try:
            async with self.db_engine.connect() as conn:
                result = await conn.execute(text("SELECT 1"))
                row = result.fetchone()
                test["details"]["query_result"] = row[0] if row else None

                if row and row[0] == 1:
                    test["status"] = "PASSED"
                else:
                    test["status"] = "FAILED"
        except Exception as e:
            test["status"] = "FAILED"
            test["details"]["error"] = str(e)

        return test

    async def check_request_to_database_flow(self, applicant_data: Dict[str, Any]) -> Dict[str, Any]:
        """Test API request → Database storage flow"""
        test = {
            "name": "Request to Database Flow",
            "status": "PASSED",
            "details": {},
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Step 1: Create investigation via API
                response = await client.post(
                    "http://localhost:8003/api/v1/investigations",
                    json={
                        "query": "Data flow test investigation",
                        "date_from": "2026-01-01",
                        "date_to": "2026-12-31",
                        "applicant_data": applicant_data
                    },
                    headers={
                        "X-API-Key": API_KEY,
                        "X-Tenant-ID": TENANT_ID
                    }
                )

                if response.status_code != 202:
                    test["status"] = "FAILED"
                    test["details"]["error"] = f"API returned {response.status_code}: {response.text}"
                    return test

                inv_data = response.json()
                inv_id = inv_data["investigation_id"]
                test["details"]["investigation_id"] = inv_id

                # Step 2: Verify data in database
                await asyncio.sleep(1)

                async with self.db_engine.connect() as conn:
                    result = await conn.execute(
                        text("""
                            SELECT investigation_id, applicant_data, status
                            FROM investigations
                            WHERE investigation_id = :id AND tenant_id = :tenant
                        """),
                        {"id": inv_id, "tenant": TENANT_ID}
                    )
                    row = result.fetchone()

                    if not row:
                        test["status"] = "FAILED"
                        test["details"]["error"] = "Investigation not found in database"
                        return test

                    # Verify applicant_data stored correctly
                    stored_data = row.applicant_data
                    test["details"]["stored_applicant_data"] = stored_data
                    test["details"]["applicant_data_present"] = stored_data is not None

                    if stored_data is None:
                        test["status"] = "FAILED"
                        test["details"]["error"] = "applicant_data is NULL in database"
                        return test

                    # Verify key fields
                    for key in applicant_data.keys():
                        if key not in stored_data:
                            test["status"] = "FAILED"
                            test["details"]["missing_field"] = key
                            return test

                    # Compare values (allow for minor type conversions)
                    mismatches = []
                    for key, expected_value in applicant_data.items():
                        stored_value = stored_data.get(key)
                        if stored_value != expected_value:
                            # Allow string/int conversions
                            if not (str(stored_value) == str(expected_value)):
                                mismatches.append({
                                    "field": key,
                                    "expected": expected_value,
                                    "stored": stored_value,
                                })

                    if mismatches:
                        test["status"] = "WARNING"
                        test["details"]["field_mismatches"] = mismatches
                    else:
                        test["status"] = "PASSED"

        except Exception as e:
            test["status"] = "FAILED"
            test["details"]["error"] = str(e)
            import traceback
            test["details"]["traceback"] = traceback.format_exc()

        return test

    async def check_database_to_agent_flow(self, investigation_id: str) -> Dict[str, Any]:
        """Test Database → Agent execution flow"""
        test = {
            "name": "Database to Agent Flow",
            "status": "PASSED",
            "details": {},
        }

        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                # Execute investigation synchronously
                response = await client.post(
                    f"http://localhost:8003/api/v1/investigations/{investigation_id}/execute-sync",
                    json={},
                    headers={
                        "X-API-Key": API_KEY,
                        "X-Tenant-ID": TENANT_ID
                    },
                    timeout=300.0
                )

                if response.status_code != 200:
                    test["status"] = "FAILED"
                    test["details"]["error"] = f"Execute returned {response.status_code}"
                    return test

                result = response.json()
                test["details"]["status"] = result.get("status")
                test["details"]["case_count"] = result.get("case_count")
                test["details"]["verdict"] = result.get("compliance_verdict")
                test["details"]["risk"] = result.get("regulatory_risk")

                # Verify agents produced outputs
                if result.get("status") != "complete":
                    test["status"] = "FAILED"
                    test["details"]["error"] = f"Investigation status is {result.get('status')}, not complete"
                    return test

                if result.get("compliance_verdict") is None:
                    test["status"] = "FAILED"
                    test["details"]["error"] = "No compliance verdict from agents"
                    return test

                test["status"] = "PASSED"

        except Exception as e:
            test["status"] = "FAILED"
            test["details"]["error"] = str(e)

        return test

    async def check_agent_to_result_flow(self, investigation_id: str) -> Dict[str, Any]:
        """Test Agent output → Result API flow"""
        test = {
            "name": "Agent to Result API Flow",
            "status": "PASSED",
            "details": {},
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Fetch investigation result
                response = await client.get(
                    f"http://localhost:8003/api/v1/investigations/{investigation_id}",
                    headers={
                        "X-API-Key": API_KEY,
                        "X-Tenant-ID": TENANT_ID
                    }
                )

                if response.status_code != 200:
                    test["status"] = "FAILED"
                    test["details"]["error"] = f"API returned {response.status_code}"
                    return test

                result = response.json()
                test["details"]["investigation_id"] = result.get("investigation_id")
                test["details"]["status"] = result.get("status")
                test["details"]["compliance_verdict"] = result.get("compliance_verdict")
                test["details"]["regulatory_risk"] = result.get("regulatory_risk")
                test["details"]["bias_detected"] = result.get("bias_detected")
                test["details"]["report_generated"] = bool(result.get("final_report"))
                test["details"]["report_length"] = len(result.get("final_report", ""))

                # Verify all required fields
                required_fields = [
                    "investigation_id",
                    "status",
                    "compliance_verdict",
                    "regulatory_risk",
                ]

                missing_fields = []
                for field in required_fields:
                    if not result.get(field):
                        missing_fields.append(field)

                if missing_fields:
                    test["status"] = "FAILED"
                    test["details"]["missing_fields"] = missing_fields
                    return test

                # Verify report generation
                if not result.get("final_report"):
                    test["status"] = "FAILED"
                    test["details"]["error"] = "No final report generated"
                    return test

                test["status"] = "PASSED"

        except Exception as e:
            test["status"] = "FAILED"
            test["details"]["error"] = str(e)

        return test

    async def run_full_flow_validation(self, applicant_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run complete data flow validation"""
        flow_result = {
            "test_case": applicant_data.get("applicant_id", "unknown"),
            "timestamp": datetime.now().isoformat(),
            "flows": [],
        }

        # 1. API Connectivity
        print("  → Testing API connectivity...", end=" ", flush=True)
        api_test = await self.check_api_connectivity()
        flow_result["flows"].append(api_test)
        print("✅" if api_test["status"] == "PASSED" else "❌")

        # 2. Database Connectivity
        print("  → Testing database connectivity...", end=" ", flush=True)
        db_test = await self.check_database_connectivity()
        flow_result["flows"].append(db_test)
        print("✅" if db_test["status"] == "PASSED" else "❌")

        if db_test["status"] != "PASSED":
            return flow_result

        # 3. Request → Database
        print("  → Testing request to database flow...", end=" ", flush=True)
        request_db_test = await self.check_request_to_database_flow(applicant_data)
        flow_result["flows"].append(request_db_test)
        print("✅" if request_db_test["status"] in ["PASSED", "WARNING"] else "❌")

        if request_db_test["status"] == "FAILED":
            return flow_result

        inv_id = request_db_test["details"].get("investigation_id")

        # 4. Database → Agents
        print("  → Testing database to agent flow...", end=" ", flush=True)
        db_agent_test = await self.check_database_to_agent_flow(inv_id)
        flow_result["flows"].append(db_agent_test)
        print("✅" if db_agent_test["status"] == "PASSED" else "❌")

        # 5. Agents → Results
        print("  → Testing agent to result API flow...", end=" ", flush=True)
        agent_result_test = await self.check_agent_to_result_flow(inv_id)
        flow_result["flows"].append(agent_result_test)
        print("✅" if agent_result_test["status"] == "PASSED" else "❌")

        return flow_result

    async def run_all_validations(self):
        """Run all data flow validations"""
        print("\n" + "="*80)
        print("SENTINEL v2 — DATA FLOW VALIDATION")
        print("="*80 + "\n")

        await self.init_db()

        try:
            # Test with multiple applicant profiles
            test_cases = [
                {
                    "applicant_id": "FLOW_001",
                    "applicant_name": "Test User 1",
                    "race": "White",
                    "age": 45,
                    "income": 120000,
                    "credit_score": 750,
                    "denied": False,
                },
                {
                    "applicant_id": "FLOW_002",
                    "applicant_name": "Test User 2",
                    "race": "African American",
                    "age": 35,
                    "income": 50000,
                    "credit_score": 620,
                    "denied": True,
                    "denial_reason": "credit_score_too_low",
                },
            ]

            for test_case in test_cases:
                print(f"Testing data flow for {test_case['applicant_id']}...")
                result = await self.run_full_flow_validation(test_case)
                self.test_results.append(result)
                print()

            self.generate_report()

        finally:
            await self.close_db()

    def generate_report(self):
        """Generate data flow validation report"""
        report_lines = [
            "=" * 100,
            "SENTINEL v2 — DATA FLOW VALIDATION REPORT",
            "=" * 100,
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"Total Test Cases: {len(self.test_results)}",
            "",
        ]

        for test_case in self.test_results:
            passed_flows = sum(1 for f in test_case["flows"] if f["status"] == "PASSED")
            total_flows = len(test_case["flows"])

            report_lines.extend([
                f"Test Case: {test_case['test_case']}",
                f"Status: {passed_flows}/{total_flows} flows successful",
                "",
            ])

            for flow in test_case["flows"]:
                status_symbol = "✅" if flow["status"] == "PASSED" else "⚠️" if flow["status"] == "WARNING" else "❌"
                report_lines.append(f"  {status_symbol} {flow['name']}")

                if flow.get("details"):
                    for key, value in flow["details"].items():
                        if key != "traceback":
                            report_lines.append(f"      {key}: {value}")

                report_lines.append("")

        report_lines.append("=" * 100)

        report = "\n".join(report_lines)
        report_file = Path(__file__).parent.parent / "test_results" / f"dataflow_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        report_file.parent.mkdir(parents=True, exist_ok=True)
        report_file.write_text(report)

        print(report)
        print(f"\n📄 Data Flow Report saved to: {report_file}")


async def main():
    """Main data flow validation runner"""
    validator = DataFlowValidator()
    await validator.run_all_validations()


if __name__ == "__main__":
    asyncio.run(main())
