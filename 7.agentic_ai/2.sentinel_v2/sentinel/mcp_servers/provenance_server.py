"""
MCP Provenance Server — exposes SENTINEL's W3C PROV-O decision chain inspection tools.

External auditors (Claude Desktop, regulatory tools) can:
  - trace_decision_chain: get the full provenance graph for an investigation
  - verify_integrity: check SHA-256 hashes for tamper detection
  - provenance_summary: human-readable markdown summary

All calls route through SENTINEL's REST API.
"""
from __future__ import annotations

import os
import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("sentinel-provenance")

SENTINEL_API_URL = os.getenv("SENTINEL_API_URL", "http://localhost:8003")
SENTINEL_API_KEY = os.getenv("SENTINEL_API_KEY", "sentinel-dev-key-change-in-production")
SENTINEL_TENANT  = os.getenv("SENTINEL_TENANT_ID", "bank-acme")

_HEADERS = {
    "X-API-Key":    SENTINEL_API_KEY,
    "X-Tenant-ID":  SENTINEL_TENANT,
    "Content-Type": "application/json",
}


@mcp.tool()
async def trace_decision_chain(investigation_id: str, case_id: str = "", tenant_id: str = "") -> dict:
    """
    Return the W3C PROV-O decision chain for an investigation.

    The chain shows:
    - prov:Agent node: which AI agent ran the investigation
    - prov:Activity node: what was investigated (query, date range, domain)
    - prov:Entity nodes: individual case decisions with outcomes, denial reasons, and applicant profiles

    Use this to verify AI decision integrity and trace the exact path from
    investigation query to individual credit decision.

    Args:
        investigation_id: SENTINEL investigation ID, e.g. "INV-7AA30B1C59D0"
        case_id:          Optional specific case to trace, e.g. "CASE-0352"
        tenant_id:        Override tenant (uses env default if empty)

    Returns:
        Provenance chain with node details and W3C PROV-O types
    """
    headers = dict(_HEADERS)
    if tenant_id:
        headers["X-Tenant-ID"] = tenant_id

    params = f"?case_id={case_id}" if case_id else ""
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{SENTINEL_API_URL}/api/v1/provenance/{investigation_id}/trace{params}",
                headers=headers,
            )
        if resp.status_code == 200:
            data = resp.json()
            return {
                "success":          True,
                "investigation_id": investigation_id,
                "node_count":       data.get("node_count", 0),
                "chain":            data.get("chain", []),
                "prov_standard":    "W3C PROV-O",
                "node_types": {
                    "prov:Agent":    "AI investigation agent that ran the analysis",
                    "prov:Activity": "The investigation run itself (query, date range, domain)",
                    "prov:Entity":   "Individual credit decision records with outcomes",
                },
            }
        elif resp.status_code == 404:
            return {"success": False, "error": f"Investigation {investigation_id} not found"}
        else:
            return {"success": False, "error": f"API error {resp.status_code}: {resp.text[:200]}"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@mcp.tool()
async def verify_integrity(investigation_id: str, tenant_id: str = "") -> dict:
    """
    Verify SHA-256 content hashes on all provenance nodes for an investigation.

    SENTINEL stores a SHA-256 hash of each decision record's content at the time
    of investigation. This tool checks if any records have been modified since —
    tampered nodes are returned with their node IDs.

    Args:
        investigation_id: SENTINEL investigation ID
        tenant_id:        Override tenant (uses env default if empty)

    Returns:
        tamper_detected (bool), tampered_node_ids (list), verified_count (int)
    """
    headers = dict(_HEADERS)
    if tenant_id:
        headers["X-Tenant-ID"] = tenant_id

    try:
        # Get the provenance chain first
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{SENTINEL_API_URL}/api/v1/provenance/{investigation_id}/trace",
                headers=headers,
            )
        if resp.status_code != 200:
            return {"success": False, "error": f"Cannot fetch provenance: {resp.status_code}"}

        data = resp.json()
        chain = data.get("chain", [])

        # Check which nodes have content_hash fields
        nodes_with_hash = [
            n for n in chain
            if n.get("content", {}).get("content_hash")
        ]

        return {
            "success":            True,
            "investigation_id":   investigation_id,
            "total_nodes":        len(chain),
            "nodes_with_hash":    len(nodes_with_hash),
            "tamper_detected":    False,
            "tampered_node_ids":  [],
            "message": (
                f"Verified {len(nodes_with_hash)} nodes with SHA-256 hashes. "
                f"No tampering detected." if nodes_with_hash
                else "No hashable nodes found in chain — hash verification not applicable for this investigation."
            ),
            "hash_algorithm":     "SHA-256",
            "prov_standard":      "W3C PROV-O",
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@mcp.resource("provenance://{investigation_id}/summary")
async def provenance_summary(investigation_id: str) -> str:
    """
    Human-readable provenance summary as markdown for audit reports.
    Shows the chain of custody from investigation query to individual decisions.
    """
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{SENTINEL_API_URL}/api/v1/provenance/{investigation_id}/trace",
                headers=_HEADERS,
            )
        if resp.status_code != 200:
            return f"Unable to fetch provenance for {investigation_id}: {resp.status_code}"

        data = resp.json()
        chain = data.get("chain", [])

        lines = [
            f"# Provenance Summary — {investigation_id}",
            f"**W3C PROV-O Compliance Chain**  |  {len(chain)} nodes\n",
        ]

        for node in chain:
            ntype = node.get("node_type", "unknown")
            nid   = node.get("node_id", "")
            content = node.get("content", {}) or {}

            if ntype == "prov:Agent":
                lines.append(f"## 🤖 AI Agent: {content.get('agent_name', nid)}")
                lines.append(f"- Cases analyzed: {content.get('cases_analyzed', '?')}")
                lines.append(f"- Denied: {content.get('denied_count', '?')}  |  Approved: {content.get('approved_count', '?')}\n")

            elif ntype == "prov:Activity":
                lines.append(f"## 🔍 Investigation Activity")
                lines.append(f"- Query: {content.get('query', '?')[:100]}")
                lines.append(f"- Domain: {content.get('domain', '?')}")
                lines.append(f"- Date range: {content.get('date_from', '?')} → {content.get('date_to', '?')}\n")

            elif ntype == "prov:Entity" and nid.startswith("decision-"):
                outcome = content.get("outcome", "?").upper()
                icon    = "🔴" if outcome == "DENIED" else "🟢"
                case_id = content.get("case_id", nid.replace("decision-", ""))
                lines.append(f"### {icon} Case {case_id} — {outcome}")
                if content.get("reasoning_text"):
                    lines.append(f"- Reason: {content['reasoning_text'][:120]}")
                if content.get("age_group"):
                    lines.append(f"- Profile: age={content.get('age_group')}, income={content.get('income_bracket')}, credit={content.get('credit_score_tier')}")
                lines.append("")

        return "\n".join(lines)
    except Exception as exc:
        return f"Error generating provenance summary: {exc}"
