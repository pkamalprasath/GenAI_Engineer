"""
Debug utilities for SENTINEL agent execution.
Provides detailed logging and mock response generation for testing.
"""
import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def log_agent_input(agent_name: str, inv_id: str, state_keys: list[str], values: dict) -> None:
    """Log agent inputs in structured format."""
    logger.info(
        f"[{agent_name.upper()}] INPUT: inv_id={inv_id}, keys={state_keys}",
        extra={
            "agent": agent_name,
            "investigation_id": inv_id,
            "input_keys": state_keys,
            "input_summary": {k: v for k, v in values.items() if k in state_keys},
        }
    )


def log_agent_output(agent_name: str, inv_id: str, output: dict) -> None:
    """Log agent outputs in structured format."""
    output_keys = list(output.keys())
    logger.info(
        f"[{agent_name.upper()}] OUTPUT: inv_id={inv_id}, keys={output_keys}",
        extra={
            "agent": agent_name,
            "investigation_id": inv_id,
            "output_keys": output_keys,
            "output_summary": {k: str(v)[:100] if not isinstance(v, (int, float, bool)) else v
                              for k, v in output.items()},
        }
    )


def log_agent_exception(agent_name: str, inv_id: str, exc: Exception) -> None:
    """Log agent exceptions with full context."""
    logger.error(
        f"[{agent_name.upper()}] EXCEPTION: {type(exc).__name__}: {str(exc)[:200]}",
        exc_info=True,
        extra={
            "agent": agent_name,
            "investigation_id": inv_id,
            "exception_type": type(exc).__name__,
            "exception_message": str(exc)[:200],
        }
    )


def generate_mock_discovery_output(state: dict) -> dict:
    """DISABLED: Use real discovery agent instead.
    Generate mock discovery agent output for testing with applicant_data."""
    # Mock disabled - use real agent flow
    return {}

    # Mock: assume relevant case exists if applicant_data provided
    mock_case_id = f"CASE-{applicant_data.get('applicant_id', 'UNKNOWN')}"

    logger.info(
        f"[MOCK] DISCOVERY generating mock output for applicant_id={applicant_data.get('applicant_id')}",
        extra={"mode": "mock", "applicant_id": applicant_data.get("applicant_id")}
    )

    return {
        "relevant_case_ids": [mock_case_id],
        "case_count": 1,
        "discovery_confidence": 0.95,
        "status": "investigating",
        "messages": [{
            "agent": "discovery_agent",
            "event": "complete",
            "backend": "mock",
            "case_count": 1,
            "confidence": 0.95,
        }],
    }


def generate_mock_investigation_output(state: dict) -> dict:
    """DISABLED: Use real investigation agent instead.
    Generate mock investigation agent output for testing with applicant_data."""
    # Mock disabled - use real agent flow
    return {}

    # Mock evidence based on applicant data
    evidence = []
    if denied and denial_reason:
        evidence.append({
            "evidence_id": f"EV-{applicant_id}-001",
            "description": f"Applicant denied due to: {denial_reason.replace('_', ' ')}",
            "provenance_node_id": f"PROV-{applicant_id}-001",
            "trust_score": 0.9,
            "source_type": "decision_record",
        })

    # Mock decision chain
    decision_chain = {
        "applicant_id": applicant_id,
        "decision": "DENIED" if denied else "APPROVED",
        "reason": denial_reason or "Met lending criteria",
        "factors": list(applicant_data.keys()),
    }

    return {
        "evidence_items": evidence,
        "decision_chains": [decision_chain],
        "investigation_sufficient": True,
        "investigation_iterations": 1,
        "status": "investigating",
        "messages": [{
            "agent": "investigation_agent",
            "event": "complete",
            "evidence_count": len(evidence),
        }],
    }


