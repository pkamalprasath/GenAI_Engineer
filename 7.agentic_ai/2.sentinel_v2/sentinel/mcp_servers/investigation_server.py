"""
MCP Investigation Server — triggers and monitors SENTINEL compliance investigations.

External orchestrators (Claude Desktop, other LangGraph agents) can:
  - trigger_investigation: start a new compliance investigation
  - get_investigation_status: poll for results and final report
  - list_investigations: see recent investigations for a tenant

All calls route through SENTINEL's REST API — auth, rate-limiting, and
tenant isolation apply automatically.
"""
from __future__ import annotations

import os
import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("sentinel-investigations")

SENTINEL_API_URL = os.getenv("SENTINEL_API_URL", "http://localhost:8003")
SENTINEL_API_KEY = os.getenv("SENTINEL_API_KEY", "sentinel-dev-key-change-in-production")
SENTINEL_TENANT  = os.getenv("SENTINEL_TENANT_ID", "bank-acme")

_HEADERS = {
    "X-API-Key":    SENTINEL_API_KEY,
    "X-Tenant-ID":  SENTINEL_TENANT,
    "Content-Type": "application/json",
}


@mcp.tool()
async def trigger_investigation(
    query: str,
    date_from: str,
    date_to: str,
    domain: str = "finance",
    tenant_id: str = "",
) -> dict:
    """
    Trigger a SENTINEL compliance investigation.

    SENTINEL will autonomously discover relevant cases, trace provenance chains,
    run legal and bias analysis, and generate a regulatory-grade report.
    Poll get_investigation_status() until status=complete or pending_human.

    Args:
        query:     Plain-English investigation query, e.g.
                   "Review credit decisions Jan 2024 for ECOA fair lending compliance"
        date_from: Start date in YYYY-MM-DD format
        date_to:   End date in YYYY-MM-DD format
        domain:    Regulatory domain — finance | pharma | generic
        tenant_id: Override tenant (uses env default if empty)

    Returns:
        investigation_id to use for polling, and initial status
    """
    headers = dict(_HEADERS)
    if tenant_id:
        headers["X-Tenant-ID"] = tenant_id

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{SENTINEL_API_URL}/api/v1/investigations",
                headers=headers,
                json={
                    "query":        query,
                    "date_from":    date_from,
                    "date_to":      date_to,
                    "domain":       domain,
                    "trigger_mode": "reactive",
                },
            )
        if resp.status_code == 202:
            data = resp.json()
            return {
                "success":          True,
                "investigation_id": data["investigation_id"],
                "status":           data["status"],
                "message":          f"Investigation started. Poll get_investigation_status('{data['investigation_id']}') every 10s until complete (~45s total).",
            }
        else:
            return {"success": False, "error": f"API error {resp.status_code}: {resp.text[:300]}"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@mcp.tool()
async def get_investigation_status(investigation_id: str, tenant_id: str = "") -> dict:
    """
    Poll the status of a SENTINEL investigation.

    Call every 10-15 seconds after trigger_investigation().
    When status=complete or pending_human, final_report contains the compliance report.

    Args:
        investigation_id: ID returned by trigger_investigation, e.g. "INV-7AA30B1C59D0"
        tenant_id:        Override tenant (uses env default if empty)

    Returns:
        status, compliance_verdict, regulatory_risk, bias_detected, final_report (when ready)
    """
    headers = dict(_HEADERS)
    if tenant_id:
        headers["X-Tenant-ID"] = tenant_id

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{SENTINEL_API_URL}/api/v1/investigations/{investigation_id}",
                headers=headers,
            )
        if resp.status_code == 200:
            data = resp.json()
            result = {
                "success":            True,
                "investigation_id":   investigation_id,
                "status":             data["status"],
                "compliance_verdict": data.get("compliance_verdict"),
                "regulatory_risk":    data.get("regulatory_risk"),
                "bias_detected":      data.get("bias_detected", False),
                "bias_confidence":    data.get("bias_confidence", 0),
                "report_confidence":  data.get("report_confidence", 0),
                "case_count":         data.get("case_count", 0),
                "hitl_required":      data.get("hitl_required", False),
                "total_cost_usd":     data.get("total_cost_usd", 0),
            }
            if data.get("final_report"):
                result["final_report"] = data["final_report"]
            if data.get("status") == "pending_human":
                result["message"] = "Human review required. A compliance officer must approve the draft report via the SENTINEL dashboard or escalation API."
            elif data.get("status") == "complete":
                result["message"] = "Investigation complete. final_report contains the regulatory compliance report."
            else:
                result["message"] = f"Investigation in progress (status={data['status']}). Poll again in 10-15 seconds."
            return result
        elif resp.status_code == 404:
            return {"success": False, "error": f"Investigation {investigation_id} not found"}
        else:
            return {"success": False, "error": f"API error {resp.status_code}: {resp.text[:200]}"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@mcp.tool()
async def list_investigations(limit: int = 10, tenant_id: str = "") -> dict:
    """
    List recent compliance investigations for the tenant.

    Args:
        limit:     Maximum number of investigations to return (1-50)
        tenant_id: Override tenant (uses env default if empty)

    Returns:
        List of recent investigations with status and verdicts
    """
    headers = dict(_HEADERS)
    if tenant_id:
        headers["X-Tenant-ID"] = tenant_id

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{SENTINEL_API_URL}/api/v1/escalations",
                headers=headers,
            )
        if resp.status_code == 200:
            data = resp.json()
            return {
                "success": True,
                "investigations": data[:limit],
                "count": len(data[:limit]),
            }
        else:
            return {"success": False, "error": f"API error {resp.status_code}: {resp.text[:200]}"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}
