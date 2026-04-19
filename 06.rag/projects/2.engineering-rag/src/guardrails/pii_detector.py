"""
pii_detector.py — PII detection and redaction using Microsoft Presidio.

Runs fully locally (no external API). Uses spaCy en_core_web_sm NER model.

Install once:
    pip install presidio-analyzer presidio-anonymizer
    python -m spacy download en_core_web_sm

Usage:
    from src.guardrails.pii_detector import redact_pii, has_pii

    clean_text = redact_pii("Contact John Smith at john@example.com")
    # → "Contact <PERSON> at <EMAIL_ADDRESS>"

    if has_pii(query):
        logger.warning("PII in query")
"""

import logging
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)

# PII entity types to detect and redact.
# Deliberately conservative — we keep generic engineering terms like
# serial numbers, part codes. Only flag personal / sensitive identifiers.
_ENTITIES = [
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "CREDIT_CARD",
    "IBAN_CODE",
    "IP_ADDRESS",
    "MEDICAL_LICENSE",
    "URL",            # may appear in SDS documents; redact for LLM calls
    "US_SSN",
    "US_PASSPORT",
    "US_DRIVER_LICENSE",
    "NRP",            # Nationality, Religious or Political group
]


@lru_cache(maxsize=1)
def _get_engines():
    """Lazy-load Presidio engines (singleton). Cached after first call."""
    try:
        from presidio_analyzer import AnalyzerEngine
        from presidio_anonymizer import AnonymizerEngine

        analyzer   = AnalyzerEngine()
        anonymizer = AnonymizerEngine()
        logger.info("Presidio PII engines loaded (spaCy en_core_web_sm)")
        return analyzer, anonymizer
    except Exception as e:
        logger.warning("Presidio PII engines failed to load: %s — PII detection disabled", e)
        return None, None


def has_pii(text: str) -> bool:
    """
    Return True if Presidio detects any PII in the text.

    Fast check: stops after the first finding.
    """
    analyzer, _ = _get_engines()
    if analyzer is None or not text:
        return False
    try:
        results = analyzer.analyze(text=text, entities=_ENTITIES, language="en")
        return len(results) > 0
    except Exception as e:
        logger.debug("PII detection error: %s", e)
        return False


def detect_pii(text: str) -> list[dict]:
    """
    Return a list of detected PII entities.

    Each entry: {"entity_type": "PERSON", "start": 8, "end": 18, "score": 0.85}
    """
    analyzer, _ = _get_engines()
    if analyzer is None or not text:
        return []
    try:
        results = analyzer.analyze(text=text, entities=_ENTITIES, language="en")
        return [
            {"entity_type": r.entity_type, "start": r.start, "end": r.end, "score": r.score}
            for r in results
        ]
    except Exception as e:
        logger.debug("PII detection error: %s", e)
        return []


def redact_pii(text: str) -> str:
    """
    Redact PII in text, replacing each entity with a placeholder.

    Example:
        "John Smith works at ACME, call 555-1234"
        → "<PERSON> works at ACME, call <PHONE_NUMBER>"

    If Presidio is not available or text has no PII, returns the original text.
    """
    if not text:
        return text

    analyzer, anonymizer = _get_engines()
    if analyzer is None or anonymizer is None:
        return text

    try:
        results = analyzer.analyze(text=text, entities=_ENTITIES, language="en")
        if not results:
            return text

        from presidio_anonymizer.entities import OperatorConfig
        operators = {
            entity: OperatorConfig("replace", {"new_value": f"<{entity}>"})
            for entity in _ENTITIES
        }
        anonymized = anonymizer.anonymize(
            text=text,
            analyzer_results=results,
            operators=operators,
        )
        redacted = anonymized.text
        if redacted != text:
            logger.info("PII redacted: %d entities replaced", len(results))
        return redacted
    except Exception as e:
        logger.warning("PII redaction failed, returning original text: %s", e)
        return text
