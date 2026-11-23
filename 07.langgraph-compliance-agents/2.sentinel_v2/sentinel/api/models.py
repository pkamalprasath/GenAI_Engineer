"""Pydantic request/response models for the SENTINEL REST API."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator


class InvestigationRequest(BaseModel):
    query: str = Field(..., min_length=10, max_length=5000)
    date_from: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    date_to: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    trigger_mode: str = Field(default="reactive")
    domain: Optional[str] = None     # Defaults to ACTIVE_DOMAIN env var if not provided
    applicant_data: Optional[Dict[str, Any]] = None  # Structured applicant/case data for analysis

    @field_validator("trigger_mode")
    @classmethod
    def validate_trigger(cls, v: str) -> str:
        if v not in {"reactive", "proactive", "scheduled"}:
            raise ValueError("trigger_mode must be reactive, proactive, or scheduled")
        return v


class InvestigationResponse(BaseModel):
    investigation_id: str
    status: str
    tenant_id: str
    created_at: str


class InvestigationResult(BaseModel):
    investigation_id: str
    status: str
    compliance_verdict: Optional[str]
    regulatory_risk: Optional[str]
    bias_detected: bool
    report_confidence: float
    total_cost_usd: float
    final_report: Optional[str]
    hitl_required: bool
    # Per-agent progress fields (populated once agents complete)
    case_count: int = 0
    discovery_confidence: float = 0.0
    evidence_count: int = 0
    investigation_sufficient: Optional[bool] = None
    bias_confidence: float = 0.0
    agent_events: list[dict] = []
    error_log: list[str] = []
    heartbeats: list[dict] = []


class EscalationResolveRequest(BaseModel):
    response: str = Field(..., min_length=10)
    action: str = Field(..., pattern=r"^(approve_draft|modify_response|close_investigation)$")
    reviewer_id: str = Field(..., min_length=1, max_length=100)


class EscalationResponse(BaseModel):
    escalation_id: str
    investigation_id: str
    status: str
    reason: str
    created_at: str
    resolved_at: Optional[str]


class ProvenanceTraceResponse(BaseModel):
    investigation_id: str
    case_id: str
    chain: list[dict]
    node_count: int


class AnalyticsResponse(BaseModel):
    period: str
    total_investigations: int
    compliance_rate: float
    bias_detection_rate: float
    avg_cost_usd: float
    hitl_rate: float
    top_risk_categories: list[dict]


# ── v2: Regulation management ─────────────────────────────────────────────────

class RegulationUploadRequest(BaseModel):
    regulation_name: str = Field(..., min_length=1, max_length=100,
                                  description="Short name, e.g. GLBA")
    full_name: str = Field(..., min_length=1, max_length=300,
                            description="Full statutory name")
    section: str = Field(..., min_length=1, max_length=300,
                          description="Section identifier, e.g. '15 U.S.C. § 6802'")
    content: str = Field(..., min_length=10,
                          description="Full text of the regulation section")
    domain: str = Field(default="finance",
                         description="Domain: finance | pharma | generic")

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v: str) -> str:
        if v not in {"finance", "pharma", "generic"}:
            raise ValueError("domain must be finance, pharma, or generic")
        return v


class RegulationUploadResponse(BaseModel):
    id: int
    regulation_name: str
    full_name: str
    section: str
    domain: str
    embedded: bool
    created_at: str


class RegulationListItem(BaseModel):
    id: int
    regulation_name: str
    full_name: str
    section: str
    domain: str
    active: bool
    created_at: str
