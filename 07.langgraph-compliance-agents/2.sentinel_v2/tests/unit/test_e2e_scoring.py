"""
Unit tests for the end-to-end scenario harness scoring (tests/automated_e2e_tests.py).

No API, database or LLM is needed: score_case() and summarise() are pure functions.
The cases below reproduce the outcomes of an earlier run (FAIR_003, ADA_002), which
the old harness counted as passes even though verdict and risk were wrong.
"""
from __future__ import annotations

import pytest

from tests.automated_e2e_tests import (
    ComplianceTestData,
    format_markdown_table,
    format_report,
    score_case,
    summarise,
)

CASE = {
    "applicant_id": "ADA_002",
    "name": "Applicant with Disability - Denied Without Accommodation",
    "framework": "ADA Accessibility (FHA Disability)",
    "expected_verdict": "VIOLATION",
    "expected_risk": "HIGH",
}

REPORT = "Draft compliance report text."


def test_match_on_verdict_and_risk_passes():
    r = score_case(CASE, verdict="VIOLATION", risk_level="HIGH", report=REPORT)
    assert r["status"] == "PASSED"
    assert r["failure_reasons"] == []
    assert r["verdict_match"] and r["risk_match"]


def test_verdict_and_risk_mismatch_fails():
    # ADA_002 in the earlier run: COMPLIANT / LOW where VIOLATION / HIGH was expected
    r = score_case(CASE, verdict="COMPLIANT", risk_level="LOW", report=REPORT)
    assert r["status"] == "FAILED"
    assert len(r["failure_reasons"]) == 2


def test_verdict_mismatch_alone_fails():
    r = score_case(CASE, verdict="COMPLIANT", risk_level="HIGH", report=REPORT)
    assert r["status"] == "FAILED"
    assert r["risk_match"] is True
    assert r["verdict_match"] is False


def test_risk_mismatch_alone_fails():
    r = score_case(CASE, verdict="VIOLATION", risk_level="MEDIUM", report=REPORT)
    assert r["status"] == "FAILED"
    assert r["verdict_match"] is True
    assert r["risk_match"] is False


@pytest.mark.parametrize("report", [None, "", "   "])
def test_missing_report_fails_even_when_labels_match(report):
    r = score_case(CASE, verdict="VIOLATION", risk_level="HIGH", report=report)
    assert r["status"] == "FAILED"
    assert "no report generated" in r["failure_reasons"]


def test_missing_verdict_or_risk_fails():
    assert score_case(CASE, verdict=None, risk_level="HIGH", report=REPORT)["status"] == "FAILED"
    assert score_case(CASE, verdict="VIOLATION", risk_level=None, report=REPORT)["status"] == "FAILED"


def test_label_comparison_ignores_case_and_whitespace():
    r = score_case(CASE, verdict=" violation ", risk_level="high", report=REPORT)
    assert r["status"] == "PASSED"


def test_summary_counts_only_true_passes():
    results = [
        score_case(CASE, "VIOLATION", "HIGH", REPORT),   # pass
        score_case(CASE, "COMPLIANT", "LOW", REPORT),    # fail
        score_case(CASE, "VIOLATION", "LOW", REPORT),    # fail
        {"test_case_id": "X", "status": "ERROR", "error": "timeout"},
    ]
    assert summarise(results) == {"total": 4, "passed": 1, "failed": 2, "errors": 1}


def test_report_and_table_show_the_true_pass_rate():
    results = [
        score_case(CASE, "VIOLATION", "HIGH", REPORT),
        score_case(CASE, "COMPLIANT", "LOW", REPORT),
    ]
    text = format_report(results)
    assert "Passed: 1" in text and "Failed: 1" in text
    assert "Pass rate: 1/2" in text
    table = format_markdown_table(results)
    assert "| pass |" in table and "| failed |" in table
    assert "Pass rate: 1/2" in table


def test_every_scenario_has_expected_labels():
    cases = ComplianceTestData.get_all_test_cases()
    assert len(cases) == 7
    for c in cases:
        assert c["expected_verdict"] in {"COMPLIANT", "VIOLATION", "UNCERTAIN"}
        assert c["expected_risk"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
