"""
SENTINEL v2 — Comprehensive Automated Testing Suite
Orchestrates all tests: compliance frameworks, data flow, UI validation
Generates executive summary and detailed reports
"""
import asyncio
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestOrchestrator:
    """Orchestrates all SENTINEL tests"""

    def __init__(self):
        self.test_dir = Path(__file__).parent
        self.results_dir = self.test_dir.parent / "test_results"
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.test_results = {}

    def run_test_module(self, module_name: str, module_path: str) -> Dict[str, Any]:
        """Run a single test module"""
        print(f"\n{'='*80}")
        print(f"Running: {module_name}")
        print(f"{'='*80}")

        try:
            result = subprocess.run(
                [sys.executable, str(self.test_dir / module_path)],
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout
            )

            return {
                "module": module_name,
                "status": "PASSED" if result.returncode == 0 else "FAILED",
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "timestamp": datetime.now().isoformat(),
            }

        except subprocess.TimeoutExpired:
            return {
                "module": module_name,
                "status": "TIMEOUT",
                "error": f"Test timed out after 600 seconds",
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {
                "module": module_name,
                "status": "ERROR",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    async def run_all_tests(self):
        """Run all test modules"""
        print("\n" + "="*80)
        print("SENTINEL v2 — COMPREHENSIVE AUTOMATED TESTING SUITE")
        print("="*80)
        print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Results Directory: {self.results_dir}")

        test_modules = [
            ("E2E Integration Tests (Multiple Compliance Frameworks)", "automated_e2e_tests.py"),
            ("Data Flow Validation Tests", "data_flow_validation.py"),
            ("UI Validation Tests", "ui_validation_tests.py"),
        ]

        # Run each test module
        for module_name, module_path in test_modules:
            if (self.test_dir / module_path).exists():
                result = self.run_test_module(module_name, module_path)
                self.test_results[module_name] = result

                # Print output
                if result.get("stdout"):
                    print(result["stdout"])
                if result.get("stderr"):
                    print("STDERR:", result["stderr"])
            else:
                print(f"⚠️  Test module not found: {module_path}")
                self.test_results[module_name] = {
                    "module": module_name,
                    "status": "SKIPPED",
                    "error": f"File not found: {module_path}",
                }

    def generate_executive_summary(self) -> str:
        """Generate executive summary"""
        summary_lines = [
            "",
            "=" * 100,
            "EXECUTIVE SUMMARY",
            "=" * 100,
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "",
        ]

        # Count results
        passed = sum(1 for r in self.test_results.values() if r.get("status") == "PASSED")
        failed = sum(1 for r in self.test_results.values() if r.get("status") == "FAILED")
        errors = sum(1 for r in self.test_results.values() if r.get("status") == "ERROR")
        skipped = sum(1 for r in self.test_results.values() if r.get("status") == "SKIPPED")

        total = len(self.test_results)
        pass_rate = f"{100*passed//total}%" if total > 0 else "0%"

        summary_lines.extend([
            f"OVERALL RESULTS:",
            f"  Total Tests: {total}",
            f"  Passed: {passed}",
            f"  Failed: {failed}",
            f"  Errors: {errors}",
            f"  Skipped: {skipped}",
            f"  Pass Rate: {pass_rate}",
            "",
            "SYSTEM READINESS:",
        ])

        # Detailed breakdown
        for module_name, result in self.test_results.items():
            status_symbol = {
                "PASSED": "✅",
                "FAILED": "❌",
                "ERROR": "⚠️",
                "TIMEOUT": "⏱️",
                "SKIPPED": "⊘",
            }.get(result.get("status"), "?")

            summary_lines.append(
                f"  {status_symbol} {module_name}: {result.get('status')}"
            )

        summary_lines.extend([
            "",
            "=" * 100,
            "",
        ])

        return "\n".join(summary_lines)

    def generate_detailed_report(self) -> str:
        """Generate detailed test report"""
        report_lines = [
            "=" * 100,
            "DETAILED TEST REPORT",
            "=" * 100,
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "",
        ]

        for module_name, result in self.test_results.items():
            report_lines.extend([
                "",
                f"MODULE: {module_name}",
                f"Status: {result.get('status')}",
                f"Timestamp: {result.get('timestamp', 'N/A')}",
                "",
            ])

            if result.get("stdout"):
                report_lines.append("OUTPUT:")
                report_lines.append(result["stdout"][:5000])  # Limit output
                report_lines.append("")

            if result.get("stderr"):
                report_lines.append("ERRORS:")
                report_lines.append(result["stderr"][:2000])
                report_lines.append("")

            if result.get("error"):
                report_lines.append(f"ERROR: {result['error']}")

            report_lines.append("-" * 100)

        report_lines.append("=" * 100)
        return "\n".join(report_lines)

    def save_reports(self):
        """Save all reports to files"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Executive summary
        summary = self.generate_executive_summary()
        summary_file = self.results_dir / f"EXECUTIVE_SUMMARY_{timestamp}.txt"
        summary_file.write_text(summary)
        print(summary)
        print(f"📄 Executive Summary saved: {summary_file}")

        # Detailed report
        detailed = self.generate_detailed_report()
        detailed_file = self.results_dir / f"DETAILED_REPORT_{timestamp}.txt"
        detailed_file.write_text(detailed)
        print(f"📄 Detailed Report saved: {detailed_file}")

        # JSON results
        json_file = self.results_dir / f"test_results_{timestamp}.json"
        json_file.write_text(json.dumps(self.test_results, indent=2))
        print(f"📊 JSON Results saved: {json_file}")

        print(f"\n✅ All reports saved to: {self.results_dir}")


async def main():
    """Main test orchestrator"""
    orchestrator = TestOrchestrator()
    await orchestrator.run_all_tests()
    orchestrator.save_reports()


if __name__ == "__main__":
    print("""
    ╔════════════════════════════════════════════════════════════════════════════╗
    ║                 SENTINEL v2 AUTOMATED TESTING SUITE                         ║
    ║                                                                            ║
    ║  This comprehensive test suite validates:                                  ║
    ║  ✓ Multiple compliance frameworks (Fair Lending, ADA, ECOA)               ║
    ║  ✓ End-to-end data flow (API → DB → Agents → Results)                    ║
    ║  ✓ UI/Dashboard appearance and functionality                              ║
    ║  ✓ Data validation and integrity                                          ║
    ║  ✓ Error handling and recovery                                            ║
    ║                                                                            ║
    ╚════════════════════════════════════════════════════════════════════════════╝
    """)

    asyncio.run(main())
