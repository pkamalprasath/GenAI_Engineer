# Rules: FastMCP Integration

## Understanding FastMCP Decorator Behavior

### The Critical Discovery: Problem #13

**What Happened:**
- All agent Slack tools completely broken
- Error: `'FunctionTool' object is not callable`
- Root cause: FastMCP's `@mcp.tool()` decorator wraps functions in non-callable objects

---

## Rule 1: Never Import MCP-Decorated Functions

### The Decorator Transformation

When you write:
```python
# In src/mcp_servers/slack_server.py
from mcp import FastMCP

mcp = FastMCP("Slack Server")

@mcp.tool()
async def get_channel_messages(channel_id: str, hours: int = 24) -> dict:
    """Fetch messages from a Slack channel."""
    # Implementation
    return {"messages": [...]}
```

FastMCP transforms it into:
```python
get_channel_messages = FunctionTool(
    name="get_channel_messages",
    description="Fetch messages from a Slack channel.",
    input_schema={...},
    callable=<original_function>
)
```

**This is NOT a function anymore!**

---

### ❌ WRONG: Direct Import

```python
# In src/agent/tools.py
from src.mcp_servers.slack_server import get_channel_messages

async def _get_channel_messages(channel_id: str, hours: int):
    # FAILS: 'FunctionTool' object is not callable
    result = await get_channel_messages(channel_id, hours)
    return result
```

**Why this fails:**
- `get_channel_messages` is now a `FunctionTool` object, not a function
- You can't call it with `()`
- Python raises: `'FunctionTool' object is not callable`

---

### ✅ RIGHT: Use SDK Directly

```python
# In src/agent/tools.py
from slack_sdk.web.async_client import AsyncWebClient
from config.settings import settings

async def _get_channel_messages(channel_id: str, hours: int = 24):
    """Fetch messages from a Slack channel."""
    try:
        slack_client = AsyncWebClient(token=settings.slack_bot_token)

        response = await slack_client.conversations_history(
            channel=channel_id,
            limit=100
        )

        messages = response.get("messages", [])

        return {
            "success": True,
            "messages": messages,
            "count": len(messages)
        }
    except Exception as e:
        logger.error("Failed to fetch messages: %s", e)
        return {"success": False, "error": str(e)}
```

**Why this works:**
- Directly uses the underlying SDK
- No decorator wrapping
- Full control over error handling
- Returns proper dict format for agent

---

## Rule 2: MCP Servers Are for External Clients

### MCP Server Purpose

MCP servers should **only** expose tools to **external MCP clients** (like Claude Desktop, other apps).

**Good use of MCP server:**
```
┌─────────────────┐
│ Claude Desktop  │ (External MCP client)
└────────┬────────┘
         │ MCP Protocol
         ▼
┌─────────────────────────┐
│ src/mcp_servers/        │
│   slack_server.py       │ (Exposes @mcp.tool() functions)
└─────────────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Slack SDK               │
└─────────────────────────┘
```

**Bad use of MCP server:**
```
┌─────────────────────────┐
│ src/agent/tools.py      │ (Internal agent code)
└────────┬────────────────┘
         │ Direct import ❌
         ▼
┌─────────────────────────┐
│ src/mcp_servers/        │
│   slack_server.py       │ (@mcp.tool() decorated)
└─────────────────────────┘
```

---

### Correct Architecture

**Internal agent tools → SDK directly:**
```python
# src/agent/tools.py
from slack_sdk.web.async_client import AsyncWebClient

class ToolRegistry:
    async def _post_message(self, channel_id: str, text: str):
        slack_client = AsyncWebClient(token=settings.slack_bot_token)
        response = await slack_client.chat_postMessage(
            channel=channel_id,
            text=text
        )
        return {"success": True, "ts": response["ts"]}
```

**External MCP clients → MCP server:**
```python
# src/mcp_servers/slack_server.py
@mcp.tool()
async def post_message(channel_id: str, text: str) -> dict:
    """Post a message to Slack channel (for external MCP clients)."""
    slack_client = AsyncWebClient(token=settings.slack_bot_token)
    response = await slack_client.chat_postMessage(
        channel=channel_id,
        text=text
    )
    return {"success": True, "ts": response["ts"]}
```

**Key difference:**
- Agent tools: Internal, fast, direct SDK access
- MCP tools: External interface, protocol overhead

---

## Rule 3: If You Must Use MCP Tools Internally, Use MCP Client

If you absolutely need to call MCP tools from internal code (rare), use the MCP client protocol:

```python
from mcp import ClientSession
from mcp.client.stdio import stdio_client

async def call_mcp_tool():
    # Connect as MCP client
    async with stdio_client("python", ["src/mcp_servers/slack_server.py"]) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize
            await session.initialize()

            # List tools
            tools = await session.list_tools()

            # Call tool via protocol
            result = await session.call_tool(
                "get_channel_messages",
                arguments={"channel_id": "C123", "hours": 24}
            )

            return result
```

**When to use this:**
- Testing MCP servers
- Integration with external MCP infrastructure
- Never for internal agent tools (too much overhead)

---

## Rule 4: Shared Logic Should Be in Utils

If both MCP server and agent need the same logic, extract to shared utilities:

