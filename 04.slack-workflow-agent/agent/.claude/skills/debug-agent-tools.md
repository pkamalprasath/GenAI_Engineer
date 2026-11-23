# Skill: Debug Agent Tools

## Purpose
Systematically debug agent tools when they're not working. Critical for finding issues like Problem #13 (MCP function imports).

## When to Use
- Agent doesn't use expected tools
- Tool execution fails silently
- Agent returns "I don't have that capability"
- Tool appears in logs but doesn't work

## Debugging Steps

### Step 1: Verify Tool Registration

**Check:** Is the tool registered in ToolRegistry?

```python
# In Python shell or test
from src.agent.tools import ToolRegistry

registry = ToolRegistry()
print("Registered tools:", list(registry.tools.keys()))

# Expected output:
# ['get_channel_messages', 'post_message', 'summarize_channel', ...]
```

**If tool is missing:**
- Add to ToolRegistry.__init__()
- Verify method exists (e.g., self._summarize_channel)
- Check conditional registration logic (GitHub/Notion tokens)

---

### Step 2: Verify Tool Schema

**Check:** Does the tool have valid JSON schema?

```python
from src.agent.tools import ToolRegistry

registry = ToolRegistry()
tool = registry.tools.get("summarize_channel")

print("Tool schema:")
print(json.dumps(tool, indent=2, default=str))

# Expected output:
# {
#   "function": <function>,
#   "description": "Generate AI summary...",
#   "parameters": {
#     "type": "object",
#     "properties": {...},
#     "required": [...]
#   }
# }
```

**If schema is invalid:**
- Missing "parameters" key
- Invalid JSON schema syntax
- Missing required fields
- Type mismatches (string vs integer)

**Fix:**
```python
self.tools["tool_name"] = {
    "function": self._tool_method,
    "description": "Clear description for agent",
    "parameters": {
        "type": "object",
        "properties": {
            "param1": {"type": "string", "description": "What is this?"},
            "param2": {"type": "integer", "description": "What is this?"}
        },
        "required": ["param1"]  # Which params are required?
    }
}
```

---

### Step 3: Test Direct Tool Execution

**Check:** Can you call the tool directly?

```python
import asyncio
from src.agent.tools import ToolRegistry

async def test_tool():
    registry = ToolRegistry()

    # Direct execution
    result = await registry.execute_tool(
        "summarize_channel",
        channel_id="C123ABC",
        hours=24
    )

    print("Tool result:", result)
    # Expected: {"success": True, "summary": "..."}
    # NOT: Exception or {"success": False, "error": "..."}

asyncio.run(test_tool())
```

**Common failures:**

**Problem #13: 'FunctionTool' object is not callable**
```python
# WRONG: Importing MCP-decorated function
from src.mcp_servers.slack_server import get_channel_messages
result = await get_channel_messages(...)  # FAILS!
```

**Fix:**
```python
# RIGHT: Use SDK directly
from slack_sdk.web.async_client import AsyncWebClient
slack_client = AsyncWebClient(token=settings.slack_bot_token)
response = await slack_client.conversations_history(...)
```

**Missing parameters:**
```python
# Error: execute_tool() missing required argument 'channel_id'
result = await registry.execute_tool("summarize_channel")  # Missing channel_id!
```

**Fix:**
```python
result = await registry.execute_tool(
    "summarize_channel",
    channel_id="C123ABC",  # Provide required param
    hours=24
)
```

---

### Step 4: Check Tool Function Implementation

**Check:** Does the underlying function work?

```python
from src.agent.tools import ToolRegistry

async def test_function():
    registry = ToolRegistry()

    # Call the actual method (not via execute_tool)
    result = await registry._summarize_channel(
        channel_id="C123ABC",
        hours=24
    )

    print("Direct function result:", result)

asyncio.run(test_function())
```

**If this fails:**
- Check imports (are they importing MCP functions?)
- Check API tokens (Slack, Anthropic, GitHub)
- Check error handling (does it return error dict or raise?)
- Check dependencies (is service available?)

