"""
Bias Detection Agent — statistical analysis of AI decision patterns.

Hybrid pipeline (configured via configs/agents.yaml anomaly_backend):
  "statistical"      → disparity thresholds only (original behavior)
  "isolation_forest" → IsolationForest on full feature matrix only
  "hybrid"           → statistical thresholds first; IsolationForest catches
                        what disparity misses; Haiku only for edge cases

Business contract: output keys (bias_detected, bias_confidence,
statistical_findings, bias_dimensions_checked) are identical regardless
of which backend is active. Downstream agents don't know which was used.

Runs in PARALLEL with legal_agent after discovery (LangGraph fan-out).
Soul file: souls/bias_detection_agent.md
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from configs.settings import agents_cfg, get_domain_config, models_cfg, settings
from sentinel.llm.client import chat as llm_chat, get_tier_for_agent
from sentinel.agents.classifiers.anomaly_detector import AnomalyResult, detect_anomalies
from sentinel.observability import cost_tracker, heartbeat, langfuse_tracer
from sentinel.observability.logger import log_agent_event, log_error
from sentinel.state.investigation_state import InvestigationState

logger = logging.getLogger(__name__)

_SOUL = open("souls/bias_detection_agent.md").read()
_agent_cfg = agents_cfg.get("agents", {}).get("bias_detection", {})
_model_cfg = models_cfg.get("models", {}).get("reasoning", {})

_MIN_SAMPLE = _agent_cfg.get("minimum_sample_size", 30)
_DISPARITY_THRESHOLD = _agent_cfg.get("disparity_alert_threshold", 0.15)
_ANOMALY_BACKEND = _agent_cfg.get("anomaly_backend", "hybrid")
_IF_CONTAMINATION = _agent_cfg.get("isolation_forest_contamination", 0.05)
_IF_N_ESTIMATORS = _agent_cfg.get("isolation_forest_n_estimators", 100)
_IF_RANDOM_STATE = _agent_cfg.get("isolation_forest_random_state", 42)
_LLM_INTERPRETATION = _agent_cfg.get("llm_interpretation", "edge_cases")


async def _load_outcomes(
    session: AsyncSession, case_ids: list[str], tenant_id: str, domain_cfg: dict,
) -> list[dict]:
    """Load outcome records for the relevant cases, tenant-scoped."""
    outcome_field = domain_cfg.get("decision_schema", {}).get("outcome_field", "outcome")
    result = await session.execute(
        text(f"""
            SELECT case_id, {outcome_field} as outcome, metadata
            FROM decision_records
            WHERE tenant_id = :tenant_id
              AND case_id = ANY(:case_ids)
        """),  # noqa: S608 — outcome_field validated against domain config whitelist
        {"tenant_id": tenant_id, "case_ids": case_ids},
    )
    return [dict(row._mapping) for row in result.fetchall()]


def _compute_disparity(
    outcomes: list[dict], dimension: str, positive_outcomes: list[str],
) -> dict | None:
    """
    Compute approval rate disparity across groups for one dimension.
    Returns None if sample size below minimum or fewer than 2 groups.
    """
    groups: dict[str, list[str]] = defaultdict(list)
    for record in outcomes:
        meta = record.get("metadata", {})
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except (json.JSONDecodeError, TypeError):
                meta = {}
        group_value = str(meta.get(dimension, "unknown"))
        groups[group_value].append(record["outcome"])

    if len(groups) < 2:
        return None

    group_rates = {}
    for group, group_outcomes in groups.items():
        if len(group_outcomes) < _MIN_SAMPLE:
            continue
        positive_count = sum(1 for o in group_outcomes if o in positive_outcomes)
        group_rates[group] = positive_count / len(group_outcomes)

    if len(group_rates) < 2:
        return None

    max_rate = max(group_rates.values())
    min_rate = min(group_rates.values())
    disparity = round(max_rate - min_rate, 4)
    sample_total = sum(len(groups[g]) for g in group_rates)

    return {
        "dimension": dimension,
        "group_rates": group_rates,
        "disparity": disparity,
        "sample_size": sample_total,
        "flagged": disparity > _DISPARITY_THRESHOLD,
    }


def _rule_based_verdict(
    findings: list[dict], anomaly_result: AnomalyResult | None
) -> tuple[bool, float, str]:
    """
    Determine bias verdict using deterministic rules — no LLM required
    for clear-cut cases.

    Returns (bias_detected, confidence, interpretation_text).
    """
    flagged_findings = [f for f in findings if f.get("flagged")]
    has_statistical_bias = len(flagged_findings) > 0

    has_anomalies = (
        anomaly_result is not None and anomaly_result.anomaly_count > 0
    )

    if has_statistical_bias and has_anomalies:
        # Both methods agree — high confidence
        bias_detected = True
        confidence = 0.92
        interpretation = (
            f"Statistical disparity flagged in {len(flagged_findings)} dimension(s) "
            f"AND Isolation Forest detected {anomaly_result.anomaly_count} anomalous "
            f"decisions. Both methods agree: systematic bias pattern present."
        )
    elif has_statistical_bias and not has_anomalies:
        # Disparity present but population-level anomaly detector doesn't agree
        bias_detected = True
        confidence = 0.75
        interpretation = (
            f"Statistical disparity flagged in {len(flagged_findings)} dimension(s) "
            f"(threshold: {_DISPARITY_THRESHOLD}). Population-level anomaly detection "
            f"did not flag additional cases. Disparity may reflect legitimate risk factors."
        )
    elif not has_statistical_bias and has_anomalies:
        # Anomalies present but no dimension-level disparity — subtle pattern
        bias_detected = True
        confidence = 0.65  # Lower confidence — anomaly without disparity is borderline
        interpretation = (
            f"No dimension-level disparity above threshold ({_DISPARITY_THRESHOLD}), "
            f"but Isolation Forest flagged {anomaly_result.anomaly_count} anomalous "
            f"decisions. Pattern may be multi-dimensional — recommend human review."
        )
    else:
        bias_detected = False
        confidence = 0.88
        interpretation = (
            f"No statistical disparity above threshold ({_DISPARITY_THRESHOLD}) "
            f"and no population-level anomalies detected. "
            f"Dimensions checked: {[f['dimension'] for f in findings]}."
        )

    return bias_detected, confidence, interpretation


async def _llm_interpret(
    findings: list[dict],
    anomaly_result: AnomalyResult | None,
    disparity_threshold: float,
) -> tuple[bool, float]:
    """
    Call Haiku to interpret edge cases where rule-based verdict is uncertain.
    Only called when llm_interpretation != "never" and case is genuinely ambiguous.
    """
    anomaly_summary = (
        anomaly_result.explanation if anomaly_result else "Anomaly detection not run."
    )
    prompt = f"""{_SOUL}

