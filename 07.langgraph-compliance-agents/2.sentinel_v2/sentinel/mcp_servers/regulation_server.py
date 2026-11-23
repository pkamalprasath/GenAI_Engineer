"""
MCP Regulation Server — exposes SENTINEL's regulation knowledge base as MCP tools.

External agents (Claude Desktop, Cline, other LangGraph systems) can:
  - search_regulations: semantic search over ECOA, HMDA, FDA, EU AI Act etc.
  - add_regulation: embed and store a new regulation section live
  - list_domains: see what domains are available

IMPORTANT: @mcp.tool() wraps functions in FunctionTool objects — NOT directly callable.
Internal code must use sentinel.tools.regulation_tools directly, never import from here.
"""
from __future__ import annotations

import os
import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("sentinel-regulations")

SENTINEL_API_URL = os.getenv("SENTINEL_API_URL", "http://localhost:8003")
SENTINEL_API_KEY = os.getenv("SENTINEL_API_KEY", "sentinel-dev-key-change-in-production")
SENTINEL_TENANT  = os.getenv("SENTINEL_TENANT_ID", "bank-acme")

_HEADERS = {
    "X-API-Key":   SENTINEL_API_KEY,
    "X-Tenant-ID": SENTINEL_TENANT,
    "Content-Type": "application/json",
}


@mcp.tool()
async def search_regulations(query: str, domain: str = "finance", top_k: int = 5) -> dict:
    """
    Search SENTINEL's compliance regulation knowledge base using semantic similarity.

    Returns ranked regulation sections relevant to the query — use this before
    performing any compliance analysis to ground your response in actual law.

    Args:
        query:  Natural language query, e.g. "credit denial discrimination adverse action"
        domain: Regulatory domain — finance | pharma | generic
        top_k:  Number of results to return (1-10)

    Returns:
        List of regulation sections with regulation_name, section, text, and relevance score
    """
    from sentinel.tools.regulation_tools import search_regulations as _search
    try:
        results = await _search(query=query, domain=domain, top_k=top_k)
        return {
            "success": True,
            "query": query,
            "domain": domain,
            "results": results,
            "count": len(results),
        }
    except Exception as exc:
        return {"success": False, "error": str(exc), "results": []}


@mcp.tool()
async def add_regulation(
    regulation_name: str,
    full_name: str,
    section: str,
    content: str,
    domain: str = "finance",
) -> dict:
    """
    Add a new regulation section to SENTINEL's knowledge base.

    The section is embedded immediately and available to the legal agent
    on the next investigation — no code change, no restart required.

    Call this when a new law, amendment, or regulatory guidance is published.

    Args:
        regulation_name: Short name, e.g. "GLBA"
        full_name:       Full statutory name, e.g. "Gramm-Leach-Bliley Act"
        section:         Section identifier, e.g. "15 U.S.C. § 6802"
        content:         Full text of the regulation section
        domain:          finance | pharma | generic

    Returns:
        Confirmation with id and whether embedding succeeded
    """
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{SENTINEL_API_URL}/api/v1/regulations",
                headers=_HEADERS,
                json={
                    "regulation_name": regulation_name,
                    "full_name": full_name,
                    "section": section,
                    "content": content,
                    "domain": domain,
                },
            )
        if resp.status_code == 201:
            data = resp.json()
            return {
                "success": True,
                "id": data["id"],
                "regulation_name": regulation_name,
                "section": section,
                "embedded": data.get("embedded", False),
                "message": f"Added {regulation_name} — {section}. Legal agent will use it on the next investigation.",
            }
        elif resp.status_code == 409:
            return {"success": False, "error": f"Already exists: {regulation_name} — {section}"}
        else:
            return {"success": False, "error": f"API error {resp.status_code}: {resp.text[:200]}"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@mcp.resource("regulations://domains")
async def list_domains() -> list[str]:
    """List available regulatory domains in SENTINEL."""
    return ["finance", "pharma", "generic"]


@mcp.resource("regulations://summary")
async def regulation_summary() -> str:
    """Summary of regulations currently in SENTINEL's knowledge base."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{SENTINEL_API_URL}/api/v1/regulations", headers=_HEADERS)
        if resp.status_code != 200:
            return "Unable to fetch regulation list from SENTINEL API."
        regs = resp.json()
        if not regs:
            return "No regulations currently in SENTINEL. Run `python scripts/ingest_regulations.py` to add them."
        grouped: dict[str, list] = {}
        for r in regs:
            grouped.setdefault(r["regulation_name"], []).append(r["section"])
        lines = ["# SENTINEL Regulation Library\n"]
        for name, sections in sorted(grouped.items()):
            lines.append(f"## {name} ({len(sections)} sections)")
            for s in sections[:3]:
                lines.append(f"  - {s}")
            if len(sections) > 3:
                lines.append(f"  - ... and {len(sections) - 3} more")
        return "\n".join(lines)
    except Exception as exc:
        return f"Error fetching regulations: {exc}"