def generate_mock_legal_output(state: dict) -> dict:
    """DISABLED: Use real legal agent instead.
    Generate mock legal analysis agent output for testing with applicant_data."""
    # Mock disabled - use real agent flow
    return {}

    applicant_id = applicant_data.get("applicant_id", "UNKNOWN")
    race = applicant_data.get("race", "")
    denied = applicant_data.get("denied", False)
    credit_score = applicant_data.get("credit_score", 0)
    adverse_notice = applicant_data.get("adverse_action_notice_sent")

    # Normalize credit score: convert string tiers to numeric values
    if isinstance(credit_score, str):
        credit_map = {'excellent': 750, 'good': 700, 'fair': 600, 'poor': 550}
        credit_score = credit_map.get(credit_score.lower(), 700)
    credit_score = float(credit_score) if isinstance(credit_score, (int, float)) else 700

    logger.info(
        f"[MOCK] LEGAL generating mock output for applicant_id={applicant_id}, race={race}",
        extra={"mode": "mock", "applicant_id": applicant_id, "race": race}
    )

    # Mock compliance check based on applicant data
    # KEY: Denied applications start as UNCERTAIN, not COMPLIANT
    verdict = "UNCERTAIN" if denied else "COMPLIANT"
    risk = "MEDIUM" if denied else "LOW"
    regulations = ["Fair Housing Act", "FCRA"]

    # If denied, always analyze for disparate impact
    if denied:
        regulations.append("Disparate Impact Analysis Required")

        # ECOA: adverse action notice required
        if adverse_notice is False:
            verdict = "VIOLATION"
            risk = "HIGH"
            regulations.append("ECOA - Adverse Action Notice Required")

        # Race + denial + any low credit = potential discrimination
        if race in ["African American", "Hispanic", "Black"] and credit_score < 750:
            if verdict == "UNCERTAIN":
                verdict = "VIOLATION"
                risk = "HIGH"
            regulations.append("Fair Lending - Disparate Impact/Discrimination")

    # Redlining check
    if applicant_data.get("neighborhood_redlining_indicator"):
        if verdict == "COMPLIANT":
            verdict = "UNCERTAIN"
        if risk == "LOW":
            risk = "MEDIUM"
        regulations.append("Community Reinvestment Act - Redlining Indicator")

    citations = [f"{reg.split(' - ')[0]} Compliance Check" for reg in regulations]

    return {
        "compliance_verdict": verdict,
        "regulatory_risk": risk,
        "applicable_regulations": regulations,
        "legal_citations": citations,
        "legal_messages": [],
        "status": "analyzing",
        "messages": [{
            "agent": "legal_agent",
            "event": "complete",
            "verdict": verdict,
            "risk": risk,
        }],
    }


def generate_mock_bias_output(state: dict) -> dict:
    """DISABLED: Use real bias detection agent instead.
    Generate mock bias detection agent output for testing with applicant_data."""
    # Mock disabled - use real agent flow
    return {}

    # Mock bias detection based on applicant data
    bias_detected = False
    bias_confidence = 0.0
    findings = []

    # Potential disparate impact if minority race + denial + low credit score
    if denied and race in ["African American", "Hispanic", "Black", "Asian"] and credit_score < 650:
        bias_detected = True
        bias_confidence = 0.75
        findings.append({
            "dimension": "race_credit_interaction",
            "finding": f"Applicant identified as {race} with credit score {credit_score} was denied. Consider disparate impact analysis.",
            "confidence": 0.75,
        })

    # Gender-based analysis if present
    if "gender" in applicant_data:
        findings.append({
            "dimension": "gender",
            "finding": f"Gender field present: {applicant_data.get('gender')}. No adverse pattern detected.",
            "confidence": 0.5,
        })

    # Age-based analysis if present
    age = applicant_data.get("age")
    if age:
        if age > 60 or age < 25:
            findings.append({
                "dimension": "age",
                "finding": f"Applicant age {age} outside typical prime lending range. Monitor for age discrimination.",
                "confidence": 0.4,
            })

    # Family status / FHA analysis
    if applicant_data.get("family_status"):
        bias_detected = True
        findings.append({
            "dimension": "family_status",
            "finding": f"Family status indicated: {applicant_data.get('family_status')}. FHA protections apply.",
            "confidence": 0.8,
        })

    # Disability accommodation analysis
    if applicant_data.get("disability"):
        bias_detected = True
        findings.append({
            "dimension": "disability",
            "finding": f"Disability indicated: {applicant_data.get('disability')}. FHA reasonable accommodation required.",
            "confidence": 0.9,
        })

    dimensions_checked = [f["dimension"] for f in findings]

    return {
        "bias_detected": bias_detected,
        "bias_confidence": bias_confidence,
        "bias_dimensions_checked": dimensions_checked,
        "statistical_findings": findings,
        "status": "analyzing",
        "messages": [{
            "agent": "bias_detection_agent",
            "event": "complete",
            "bias_detected": bias_detected,
            "dimensions": len(dimensions_checked),
        }],
    }