**Example fix (Problem #13):**

**Before (broken):**
```python
from src.mcp_servers.slack_server import get_channel_messages

async def _get_channel_messages(self, channel_id: str, hours: int):
    # FAILS: MCP function not callable
    return await get_channel_messages(channel_id, hours)
```

**After (fixed):**
```python
from slack_sdk.web.async_client import AsyncWebClient
from config.settings import settings

async def _get_channel_messages(self, channel_id: str, hours: int):
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
```

---

### Step 5: Verify Tool Returns Correct Format

**Check:** Does tool return dict (not raise exception)?

```python
async def test_tool_error_handling():
    registry = ToolRegistry()

    # Test with invalid input (should return error dict, not raise)
    result = await registry.execute_tool(
        "get_channel_messages",
        channel_id="INVALID_CHANNEL_ID",
        hours=24
    )

    print("Result:", result)
    # Expected: {"success": False, "error": "..."}
    # NOT: Exception raised
```

**If tool raises exception:**

```python
# WRONG
async def _get_channel_messages(self, channel_id: str, hours: int):
    slack_client = AsyncWebClient(token=settings.slack_bot_token)
    response = await slack_client.conversations_history(channel=channel_id)
    return response["messages"]  # Raises if API fails!
```

**RIGHT:**
```python
async def _get_channel_messages(self, channel_id: str, hours: int):
    try:
        slack_client = AsyncWebClient(token=settings.slack_bot_token)
        response = await slack_client.conversations_history(channel=channel_id)
        messages = response.get("messages", [])
        return {"success": True, "messages": messages}
    except Exception as e:
        logger.error("Tool failed: %s", e)
        return {"success": False, "error": str(e)}
```

---

### Step 6: Test Tool in Agent Context

**Check:** Can agent actually use the tool?

```python
from src.agent.orchestrator import Orchestrator

async def test_agent_tool_usage():
    orchestrator = Orchestrator()

    # Ask agent to use the tool
    response = await orchestrator.chat(
        conversation_id="test-123",
        user_message="Summarize #general from the last 24 hours"
    )

    print("Agent response:", response)
    # Should see agent using summarize_channel tool
```

**Check logs for:**
```
[DEBUG] Agent reasoning: I need to summarize #general...
[DEBUG] Executing tool: summarize_channel
[DEBUG] Tool parameters: {"channel_id": "C123", "hours": 24}
[DEBUG] Tool result: {"success": True, "summary": "..."}
```

**If agent doesn't use tool:**
- Tool not in system prompt (check build_system_prompt)
- Tool description unclear (agent doesn't know when to use it)
- Tool parameters confusing (agent can't figure out how to call it)
- Agent has other preferred tools (check tool priority)

---

### Step 7: Check API Tokens and Permissions

**Check:** Are credentials valid and have required scopes?

```python
# Test Slack token
from slack_sdk.web.async_client import AsyncWebClient
from config.settings import settings

async def test_slack_token():
    client = AsyncWebClient(token=settings.slack_bot_token)
    try:
        response = await client.auth_test()
        print("Slack token valid:", response["ok"])
        print("Bot user:", response["user"])
    except Exception as e:
        print("Slack token INVALID:", e)

asyncio.run(test_slack_token())
```

```python
# Test Anthropic token
from anthropic import AsyncAnthropic
from config.settings import settings

async def test_anthropic_token():
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    try:
        response = await client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}]
        )
        print("Anthropic token valid")
    except Exception as e:
        print("Anthropic token INVALID:", e)

asyncio.run(test_anthropic_token())
```

**If tokens are invalid:**
- Check `.env` file
- Verify token prefixes (xoxb-, sk-ant-, ghp-, etc.)
- Check token permissions/scopes in API dashboard
- Regenerate tokens if expired

---

## Common Issues and Fixes

### Issue 1: Tool Not Registered

**Symptom:** Agent says "I don't have that capability"

**Debug:**
```python
registry = ToolRegistry()
print("summarize_channel" in registry.tools)  # False!
```

**Fix:** Add to ToolRegistry.__init__()

---

### Issue 2: MCP Function Import (Problem #13)

**Symptom:** `'FunctionTool' object is not callable`

**Debug:**
```python
from src.mcp_servers.slack_server import get_channel_messages
print(type(get_channel_messages))  # <class 'mcp.server.fastmcp.FunctionTool'>
```

**Fix:** Use Slack SDK directly, not MCP imports

---

### Issue 3: Missing Parameters

**Symptom:** `execute_tool() missing required argument`

**Debug:**
```python
tool = registry.tools["summarize_channel"]
print(tool["parameters"]["required"])  # ['channel_id', 'hours']
```

**Fix:** Provide all required parameters

---

### Issue 4: Tool Returns Exception Instead of Dict

**Symptom:** Agent crashes on tool execution

**Debug:**
```python
result = await registry.execute_tool("get_channel_messages", channel_id="INVALID")
# Raises exception instead of returning {"success": False, ...}
```

**Fix:** Wrap tool logic in try/except, return error dict

---

### Issue 5: Invalid JSON Schema

**Symptom:** Agent doesn't understand tool parameters

**Debug:**
```python
tool = registry.tools["summarize_channel"]
# Missing "parameters" key, or invalid schema
```

**Fix:** Follow JSON Schema specification exactly

---

## Debugging Checklist

When a tool isn't working:

1. [ ] Is tool registered? (`print(list(registry.tools.keys()))`)
2. [ ] Does tool have valid schema? (`print(tool["parameters"])`)
3. [ ] Can you execute tool directly? (`await registry.execute_tool(...)`)
4. [ ] Does function implementation work? (`await registry._tool_method(...)`)
5. [ ] Does tool return dict (not raise)? (Test with invalid input)
6. [ ] Can agent use the tool? (Test in orchestrator.chat())
7. [ ] Are API tokens valid? (Test with SDK client)
8. [ ] Check logs for errors (`grep ERROR logs/*.log`)

---

## Example: Full Debug Session

**Problem:** `summarize_channel` tool not working

```python
# Step 1: Check registration
from src.agent.tools import ToolRegistry
registry = ToolRegistry()
print("summarize_channel" in registry.tools)  # True ✓

# Step 2: Check schema
tool = registry.tools["summarize_channel"]
print(tool["parameters"])  # Valid schema ✓

# Step 3: Try direct execution
result = await registry.execute_tool("summarize_channel", channel_id="C123", hours=24)
print(result)  # Error: 'FunctionTool' object is not callable ✗

# Step 4: Check function implementation
# Look at _summarize_channel method
# Found: from src.mcp_servers.slack_server import summarize_channel
# This is the problem! (Problem #13)

# Step 5: Fix - use SDK directly
# Rewrite _summarize_channel to use AsyncWebClient

# Step 6: Test again
result = await registry.execute_tool("summarize_channel", channel_id="C123", hours=24)
print(result)  # {"success": True, "summary": "..."} ✓
```

**Result:** Tool fixed! Problem was MCP function import.

---

## Quick Reference: Test Commands

```bash
# Test tool registration
python -c "from src.agent.tools import ToolRegistry; r = ToolRegistry(); print(list(r.tools.keys()))"

# Test tool execution (requires async)
python -c "import asyncio; from src.agent.tools import ToolRegistry; r = ToolRegistry(); asyncio.run(r.execute_tool('summarize_channel', channel_id='C123', hours=24))"

# Test Slack token
python -c "import asyncio; from slack_sdk.web.async_client import AsyncWebClient; from config.settings import settings; asyncio.run(AsyncWebClient(token=settings.slack_bot_token).auth_test())"

# Check logs for tool errors
grep "Tool.*failed" logs/*.log
grep "execute_tool" logs/*.log
```

---

## Success Criteria

- Tool appears in registered tools list
- Tool has valid JSON schema
- Direct execution returns success dict
- Tool returns error dict on failure (doesn't raise)
- Agent can use tool successfully
- Logs show successful tool execution
