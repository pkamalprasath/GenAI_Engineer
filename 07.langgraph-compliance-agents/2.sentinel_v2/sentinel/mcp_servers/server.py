"""
SENTINEL MCP Server — unified entry point for all 3 MCP servers.

Usage:
    python -m sentinel.mcp_servers.server              # stdio transport (Claude Desktop)
    MCP_TRANSPORT=sse python -m sentinel.mcp_servers.server  # SSE transport (remote agents)

Claude Desktop config (~/.config/Claude/claude_desktop_config.json on macOS,
%APPDATA%\\Claude\\claude_desktop_config.json on Windows):
{
  "mcpServers": {
    "sentinel": {
      "command": "python",
      "args": ["-m", "sentinel.mcp_servers.server"],
      "env": {
        "SENTINEL_API_URL": "http://localhost:8003",
        "SENTINEL_API_KEY": "your-api-key",
        "SENTINEL_TENANT_ID": "bank-acme"
      }
    }
  }
}

Available tools (visible to Claude Desktop after connecting):
  Regulations:
    - search_regulations(query, domain, top_k)
    - add_regulation(regulation_name, full_name, section, content, domain)
    - regulations://domains  [resource]
    - regulations://summary  [resource]

  Investigations:
    - trigger_investigation(query, date_from, date_to, domain, tenant_id)
    - get_investigation_status(investigation_id, tenant_id)
    - list_investigations(limit, tenant_id)

  Provenance:
    - trace_decision_chain(investigation_id, case_id, tenant_id)
    - verify_integrity(investigation_id, tenant_id)
    - provenance://{investigation_id}/summary  [resource]
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure project root is on path when running as module
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env", override=True)

from mcp.server.fastmcp import FastMCP

# Import the three individual servers
from sentinel.mcp_servers.regulation_server  import mcp as reg_mcp
from sentinel.mcp_servers.investigation_server import mcp as inv_mcp
from sentinel.mcp_servers.provenance_server  import mcp as prov_mcp

# Unified server — merges all tools from the three sub-servers
sentinel_mcp = FastMCP(
    "sentinel",
    instructions=(
        "SENTINEL is an autonomous AI compliance investigation platform. "
        "Use search_regulations() to find relevant laws before analysis. "
        "Use trigger_investigation() to start a compliance investigation, then "
        "poll get_investigation_status() every 10-15 seconds until complete. "
        "Use trace_decision_chain() to inspect W3C PROV-O provenance and verify "
        "integrity of AI credit decisions. "
        "Use add_regulation() to add new laws or amendments to the knowledge base."
    ),
)

# Mount all tools from sub-servers onto the unified server
for tool in reg_mcp._tool_manager.tools.values():
    sentinel_mcp._tool_manager.add_tool(tool)

for tool in inv_mcp._tool_manager.tools.values():
    sentinel_mcp._tool_manager.add_tool(tool)

for tool in prov_mcp._tool_manager.tools.values():
    sentinel_mcp._tool_manager.add_tool(tool)


def main() -> None:
    transport = os.getenv("MCP_TRANSPORT", "stdio")

    if transport == "sse":
        port = int(os.getenv("MCP_SSE_PORT", "8004"))
        print(f"Starting SENTINEL MCP server on SSE transport — port {port}", flush=True)
        sentinel_mcp.run(transport="sse", port=port)
    else:
        # stdio — default for Claude Desktop
        sentinel_mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