def generate_mock_report_output(state: dict) -> dict:
    """DISABLED: Use real report agent instead.
    Generate mock report agent output for testing with applicant_data."""
    # Mock disabled - use real agent flow
    return {}

    verdict = state.get("compliance_verdict", "UNCERTAIN")
    risk = state.get("regulatory_risk", "MEDIUM")
    bias_detected = state.get("bias_detected", False)

    # Build report content
    report_lines = [
        f"COMPLIANCE INVESTIGATION REPORT",
        f"Investigation ID: {state.get('investigation_id', 'UNKNOWN')}",
        f"Applicant: {applicant_name} ({applicant_id})",
        f"Date: 2026-04-25",
        f"",
        f"EXECUTIVE SUMMARY",
        f"Compliance Verdict: {verdict}",
        f"Regulatory Risk: {risk}",
        f"Bias Detection: {'Yes' if bias_detected else 'No'}",
        f"",
        f"FINDINGS",
        f"The investigation analyzed loan application from {applicant_name}.",
    ]

    # Add specific findings based on applicant data
    if applicant_data.get("denied"):
        report_lines.append(f"Status: Application DENIED - Reason: {applicant_data.get('denial_reason', 'Unknown')}")
    else:
        approved_rate = applicant_data.get("approved_rate")
        if approved_rate:
            report_lines.append(f"Status: Application APPROVED - Rate: {approved_rate}%")

    if applicant_data.get("race"):
        report_lines.append(f"Protected Class: {applicant_data.get('race')}")

    report_lines.append("")
    report_lines.append("COMPLIANCE ASSESSMENT")

    if verdict == "COMPLIANT":
        report_lines.append(f"No compliance violations identified. Application decision appears compliant with applicable regulations.")
    elif verdict == "VIOLATION":
        report_lines.append(f"Potential compliance violation identified. Immediate remediation required.")
    else:
        report_lines.append(f"Compliance status uncertain. Human review recommended.")

    if bias_detected:
        report_lines.append("")
        report_lines.append("BIAS ANALYSIS")
        report_lines.append("Statistical analysis detected potential bias indicators. Further investigation recommended.")

    report_lines.append("")
    report_lines.append("RECOMMENDATION")
    if verdict == "VIOLATION" or risk == "CRITICAL":
        report_lines.append("ESCALATE: Refer to legal review immediately.")
    elif verdict == "UNCERTAIN" or bias_detected:
        report_lines.append("REVIEW: Human review recommended before closure.")
    else:
        report_lines.append("APPROVE: No further action required.")

    draft_report = "\n".join(report_lines)

    return {
        "draft_report": draft_report,
        "final_report": draft_report,
        "report_citations": state.get("legal_citations", []),
        "report_confidence": 0.85,
        "status": "complete",
        "messages": [{
            "agent": "report_agent",
            "event": "complete",
            "report_length": len(draft_report),
            "confidence": 0.85,
        }],
    }
