"""
PII detection and redaction using Microsoft Presidio.

Detects personal data (names, SSN, account numbers, etc.) and replaces
with typed placeholders. PII content is never logged — only detection events.
Entity types and replacement tokens are configured in configs/security.yaml.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from configs.settings import security_cfg

logger = logging.getLogger(__name__)

# Module-level flag — can be patched in tests
PII_ENABLED: bool = security_cfg.get("pii", {}).get("enabled", True)

# Lazy imports — Presidio is only loaded if PII detection is enabled
_analyzer = None
_anonymizer = None


def _get_analyzer():
    """Lazy-load Presidio AnalyzerEngine to avoid import overhead when disabled."""
    global _analyzer
    if _analyzer is None:
        from presidio_analyzer import AnalyzerEngine
        _analyzer = AnalyzerEngine()
    return _analyzer


def _get_anonymizer():
    global _anonymizer
    if _anonymizer is None:
        from presidio_anonymizer import AnonymizerEngine
        _anonymizer = AnonymizerEngine()
    return _anonymizer


@dataclass
class PIIResult:
    redacted_text: str
    pii_detected: bool
    entity_types_found: list[str]  # Types found — NOT the actual values

    @property
    def entities_found(self) -> list[str]:
        """Alias for entity_types_found — used by tests and API layer."""
        return self.entity_types_found

    @property
    def entity_count(self) -> int:
        return len(self.entity_types_found)


def detect_and_redact(text: str, language: str = "en") -> PIIResult:
    """
    Run Presidio PII detection on input text.
    Returns redacted text with typed placeholders.
    PII values are never stored, logged, or returned.
    """
    pii_cfg = security_cfg.get("pii", {})
    enabled = pii_cfg.get("enabled", True)

    if not PII_ENABLED or not enabled:
        return PIIResult(redacted_text=text, pii_detected=False, entity_types_found=[])

    entities = pii_cfg.get("entities", [])
    replacements = pii_cfg.get("replacements", {})

    try:
        analyzer = _get_analyzer()
        anonymizer = _get_anonymizer()

        results = analyzer.analyze(text=text, entities=entities, language=language)

        if not results:
            return PIIResult(redacted_text=text, pii_detected=False, entity_types_found=[])

        # Build anonymizer operators from config replacements
        from presidio_anonymizer.entities import OperatorConfig
        operators = {
            entity: OperatorConfig("replace", {"new_value": replacements.get(entity, f"<{entity}>")})
            for entity in {r.entity_type for r in results}
        }

        anonymized = anonymizer.anonymize(text=text, analyzer_results=results, operators=operators)
        entity_types = list({r.entity_type for r in results})

        # Log only that PII was found — never log what it was
        logger.info(
            '{"event":"pii_detected","entity_count":%d,"types":%s}',
            len(results),
            entity_types,
        )

        return PIIResult(
            redacted_text=anonymized.text,
            pii_detected=True,
            entity_types_found=entity_types,
        )

    except Exception as exc:
        # PII detection failure is non-fatal — pass through but flag it
        logger.error('{"event":"pii_detection_error","error":"%s"}', str(exc))
        return PIIResult(redacted_text=text, pii_detected=False, entity_types_found=[])


def scan_for_pii(text: str) -> bool:
    """Quick check — returns True if PII detected. Used for input scanning."""
    result = detect_and_redact(text)
    return result.pii_detected


def scan_output_for_pii(text: str, language: str = "en") -> bool:
    """Output-specific PII scan using narrower entity list (no PERSON/LOCATION/DATE_TIME).
    Compliance reports legitimately contain names of regulations, locations, and dates.
    Only blocks genuinely sensitive identifiers: SSN, email, phone, account, card numbers.
    """
    pii_cfg = security_cfg.get("pii", {})
    if not PII_ENABLED or not pii_cfg.get("enabled", True):
        return False

    output_entities = pii_cfg.get("output_entities", [
        "EMAIL_ADDRESS", "PHONE_NUMBER", "US_SSN", "US_BANK_NUMBER", "CREDIT_CARD",
    ])
    if not output_entities:
        return False

    try:
        analyzer = _get_analyzer()
        results = analyzer.analyze(text=text, entities=output_entities, language=language)
        return bool(results)
    except Exception as exc:
        logger.error('{"event":"output_pii_scan_error","error":"%s"}', str(exc))
        return False
