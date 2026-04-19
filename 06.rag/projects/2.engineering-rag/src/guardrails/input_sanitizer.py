"""
input_sanitizer.py — Prompt injection and input validation guardrail.

Strips control characters and known injection patterns from user input
before it reaches the LLM. Does NOT alter meaning — only removes characters
that have no place in a well-formed natural language engineering question.
"""

import logging
import re

logger = logging.getLogger(__name__)

# Max characters accepted from user input
MAX_INPUT_LENGTH = 2000

# Patterns that look like prompt injection attempts
_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"forget\s+(everything|all)",
    r"you\s+are\s+now",
    r"act\s+as\s+",
    r"<\s*system\s*>",
    r"\[INST\]",
    r"###\s*(system|instruction|prompt)",
    r"<\|im_start\|>",
    r"<\|endoftext\|>",
]
_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)

# Control characters: keep printable ASCII + common Unicode; strip everything else
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize(text: str) -> str:
    """
    Sanitize user input for safe LLM use.

    Steps:
      1. Truncate to MAX_INPUT_LENGTH characters
      2. Strip ASCII control characters (keep newline \\n, tab \\t)
      3. Log a warning if injection patterns are detected (don't block — log and continue)

    Returns the sanitized string.
    """
    if not isinstance(text, str):
        return ""

    # 1. Truncate
    if len(text) > MAX_INPUT_LENGTH:
        logger.warning("Input truncated from %d to %d chars", len(text), MAX_INPUT_LENGTH)
        text = text[:MAX_INPUT_LENGTH]

    # 2. Strip control characters
    text = _CONTROL_CHARS_RE.sub("", text)

    # 3. Log injection patterns (warn only — do not block; engineers may legitimately
    #    ask about instruction sets, system prompts in documentation, etc.)
    if _INJECTION_RE.search(text):
        logger.warning("Possible prompt injection pattern detected in input: %.80r", text)

    return text.strip()