```python
# src/utils/slack_helpers.py
from slack_sdk.web.async_client import AsyncWebClient
from config.settings import settings

async def fetch_channel_messages(channel_id: str, hours: int = 24) -> dict:
    """Shared helper for fetching Slack messages."""
    slack_client = AsyncWebClient(token=settings.slack_bot_token)

    response = await slack_client.conversations_history(
        channel=channel_id,
        limit=100
    )

    return {
        "success": True,
        "messages": response.get("messages", [])
    }
```

**Then use in both places:**

```python
# src/agent/tools.py
from src.utils.slack_helpers import fetch_channel_messages

async def _get_channel_messages(channel_id: str, hours: int):
    return await fetch_channel_messages(channel_id, hours)
```

```python
# src/mcp_servers/slack_server.py
from src.utils.slack_helpers import fetch_channel_messages

@mcp.tool()
async def get_channel_messages(channel_id: str, hours: int = 24) -> dict:
    """Fetch messages from Slack (MCP interface)."""
    return await fetch_channel_messages(channel_id, hours)
```

**Benefits:**
- Single source of truth
- Both paths stay in sync
- Easier to test

---

## Rule 5: Understand MCP Decorator Side Effects

### What @mcp.tool() Actually Does

```python
@mcp.tool()
async def my_function(arg: str) -> dict:
    return {"result": arg}
```

Becomes:
```python
my_function = FunctionTool(
    name="my_function",
    description="<extracted from docstring>",
    input_schema={
        "type": "object",
        "properties": {"arg": {"type": "string"}},
        "required": ["arg"]
    },
    callable=<original_async_function>
)
```

**You can access:**
- `my_function.name` → `"my_function"`
- `my_function.description` → Docstring
- `my_function.input_schema` → JSON schema
- `my_function.callable` → Original function (but use with caution)

**You CANNOT:**
- Call it directly: `await my_function(arg="test")` ❌
- Use it as a normal function

---

## Complete Example: Before and After

### Before (Broken)

```python
# src/mcp_servers/slack_server.py
@mcp.tool()
async def get_channel_messages(channel_id: str, hours: int = 24) -> dict:
    slack_client = AsyncWebClient(token=settings.slack_bot_token)
    response = await slack_client.conversations_history(channel=channel_id)
    return {"messages": response["messages"]}

@mcp.tool()
async def post_message(channel_id: str, text: str) -> dict:
    slack_client = AsyncWebClient(token=settings.slack_bot_token)
    response = await slack_client.chat_postMessage(channel=channel_id, text=text)
    return {"ts": response["ts"]}
```

```python
# src/agent/tools.py
from src.mcp_servers.slack_server import get_channel_messages, post_message

class ToolRegistry:
    async def _get_channel_messages(self, channel_id: str, hours: int = 24):
        # FAILS: 'FunctionTool' object is not callable
        return await get_channel_messages(channel_id, hours)

    async def _post_message(self, channel_id: str, text: str):
        # FAILS: 'FunctionTool' object is not callable
        return await post_message(channel_id, text)
```

**Result:** All agent tools broken ❌

---

### After (Fixed)

```python
# src/mcp_servers/slack_server.py (unchanged - still for external MCP clients)
@mcp.tool()
async def get_channel_messages(channel_id: str, hours: int = 24) -> dict:
    slack_client = AsyncWebClient(token=settings.slack_bot_token)
    response = await slack_client.conversations_history(channel=channel_id)
    return {"messages": response["messages"]}

@mcp.tool()
async def post_message(channel_id: str, text: str) -> dict:
    slack_client = AsyncWebClient(token=settings.slack_bot_token)
    response = await slack_client.chat_postMessage(channel=channel_id, text=text)
    return {"ts": response["ts"]}
```

```python
# src/agent/tools.py (rewritten - use SDK directly)
from slack_sdk.web.async_client import AsyncWebClient
from config.settings import settings

class ToolRegistry:
    async def _get_channel_messages(self, channel_id: str, hours: int = 24):
        try:
            slack_client = AsyncWebClient(token=settings.slack_bot_token)
            response = await slack_client.conversations_history(
                channel=channel_id,
                limit=100
            )
            messages = response.get("messages", [])
            return {"success": True, "messages": messages}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _post_message(self, channel_id: str, text: str):
        try:
            slack_client = AsyncWebClient(token=settings.slack_bot_token)
            response = await slack_client.chat_postMessage(
                channel=channel_id,
                text=text
            )
            return {"success": True, "ts": response["ts"]}
        except Exception as e:
            return {"success": False, "error": str(e)}
```

**Result:** All agent tools working ✅

---

## Summary

### FastMCP Integration Rules

1. **Never import MCP-decorated functions for internal use**
2. **Use underlying SDK directly in agent tools**
3. **MCP servers are for external MCP clients only**
4. **Share logic via utility modules, not MCP functions**
5. **Understand @mcp.tool() transforms functions into FunctionTool objects**

### Quick Decision Tree

```
Need to implement functionality?
│
├─ For external MCP clients (Claude Desktop, etc.)
│  └─ Use @mcp.tool() in mcp_servers/
│
└─ For internal agent/bot
   └─ Use SDK directly in agent/tools.py
```

### The Fix That Solved Problem #13

**Before:** 8 broken tools trying to import MCP functions
**After:** 8 rewritten tools using Slack SDK directly
**Impact:** Agent fully functional, all Slack operations working

This was the most critical fix in the entire project.