Statistical disparity findings:
{json.dumps(findings, indent=2)}

Isolation Forest anomaly detection:
{anomaly_summary}

Disparity threshold: {disparity_threshold}

You are interpreting statistical findings only. Do NOT make legal conclusions.
Respond ONLY with JSON:
{{
  "bias_detected": true/false,
  "bias_confidence": 0.0-1.0,
  "interpretation": "One paragraph — statistical pattern description only"
}}"""

    tier = get_tier_for_agent("bias_detection_agent")
    response = await llm_chat(prompt, tier=tier)
    raw = response.text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1].lstrip("json").strip()
    result = json.loads(raw)
    return (
        bool(result.get("bias_detected", False)),
        float(result.get("bias_confidence", 0.5)),
        response,
    )


async def run(state: InvestigationState, session: AsyncSession) -> dict:
    """
    Bias detection agent node — called by LangGraph.
    Returns partial state update dict (same keys regardless of anomaly_backend).
    """
    from sentinel.core.debug import (
        log_agent_input, log_agent_output, log_agent_exception,
        generate_mock_bias_output
    )

    inv_id = state["investigation_id"]
    tenant_id = state["tenant_id"]
    hb_start = heartbeat.emit("bias_detection_agent", "running", state["iteration_count"])

    with langfuse_tracer.trace_agent_node("bias_detection_agent", inv_id, tenant_id):
        try:
            log_agent_input(
                "bias_detection_agent", inv_id,
                ["relevant_case_ids", "applicant_data", "compliance_verdict"],
                state
            )

            domain_cfg = get_domain_config()
            bias_cfg = domain_cfg.get("bias_config", {})
            dimensions = bias_cfg.get("dimensions", [])
            outcome_schema = domain_cfg.get("decision_schema", {})
            positive_outcomes = [outcome_schema.get("outcome_values", ["approved"])[0]]

            if not dimensions or not state["relevant_case_ids"]:
                logger.info(
                    f"[BIAS] No dimensions or case IDs. Checking applicant_data...",
                    extra={
                        "has_dimensions": bool(dimensions),
                        "has_case_ids": bool(state["relevant_case_ids"]),
                        "has_applicant_data": bool(state.get("applicant_data"))
                    }
                )


                return {
                    **hb_start,
                    "status": "analyzing",
                    "bias_dimensions_checked": [],
                    "statistical_findings": [],
                    "bias_detected": False,
                    "bias_confidence": 0.0,
                    "messages": [{"agent": "bias_detection_agent", "event": "skipped_no_data"}],
                }

            outcomes = await _load_outcomes(
                session, state["relevant_case_ids"], tenant_id, domain_cfg,
            )

            # Stage 1: Statistical disparity per dimension (always runs)
            findings = []
            for dimension in dimensions:
                finding = _compute_disparity(outcomes, dimension, positive_outcomes)
                if finding:
                    findings.append(finding)

            # Stage 2: Isolation Forest (if enabled)
            anomaly_result: AnomalyResult | None = None
            if _ANOMALY_BACKEND in ("isolation_forest", "hybrid"):
                anomaly_result = detect_anomalies(
                    outcomes=outcomes,
                    dimensions=dimensions,
                    positive_outcome_values=positive_outcomes,
                    contamination=_IF_CONTAMINATION,
                    n_estimators=_IF_N_ESTIMATORS,
                    random_state=_IF_RANDOM_STATE,
                )

            # Stage 3: Determine verdict
            llm_usage = None
            bias_detected, confidence, interpretation = _rule_based_verdict(
                findings, anomaly_result
            )

            # Only call LLM when genuinely ambiguous and interpretation mode allows it
            is_ambiguous = 0.60 <= confidence <= 0.78  # Borderline confidence range
            should_call_llm = (
                _LLM_INTERPRETATION == "always"
                or (_LLM_INTERPRETATION == "edge_cases" and is_ambiguous)
            )

            if should_call_llm:
                bias_detected, confidence, llm_usage = await _llm_interpret(
                    findings, anomaly_result, _DISPARITY_THRESHOLD
                )
                logger.info(
                    "Bias detection: LLM interpretation invoked (ambiguous case, confidence=%.2f)",
                    confidence,
                )
            else:
                logger.info(
                    "Bias detection: rule-based verdict used (confidence=%.2f, llm_skipped=True)",
                    confidence,
                )

            # Add anomaly finding to statistical_findings list if anomalies found
            if anomaly_result and anomaly_result.anomaly_count > 0:
                findings.append({
                    "dimension": "_isolation_forest",
                    "anomalous_case_ids": anomaly_result.anomalous_case_ids[:10],  # Top 10 for state
                    "anomaly_count": anomaly_result.anomaly_count,
                    "total_cases": anomaly_result.total_cases,
                    "disparity": None,
                    "flagged": True,
                    "explanation": anomaly_result.explanation,
                })

            log_agent_event(
                logger, inv_id, tenant_id, "bias_detection_agent", "bias_analysis_complete",
                details={
                    "backend": _ANOMALY_BACKEND,
                    "bias_detected": bias_detected,
                    "flagged_dimensions": sum(1 for f in findings if f.get("flagged")),
                    "anomaly_count": anomaly_result.anomaly_count if anomaly_result else 0,
                    "llm_called": llm_usage is not None,
                },
            )

            hb_end = heartbeat.emit("bias_detection_agent", "complete", state["iteration_count"])
            cost_update = cost_tracker.record_cost(
                "bias_detection_agent", llm_usage.model if llm_usage else _model_cfg.get("model"), llm_usage.provider if llm_usage else "none",
                llm_usage.input_tokens if llm_usage else 0, llm_usage.output_tokens if llm_usage else 0,
                state_total=state["total_cost_usd"],
            )

            output = {
                **hb_end,
                **cost_update,
                "status": "analyzing",
                "bias_dimensions_checked": dimensions,
                "statistical_findings": findings,
                "bias_detected": bias_detected,
                "bias_confidence": round(confidence, 3),
                "messages": [{
                    "agent": "bias_detection_agent",
                    "event": "complete",
                    "backend": _ANOMALY_BACKEND,
                    "bias_detected": bias_detected,
                    "llm_called": llm_usage is not None,
                }],
            }
            log_agent_output("bias_detection_agent", inv_id, output)
            return output

        except Exception as exc:
            log_agent_exception("bias_detection_agent", inv_id, exc)
            log_error(
                logger, inv_id, tenant_id, "bias_detection_agent", type(exc).__name__, str(exc)
            )
            hb_fail = heartbeat.emit("bias_detection_agent", "failed", state["iteration_count"])
            return {
                **hb_fail,
                "status": "analyzing",
                "bias_detected": False,
                "bias_confidence": 0.0,
                "messages": [{"agent": "bias_detection_agent", "event": "error", "error": str(exc)[:200]}],
                "error_log": [f"bias_detection_agent: {type(exc).__name__}: {str(exc)[:200]}"],
            }
