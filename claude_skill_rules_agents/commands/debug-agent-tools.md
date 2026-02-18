# Skill: Debug Agent Tools

## Purpose
Systematically debug agent tools when they're not working. 7-step process covering registration, schema, execution, error handling, and API tokens.

## When to Use
- Agent says "I don't have that capability"
- Tool execution fails silently
- Agent returns wrong results from a tool
- Tool appears registered but doesn't work

## 7-Step Debugging Process

### Step 1: Verify Tool Registration

```python
from src.agent.tools import ToolRegistry

registry = ToolRegistry()
print("Registered tools:", list(registry.tools.keys()))
# Expected: ['get_channel_messages', 'post_message', 'summarize_channel', ...]
```

If tool is missing → add to `ToolRegistry.__init__()`, check conditional registration logic.

---

### Step 2: Verify Tool Schema

```python
import json
tool = registry.tools.get("summarize_channel")
print(json.dumps(tool, indent=2, default=str))
```

Common schema issues:
- Missing `"parameters"` key
- Invalid JSON schema syntax
- Type mismatches (`"string"` vs `"integer"`)
- Required fields not listed in `"required"` array

---

### Step 3: Test Direct Tool Execution

```python
import asyncio
from src.agent.tools import ToolRegistry

async def test_tool():
    registry = ToolRegistry()
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

---

### Step 4: Check Tool Function Implementation

```python
async def test_function():
    registry = ToolRegistry()
    result = await registry._summarize_channel(channel_id="C123ABC", hours=24)
    print("Direct function result:", result)

asyncio.run(test_function())
```

**CRITICAL — Problem #13: `'FunctionTool' object is not callable`**

This means you imported an MCP-decorated function directly:

```python
# WRONG
from src.mcp_servers.slack_server import get_channel_messages
result = await get_channel_messages(channel_id, hours)  # FAILS!

# RIGHT — Use SDK directly
from slack_sdk.web.async_client import AsyncWebClient
slack_client = AsyncWebClient(token=settings.slack_bot_token)
response = await slack_client.conversations_history(channel=channel_id)
```

---

### Step 5: Verify Tool Returns Dict (Never Raises)

```python
# Test with invalid input — should return error dict, NOT raise exception
result = await registry.execute_tool("get_channel_messages", channel_id="INVALID")
print(result)
# Expected: {"success": False, "error": "..."}
# NOT: Exception raised
```

If tool raises: wrap logic in `try/except`, return `{"success": False, "error": str(e)}`.

---

### Step 6: Test in Agent Context

```python
from src.agent.orchestrator import Orchestrator

async def test_agent_tool_usage():
    orchestrator = Orchestrator()
    response = await orchestrator.chat(
        conversation_id="test-123",
        user_message="Summarize #general from the last 24 hours"
    )
    print("Agent response:", response)

asyncio.run(test_agent_tool_usage())
```

Check logs for:
```
[DEBUG] Executing tool: summarize_channel
[DEBUG] Tool parameters: {"channel_id": "C123", "hours": 24}
[DEBUG] Tool result: {"success": True, "summary": "..."}
```

If agent doesn't use tool → tool description unclear, or tool not in system prompt.

---

### Step 7: Check API Tokens and Permissions

```python
# Test Slack token
from slack_sdk.web.async_client import AsyncWebClient
from config.settings import settings

async def test_slack():
    client = AsyncWebClient(token=settings.slack_bot_token)
    response = await client.auth_test()
    print("Valid:", response["ok"], "Bot:", response["user"])

asyncio.run(test_slack())
```

```python
# Test Anthropic token
from anthropic import AsyncAnthropic

async def test_anthropic():
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    response = await client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=10,
        messages=[{"role": "user", "content": "Hi"}]
    )
    print("Anthropic token valid")

asyncio.run(test_anthropic())
```

---

## Common Issues Reference

| Issue | Symptom | Fix |
|---|---|---|
| Tool not registered | Agent says "I don't have that capability" | Add to `ToolRegistry.__init__()` |
| MCP import (Problem #13) | `'FunctionTool' object is not callable` | Use Slack SDK directly, not MCP imports |
| Missing parameters | `execute_tool() missing required argument` | Check `required` list in schema |
| Tool raises instead of returns | Agent crashes on tool execution | Wrap in `try/except`, return error dict |
| Invalid JSON schema | Agent doesn't understand parameters | Follow JSON Schema spec exactly |

## Debugging Checklist

- [ ] Is tool registered? (`list(registry.tools.keys())`)
- [ ] Does tool have valid schema? (`print(tool["parameters"])`)
- [ ] Can you execute tool directly? (`await registry.execute_tool(...)`)
- [ ] Does function implementation work? (`await registry._tool_method(...)`)
- [ ] Does tool return dict on failure? (Test with invalid input)
- [ ] Can agent use the tool? (Test in `orchestrator.chat()`)
- [ ] Are API tokens valid? (Test with SDK client)

## Quick Reference: CLI Test Commands

```bash
# Check tool registration
python -c "from src.agent.tools import ToolRegistry; r = ToolRegistry(); print(list(r.tools.keys()))"

# Check Slack token
python -c "import asyncio; from slack_sdk.web.async_client import AsyncWebClient; from config.settings import settings; c = AsyncWebClient(token=settings.slack_bot_token); asyncio.run(c.auth_test())"

# Check logs for errors
grep "Tool.*failed" logs/*.log
grep "FunctionTool" logs/*.log
```
