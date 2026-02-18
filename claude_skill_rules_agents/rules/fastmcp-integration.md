# Rule: FastMCP Integration

## The Critical Discovery

`@mcp.tool()` wraps functions in `FunctionTool` objects — they are NOT directly callable.

```python
# What you write:
@mcp.tool()
async def get_channel_messages(channel_id: str, hours: int = 24) -> dict:
    return {"messages": [...]}

# What FastMCP creates:
get_channel_messages = FunctionTool(
    name="get_channel_messages",
    description="...",
    input_schema={...},
    callable=<original_function>
)
# This is an OBJECT, not a function. You CANNOT call it with ()
```

---

## Rule 1: Never Import MCP-Decorated Functions for Internal Use

```python
# WRONG — Causes 'FunctionTool' object is not callable
from src.mcp_servers.slack_server import get_channel_messages
result = await get_channel_messages(channel_id, hours)  # FAILS!

# RIGHT — Use Slack SDK directly
from slack_sdk.web.async_client import AsyncWebClient
from config.settings import settings

async def _get_channel_messages(channel_id: str, hours: int = 24):
    try:
        slack_client = AsyncWebClient(token=settings.slack_bot_token)
        response = await slack_client.conversations_history(channel=channel_id, limit=100)
        return {"success": True, "messages": response.get("messages", [])}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

---

## Rule 2: MCP Servers Are for External Clients ONLY

```
CORRECT architecture:

External MCP Client (Claude Desktop, etc.)
        |
        | MCP Protocol
        v
src/mcp_servers/slack_server.py   (@mcp.tool() functions — external interface)
        |
        v
Slack SDK (AsyncWebClient)

WRONG architecture:

src/agent/tools.py     (internal agent code)
        |
        | Direct import ❌
        v
src/mcp_servers/slack_server.py   (MCP-decorated — not callable internally!)
```

---

## Rule 3: Share Logic via Utility Modules

If both MCP server and agent need the same Slack calls, extract to a shared helper:

```python
# src/utils/slack_helpers.py — plain async function, no decorators
async def fetch_channel_messages(channel_id: str, hours: int = 24) -> dict:
    slack_client = AsyncWebClient(token=settings.slack_bot_token)
    response = await slack_client.conversations_history(channel=channel_id, limit=100)
    return {"success": True, "messages": response.get("messages", [])}

# src/agent/tools.py — internal agent tool
from src.utils.slack_helpers import fetch_channel_messages
async def _get_channel_messages(self, channel_id: str, hours: int = 24):
    return await fetch_channel_messages(channel_id, hours)

# src/mcp_servers/slack_server.py — external MCP interface
from src.utils.slack_helpers import fetch_channel_messages
@mcp.tool()
async def get_channel_messages(channel_id: str, hours: int = 24) -> dict:
    return await fetch_channel_messages(channel_id, hours)
```

---

## Rule 4: If You Must Call MCP Tools Internally, Use MCP Client Protocol

```python
from mcp import ClientSession
from mcp.client.stdio import stdio_client

async def call_mcp_tool():
    async with stdio_client("python", ["src/mcp_servers/slack_server.py"]) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "get_channel_messages",
                arguments={"channel_id": "C123", "hours": 24}
            )
            return result
# Note: This has protocol overhead — only for testing MCP servers, not for internal agent tools
```

---

## Decision Tree

```
Need to implement functionality?
|
├─ For EXTERNAL MCP clients (Claude Desktop, Cline, etc.)
|  └─ Use @mcp.tool() in src/mcp_servers/
|
└─ For INTERNAL agent/bot use
   └─ Use SDK directly in src/agent/tools.py
      (or extract shared logic to src/utils/)
```

---

## Summary

| Context | Approach |
|---|---|
| External MCP client integration | `@mcp.tool()` in `mcp_servers/` |
| Internal agent tool | `AsyncWebClient` in `agent/tools.py` |
| Shared business logic | Plain `async def` in `utils/` |
| Testing MCP server | MCP client protocol |

**The fix for Problem #13 in open_claw_slack_bot:**
- 8 broken tools importing MCP functions
- Rewrote all 8 to use Slack SDK directly
- Agent fully functional after fix
