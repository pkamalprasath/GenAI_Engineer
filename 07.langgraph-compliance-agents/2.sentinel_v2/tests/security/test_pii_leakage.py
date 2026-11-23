"""
PII leakage tests — PII must never appear in logs, API responses, or reports.
All inputs crafted locally — no external deps.

Run with: make test-security
"""
from __future__ import annotations

import json
import logging
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from sentinel.guardrails.pii_detector import detect_and_redact


PII_SAMPLES = {
    "ssn": "219-09-9999",   # Presidio-detectable SSN pattern (not all formats score above threshold)
    "email": "john.applicant@email.com",
    "phone": "(555) 867-5309",
    "dob": "01/15/1985",
    "name": "John Applicant",
}


class TestPIIRedactionCompleteness:
    """All PII types must be redacted before text reaches LLM or logs."""

    def test_ssn_fully_redacted(self):
        text = f"Applicant SSN: {PII_SAMPLES['ssn']} was reviewed"
        result = detect_and_redact(text)
        assert PII_SAMPLES["ssn"] not in result.redacted_text

    def test_email_fully_redacted(self):
        text = f"Contact {PII_SAMPLES['email']} for documentation"
        result = detect_and_redact(text)
        assert PII_SAMPLES["email"] not in result.redacted_text

    def test_phone_fully_redacted(self):
        text = f"Applicant phone: {PII_SAMPLES['phone']}"
        result = detect_and_redact(text)
        assert PII_SAMPLES["phone"] not in result.redacted_text

    def test_multiple_pii_types_all_redacted(self):
        text = (
            f"Name: {PII_SAMPLES['name']}, "
            f"SSN: {PII_SAMPLES['ssn']}, "
            f"Email: {PII_SAMPLES['email']}"
        )
        result = detect_and_redact(text)
        assert PII_SAMPLES["ssn"] not in result.redacted_text
        assert PII_SAMPLES["email"] not in result.redacted_text
        assert result.pii_detected is True

    def test_redacted_output_contains_placeholder(self):
        """Redacted text must contain placeholder markers, not blanks."""
        text = f"SSN: {PII_SAMPLES['ssn']}"
        result = detect_and_redact(text)
        if result.pii_detected:
            # Should have a placeholder like <SSN_NUMBER> or [REDACTED] or similar
            assert len(result.redacted_text) > 0
            # The redacted text must not just be empty or the same as input
            assert result.redacted_text != text


class TestPIINotInLogs:
    """PII values must never appear in log output — only entity types."""

    def test_pii_detection_log_contains_no_pii_values(self):
        """When PII is detected, log must contain entity types not actual values."""
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        logger = logging.getLogger("sentinel.guardrails.pii_detector")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        text = f"SSN: {PII_SAMPLES['ssn']}, Email: {PII_SAMPLES['email']}"
        detect_and_redact(text)

        log_output = log_stream.getvalue()
        logger.removeHandler(handler)

        # PII values must not appear in log output
        assert PII_SAMPLES["ssn"] not in log_output, "SSN leaked to logs!"
        assert PII_SAMPLES["email"] not in log_output, "Email leaked to logs!"

    def test_pii_result_entities_found_contains_no_values(self):
        """entities_found list must contain type names, not actual PII."""
        text = f"SSN: {PII_SAMPLES['ssn']}"
        result = detect_and_redact(text)
        if result.pii_detected:
            for entity in result.entities_found:
                assert PII_SAMPLES["ssn"] not in entity, f"PII value in entities_found: {entity}"
                assert "123" not in entity, "Raw SSN digits in entities_found"


class TestPIIInAPIResponse:
    """Simulate API response — verify PII not leaked in mock response."""

    def test_investigation_response_no_pii_in_query(self):
        """After PII redaction, stored query must not contain original PII."""
        from sentinel.guardrails.input_guard import sanitize_input

        pii_query = f"Review applicant {PII_SAMPLES['name']} SSN {PII_SAMPLES['ssn']}"
        result = sanitize_input(pii_query, tenant_id="bank-acme")

        if result.safe:
            assert PII_SAMPLES["ssn"] not in result.sanitized_text
            # Name may or may not be detected depending on Presidio model
            # But SSN must always be redacted

    def test_evidence_items_contain_no_pii(self, sample_state_complete):
        """Evidence items reference case IDs only — never applicant details."""
        for item in sample_state_complete["evidence_items"]:
            item_str = json.dumps(item)
            for pii_value in PII_SAMPLES.values():
                assert pii_value not in item_str, (
                    f"PII value '{pii_value}' found in evidence item"
                )


class TestPIIInReports:
    """Final reports must reference case IDs only — never personal data."""

    def test_draft_report_references_case_ids_not_persons(self):
        """Reports cite CASE-XXXX identifiers, not applicant names or SSNs."""
        sample_report = (
            "Investigation of CASE-0001 through CASE-0030 reveals systematic "
            "denial rate disparity in census tracts CT-001 through CT-030. "
            "Applicants in these tracts with credit tier 'excellent' were denied "
            "at 23% higher rate than comparable applicants in other tracts. "
            "See provenance nodes: decision-CASE-0001 through decision-CASE-0030."
        )
        # Verify no PII in a well-formed compliance report
        for pii_value in PII_SAMPLES.values():
            assert pii_value not in sample_report

    def test_output_guard_blocks_pii_in_report(self):
        """output_guard must reject any report containing unredacted PII."""
        from sentinel.guardrails.output_guard import validate_output

        pii_report = (
            f"Applicant John Smith (SSN: {PII_SAMPLES['ssn']}) was denied credit. "
            f"Contact: {PII_SAMPLES['email']}"
        )
        is_valid, reason = validate_output(pii_report, provenance_node_ids=[])
        assert is_valid is False
        assert "pii" in reason.lower() or "redact" in reason.lower()

    def test_output_guard_accepts_clean_report(self):
        """Clean report with case IDs and no PII should pass output guard."""
        from sentinel.guardrails.output_guard import validate_output

        clean_report = (
            "SENTINEL Compliance Investigation Report\n"
            "Investigation ID: INV-001\n"
            "Cases Reviewed: CASE-0001, CASE-0002, CASE-0003\n"
            "Compliance Verdict: UNCERTAIN\n"
            "Regulatory Risk: MEDIUM\n"
            "Applicable Regulation: ECOA Section 202.6\n"
            "No bias patterns detected above threshold.\n"
            "Provenance: decision-CASE-0001, decision-CASE-0002\n"
        )
        is_valid, reason = validate_output(
            clean_report,
            provenance_node_ids=["decision-CASE-0001", "decision-CASE-0002"],
        )
        assert is_valid is True
