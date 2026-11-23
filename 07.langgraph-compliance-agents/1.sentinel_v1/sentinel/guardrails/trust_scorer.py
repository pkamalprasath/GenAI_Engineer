"""
Context trust scoring — from Ranjan Kumar's audit trail pattern.

Each context source is assigned a trust score (0.0–1.0) before agents
process it. Low-trust sources are flagged but not blocked. Agents use
trust scores to weight evidence when building findings.

Scores are configured in configs/security.yaml under trust_scores.
"""
from __future__ import annotations

import logging
import re

from configs.settings import security_cfg

logger = logging.getLogger(__name__)

# Source type → trust score mapping from security.yaml
_TRUST_SCORES: dict[str, float] = security_cfg.get("trust_scores", {
    "regulation_document": 0.95,
    "tool_response": 0.80,
    "past_investigation": 0.75,
    "system_prompt": 0.90,
    "user_input": 0.40,
})

# Patterns that indicate possible prompt injection in user input
_INJECTION_PATTERNS = [
    r"ignore (previous|all|prior) (instructions?|prompts?)",
    r"you are now",
    r"pretend (to be|you are)",
    r"disregard your",
    r"new (system|instruction)",
    r"jailbreak",
]
_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)


def score_source(source_type: str, content: str) -> float:
    """
    Return trust score for a context source.
    For user_input, additionally penalize if injection patterns detected.
    """
    base_score = _TRUST_SCORES.get(source_type, 0.5)

    # Extra penalty for possible prompt injection in user-supplied content
    if source_type == "user_input" and _INJECTION_RE.search(content):
        penalized = max(0.1, base_score - 0.3)
        logger.warning(
            '{"event":"injection_pattern_detected","score_before":%.2f,"score_after":%.2f}',
            base_score, penalized,
        )
        return penalized

    return base_score


def score_context_sources(sources: list[dict]) -> list[dict]:
    """
    Add trust_score field to each source dict.
    Expects each source to have 'type' and 'content' keys.
    Returns new list — does not mutate input.
    """
    scored = []
    for src in sources:
        trust = score_source(src.get("type", "user_input"), src.get("content", ""))
        scored.append({**src, "trust_score": trust})
    return scored


def aggregate_trust(evidence_items: list[dict]) -> float:
    """
    Compute weighted average trust across a list of evidence items.
    Used by report_agent to set overall report_confidence.
    Returns 0.0 if no evidence provided.
    """
    if not evidence_items:
        return 0.0
    total = sum(item.get("trust_score", 0.5) for item in evidence_items)
    return round(total / len(evidence_items), 4)
