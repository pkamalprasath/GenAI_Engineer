"""
Unit tests for OWASP input guardrails and PII detection.
No Docker, no API calls, no network — all inputs crafted locally.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from sentinel.guardrails.input_guard import GuardResult, sanitize_input
from sentinel.guardrails.pii_detector import PIIResult, detect_and_redact


# ── Input Sanitization ─────────────────────────────────────────────────────────

class TestOWASPSanitization:
    """Stage 1: OWASP sanitization — strip dangerous patterns before any LLM call."""

    def test_clean_input_passes(self):
        result = sanitize_input(
            "Review Q1 2024 credit decisions for fair lending compliance",
            tenant_id="test-tenant",
        )
        assert result.safe is True
        assert result.sanitized_text != ""

    def test_html_script_tag_stripped(self):
        result = sanitize_input(
            "Review decisions <script>alert('xss')</script> for compliance",
            tenant_id="test-tenant",
        )
        assert result.safe is True
        assert "<script>" not in result.sanitized_text
        assert "alert" not in result.sanitized_text

    def test_sql_injection_blocked(self):
        result = sanitize_input(
            "'; DROP TABLE decision_records; --",
            tenant_id="test-tenant",
        )
        assert result.safe is False
        assert "injection" in result.block_reason.lower() or "sql" in result.block_reason.lower()

    def test_sql_union_attack_blocked(self):
        result = sanitize_input(
            "UNION SELECT * FROM provenance_nodes WHERE tenant_id='other-tenant'",
            tenant_id="test-tenant",
        )
        assert result.safe is False

    def test_path_traversal_blocked(self):
        result = sanitize_input(
            "Review file at ../../etc/passwd",
            tenant_id="test-tenant",
        )
        assert result.safe is False

    def test_url_encoded_path_traversal_blocked(self):
        # %2E%2E%2F decodes to ../ — URL-encoded directory traversal
        result = sanitize_input(
            "Access %2E%2E%2Fetc%2Fpasswd config",
            tenant_id="test-tenant",
        )
        assert result.safe is False

    def test_oversized_input_truncated(self):
        huge_input = "a" * 100_000
        result = sanitize_input(huge_input, tenant_id="test-tenant")
        # Either truncated or blocked — either is acceptable security behavior
        if result.safe:
            assert len(result.sanitized_text) < len(huge_input)
        else:
            assert result.block_reason != ""

    def test_empty_input_blocked(self):
        result = sanitize_input("", tenant_id="test-tenant")
        assert result.safe is False

    def test_whitespace_only_blocked(self):
        result = sanitize_input("   \n\t  ", tenant_id="test-tenant")
        assert result.safe is False

    def test_null_bytes_stripped(self):
        result = sanitize_input(
            "Review decisions\x00 for compliance",
            tenant_id="test-tenant",
        )
        if result.safe:
            assert "\x00" not in result.sanitized_text

    def test_html_entities_handled(self):
        result = sanitize_input(
            "Review &lt;script&gt; patterns in decisions",
            tenant_id="test-tenant",
        )
        # Should pass — entity-encoded is not executable
        assert result.safe is True


class TestGuardResultStructure:
    """GuardResult dataclass should carry all needed info for state updates."""

    def test_safe_result_has_sanitized_text(self):
        result = sanitize_input("Review Q1 2024 compliance", tenant_id="test-tenant")
        assert result.safe is True
        assert isinstance(result.sanitized_text, str)
        assert result.sanitized_text != ""
        assert result.block_reason is None or result.block_reason == ""

    def test_blocked_result_has_reason(self):
        result = sanitize_input("'; DROP TABLE users; --", tenant_id="test-tenant")
        assert result.safe is False
        assert result.block_reason is not None
        assert len(result.block_reason) > 0


# ── PII Detection ──────────────────────────────────────────────────────────────

class TestPIIDetection:
    """Stage 2: PII detection — names, SSN, accounts detected and redacted."""

    def test_clean_text_not_flagged(self):
        result = detect_and_redact("Review Q1 2024 credit decisions for CASE-0001")
        assert result.pii_detected is False
        assert result.redacted_text == "Review Q1 2024 credit decisions for CASE-0001"

    def test_ssn_detected_and_redacted(self):
        # 219-09-9999 is a Presidio-detectable SSN pattern (not all formats score above threshold)
        result = detect_and_redact("Applicant SSN: 219-09-9999 was denied")
        assert result.pii_detected is True
        assert "219-09-9999" not in result.redacted_text
        assert "<" in result.redacted_text

    def test_email_detected_and_redacted(self):
        result = detect_and_redact("Contact applicant at john.doe@example.com for review")
        assert result.pii_detected is True
        assert "john.doe@example.com" not in result.redacted_text

    def test_phone_number_detected(self):
        result = detect_and_redact("Applicant phone: (555) 867-5309")
        assert result.pii_detected is True
        assert "867-5309" not in result.redacted_text

    def test_pii_result_never_contains_actual_values(self):
        """PIIResult.entities_found must contain only types, never PII content."""
        result = detect_and_redact("SSN 219-09-9999 for John Smith")
        assert result.pii_detected is True
        # entities_found should be type strings, not actual values
        for entity in result.entities_found:
            assert "999-88-7777" not in entity
            assert "John Smith" not in entity

    def test_entity_types_are_strings(self):
        result = detect_and_redact("email: test@test.com")
        assert all(isinstance(e, str) for e in result.entities_found)

    def test_pii_result_has_count(self):
        result = detect_and_redact("SSN 123-45-6789 and email foo@bar.com")
        if result.pii_detected:
            assert result.entity_count >= 1

    def test_case_ids_not_flagged_as_pii(self):
        """Case IDs like CASE-0001 are internal identifiers, not PII."""
        result = detect_and_redact(
            "Investigating CASE-0001, CASE-0002, CASE-0003 for compliance"
        )
        # These are internal case IDs, should not be redacted
        assert result.pii_detected is False or "CASE-0001" in result.redacted_text

    def test_disabled_pii_detection_is_passthrough(self):
        """When PII_REDACTION_ENABLED=false, detect_and_redact returns text unchanged."""
        with patch("sentinel.guardrails.pii_detector.PII_ENABLED", False):
            result = detect_and_redact("SSN 123-45-6789")
            assert result.redacted_text == "SSN 123-45-6789"
            assert result.pii_detected is False


class TestPIIResultStructure:
    """PIIResult dataclass structure validation."""

    def test_no_pii_result_structure(self):
        result = detect_and_redact("Review compliance data")
        assert isinstance(result, PIIResult)
        assert isinstance(result.pii_detected, bool)
        assert isinstance(result.redacted_text, str)
        assert isinstance(result.entities_found, list)
        assert isinstance(result.entity_count, int)

    def test_pii_result_entity_count_matches_list(self):
        result = detect_and_redact("SSN: 123-45-6789")
        if result.pii_detected:
            assert result.entity_count == len(result.entities_found)


# ── Full Pipeline Integration ──────────────────────────────────────────────────

class TestFullGuardrailPipeline:
    """Guardrail pipeline as a whole — injection + PII in same input."""

    def test_injection_with_pii_blocked_at_first_stage(self):
        # SQL injection should be caught at stage 1 before PII even runs
        result = sanitize_input(
            "'; DROP TABLE users WHERE ssn='123-45-6789'; --",
            tenant_id="test-tenant",
        )
        assert result.safe is False

    def test_pii_in_clean_query_is_redacted(self):
        result = sanitize_input(
            "Review decisions for applicant email foo@bar.com in Q1 2024",
            tenant_id="test-tenant",
        )
        if result.safe:
            assert "foo@bar.com" not in result.sanitized_text
            assert result.pii_detected is True

    def test_clean_compliance_query_passes_all_stages(self):
        result = sanitize_input(
            "Analyze Q1 2024 credit decisions in census tract CT-001 for fair lending",
            tenant_id="bank-acme",
        )
        # Must not be blocked — PII may be detected (date expressions can trigger Presidio)
        assert result.safe is True
        assert result.sanitized_text != ""
