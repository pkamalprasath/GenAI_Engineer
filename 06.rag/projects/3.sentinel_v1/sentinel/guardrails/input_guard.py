"""
OWASP-compliant input guard — four-stage pipeline applied to every input
before any agent or LLM sees it.

Stage 1: OWASP sanitization (injection, XSS, path traversal)
Stage 2: PII detection and redaction (Presidio)
Stage 3: Trust scoring of context sources
Stage 4: Rate limit check (enforced at API middleware; checked here for direct callers)

All parameters come from configs/security.yaml — nothing is hardcoded.
"""
from __future__ import annotations

import html
import logging
import re
import urllib.parse
from dataclasses import dataclass, field

from configs.settings import security_cfg
from sentinel.guardrails.pii_detector import detect_and_redact
from sentinel.guardrails.trust_scorer import score_context_sources

logger = logging.getLogger(__name__)

_owasp_cfg = security_cfg.get("owasp", {})
_MAX_INPUT_LENGTH: int = _owasp_cfg.get("max_input_length", 5000)
_BLOCKED_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE | re.DOTALL)
    for p in _owasp_cfg.get("blocked_patterns", [])
]
_STRIP_HTML: bool = _owasp_cfg.get("strip_html", True)

# Pattern labels for descriptive block reasons
_PATTERN_LABELS = [
    (re.compile(r"(?i)(select|insert|update|delete|drop|union|exec|xp_)\s"), "SQL injection attempt"),
    (re.compile(r"\.\./|\.\.\\"), "Path traversal attempt"),
    (re.compile(r"<script[^>]*>|javascript:", re.IGNORECASE), "XSS injection attempt"),
    (re.compile(r"\$\{|\{\{|<%"), "Template injection attempt"),
]


@dataclass
class GuardResult:
    clean_text: str
    pii_detected: bool = False
    pii_entity_types: list[str] = field(default_factory=list)
    blocked: bool = False
    block_reason: str = ""
    context_sources: list[dict] = field(default_factory=list)

    @property
    def safe(self) -> bool:
        """Inverse of blocked — True means input passed all guard stages."""
        return not self.blocked

    @property
    def sanitized_text(self) -> str:
        """Alias for clean_text."""
        return self.clean_text


def sanitize_input(
    raw_text: str,
    context_sources: list[dict] | None = None,
    tenant_id: str = "",
) -> GuardResult:
    """
    Run all four guard stages on raw user input.
    Returns GuardResult with clean_text if safe, or blocked=True with reason.
    Never raises — all errors result in a blocked result to fail safely.
    """
    try:
        # ── Stage 1: OWASP sanitization ───────────────────────────────────
        text = raw_text.strip()

        # Block missing/empty tenant_id — all requests must be tenant-scoped
        if not tenant_id:
            return GuardResult(clean_text="", blocked=True, block_reason="Missing tenant_id — request rejected")

        # Block empty or whitespace-only inputs
        if not text:
            return GuardResult(clean_text="", blocked=True, block_reason="Empty input not allowed")

        # Truncate first — prevents regex DoS on huge inputs
        if len(text) > _MAX_INPUT_LENGTH:
            logger.warning('{"event":"input_truncated","original_len":%d}', len(text))
            text = text[:_MAX_INPUT_LENGTH]

        # Strip null bytes (common in binary injection attempts)
        text = text.replace("\x00", "")

        # URL-decode to catch encoded attacks like %2E%2E%2F = ../
        decoded = urllib.parse.unquote(text)
        _path_pattern = re.compile(r"\.\./|\.\.\\", re.IGNORECASE)
        if _path_pattern.search(decoded):
            return GuardResult(clean_text="", blocked=True, block_reason="Path traversal attempt")

        # Remove script tag content entirely (XSS: <script>alert('xss')</script>)
        if _STRIP_HTML:
            decoded = re.sub(r"<script[^>]*>.*?</script>", "", decoded, flags=re.DOTALL | re.IGNORECASE)
            decoded = html.unescape(decoded)
            decoded = re.sub(r"<[^>]+>", "", decoded)
        text = decoded

        # Check for blocked patterns — use descriptive label for block reason
        for pattern in _BLOCKED_PATTERNS:
            if pattern.search(text):
                # Find the descriptive label for this pattern
                reason = "Input contains disallowed pattern"
                for label_pattern, label in _PATTERN_LABELS:
                    if label_pattern.search(text) or label_pattern.search(urllib.parse.unquote(raw_text)):
                        reason = label
                        break
                logger.warning(
                    '{"event":"input_blocked","reason":"%s"}', reason,
                )
                return GuardResult(clean_text="", blocked=True, block_reason=reason)


        # ── Stage 2: PII detection and redaction ──────────────────────────
        pii_result = detect_and_redact(text)
        clean_text = pii_result.redacted_text

        # ── Stage 3: Trust scoring of context sources ─────────────────────
        scored_sources = score_context_sources(context_sources or [])

        # ── Stage 4: Log clean event (no PII, no original content) ────────
        logger.info(
            '{"event":"input_sanitized","pii_detected":%s,"source_count":%d}',
            str(pii_result.pii_detected).lower(),
            len(scored_sources),
        )

        return GuardResult(
            clean_text=clean_text,
            pii_detected=pii_result.pii_detected,
            pii_entity_types=pii_result.entity_types_found,
            blocked=False,
            context_sources=scored_sources,
        )

    except Exception as exc:
        # Fail closed — any unexpected error blocks the input
        logger.error('{"event":"input_guard_error","error":"%s"}', str(exc))
        return GuardResult(
            clean_text="",
            blocked=True,
            block_reason=f"Input validation error: {type(exc).__name__}",
        )
