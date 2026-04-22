"""
Output guardrail — validates every agent output before it leaves the system.

Stage 1: Citation verification — every provenance_node_id must exist in DB
Stage 2: PII scan — block any output containing unredacted PII
Stage 3: Confidence threshold — below floor → force HITL flag
Stage 4: Content hash — SHA-256 stored for tamper detection

Called by report_agent and API layer before returning responses to callers.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

from configs.settings import agents_cfg
from sentinel.guardrails.pii_detector import scan_for_pii, scan_output_for_pii

logger = logging.getLogger(__name__)

# Confidence below which HITL is forced, regardless of agent decision
_AUTO_RESOLVE_THRESHOLD: float = (
    agents_cfg.get("agents", {})
    .get("report_generation", {})
    .get("auto_resolve_confidence", 0.85)
)


@dataclass
class OutputGuardResult:
    safe: bool
    content: str
    content_hash: str
    hitl_required: bool
    hitl_reason: str
    block_reason: str = ""


def validate_output(
    content: str,
    provenance_node_ids: list[str] | None = None,
) -> tuple[bool, str]:
    """
    Synchronous output guard — used by tests and API layer for quick PII + sanity checks.
    Returns (is_valid, reason). is_valid=False means the output must not be delivered.
    """
    if scan_output_for_pii(content):
        return False, "PII detected in output — redact before delivery"
    if not content.strip():
        return False, "Empty output rejected"
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    logger.info('{"event":"output_validated_sync","hash":"%s"}', content_hash[:16])
    return True, "output_valid"


async def validate_output_async(
    content: str,
    confidence: float,
    citations: list[str],
    provenance_store,   # sentinel.provenance.store.ProvenanceStore instance
) -> OutputGuardResult:
    """
    Run all output guard stages.
    Returns OutputGuardResult — safe=False means the output must not be delivered.
    """
    # ── Stage 1: Citation verification ────────────────────────────────────────
    invalid_citations = []
    for node_id in citations:
        exists = await provenance_store.node_exists(node_id)
        if not exists:
            # A cited node_id that doesn't exist = agent hallucinated a citation
            invalid_citations.append(node_id)

    if invalid_citations:
        logger.error(
            '{"event":"hallucinated_citations","count":%d,"ids":%s}',
            len(invalid_citations), invalid_citations[:3],
        )
        return OutputGuardResult(
            safe=False,
            content="",
            content_hash="",
            hitl_required=True,
            hitl_reason="Agent cited non-existent provenance nodes",
            block_reason="Hallucinated citations detected",
        )

    # ── Stage 2: PII scan on output ───────────────────────────────────────────
    if scan_output_for_pii(content):
        logger.error('{"event":"pii_in_output","action":"blocked"}')
        return OutputGuardResult(
            safe=False,
            content="",
            content_hash="",
            hitl_required=True,
            hitl_reason="Output contained unredacted PII",
            block_reason="PII detected in agent output",
        )

    # ── Stage 3: Confidence threshold ─────────────────────────────────────────
    hitl_required = confidence < _AUTO_RESOLVE_THRESHOLD
    hitl_reason = (
        f"Confidence {confidence:.2f} below threshold {_AUTO_RESOLVE_THRESHOLD}"
        if hitl_required else ""
    )

    # ── Stage 4: Content hash for tamper detection ────────────────────────────
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    logger.info(
        '{"event":"output_validated","confidence":%.3f,"hitl_required":%s,"hash":"%s"}',
        confidence, str(hitl_required).lower(), content_hash[:16],
    )

    return OutputGuardResult(
        safe=True,
        content=content,
        content_hash=content_hash,
        hitl_required=hitl_required,
        hitl_reason=hitl_reason,
    )
