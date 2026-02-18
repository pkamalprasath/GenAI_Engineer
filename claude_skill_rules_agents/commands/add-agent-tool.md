# Skill: Add Agent Tool

## Purpose
Add a new tool to the agent's ToolRegistry so it can invoke the functionality.

## When to Use
- After creating a new service
- When agent needs to call existing functionality
- When bridging Slack operations to agent

## Prerequisites
- Service/method already implemented
- Clear understanding of tool's parameters
- JSON schema knowledge for input_schema

## Steps

### Step 1: Define Tool in ToolRegistry
```python
# In src/agent/tools.py, inside ToolRegistry.__init__:

self.tools["tool_name"] = self._tool_name
self._definitions.append({
    "name": "tool_name",
    "description": "Clear description of what this tool does",
    "input_schema": {
        "type": "object",
        "properties": {
            "param1": {
                "type": "string",
                "description": "What param1 is for"
            },
            "param2": {
                "type": "integer",
                "description": "What param2 is for (default: 24)"
            },
        },
        "required": ["param1"],  # Only required params here
    },
})
```

### Step 2: Implement Tool Method
```python
# In src/agent/tools.py, in the appropriate section:

async def _tool_name(self, param1: str, param2: int = 24) -> Dict[str, Any]:
    """
    Brief description of what the tool does.

    This tool chains multiple operations:
      1. Operation A
      2. Operation B
      3. Return structured result
    """
    try:
        result = await some_service.method(param1, param2)
        return {
            "success": True,
            "data": result,
        }
    except Exception as e:
        return {"error": str(e)}  # Return error as dict — NEVER raise
```

## Patterns

### Pattern 1: Simple Delegation to Service
```python
async def _detect_issues(self, channel_id: str, hours: int = 24) -> Any:
    """Detect issues in channel messages."""
    messages = await self._fetch_channel_messages(channel_id, hours)
    service = self._get_issue_service()
    return await service.detect_issues(messages, channel_name=channel_id)
```

### Pattern 2: Chained Operations (Fetch + Process)
```python
async def _summarize_channel(self, channel_id: str, hours: int = 24) -> Dict[str, Any]:
    """Fetch messages and summarize them."""
    from slack_sdk.web.async_client import AsyncWebClient
    from config.settings import settings
    from src.services.summarization import SummarizationService

    try:
        slack_client = AsyncWebClient(token=settings.slack_bot_token)
        response = await slack_client.conversations_history(...)
        messages = response.get("messages", [])

        if not messages:
            return {"summary": "No messages found", "message_count": 0}

        service = SummarizationService()
        summary = await service.summarize_messages(messages, channel_name)

        return {
            "summary": summary,
            "channel": channel_name,
            "message_count": len(messages),
        }
    except Exception as e:
        return {"error": f"Failed: {str(e)}"}
```

### Pattern 3: Conditional Tool (GitHub, Notion)
```python
# In __init__, only register if integration is configured:
if self.mcp_registry.github is not None:
    self.tools["create_github_issue"] = self._create_github_issue
    self._definitions.append({"name": "create_github_issue", ...})

async def _create_github_issue(self, repo, title, body, labels=None):
    if self.mcp_registry.github is None:
        return {"error": "GitHub integration not configured"}
    return await self.mcp_registry.github.create_issue(repo, title, body, labels=labels)
```

### Pattern 4: Lazy Service Initialization
```python
def _get_issue_service(self):
    """Lazy initialization with caching."""
    if not hasattr(self, '_issue_service'):
        from src.services.issue_detection import IssueDetectionService
        self._issue_service = IssueDetectionService()
    return self._issue_service
```

## Critical Rules

### DO:
1. **Return dicts with error field** — Not exceptions: `return {"error": "Something failed"}`
2. **Use Slack SDK directly** — Not MCP-decorated functions
3. **Provide default values** for optional parameters
4. **Include description** in both tool definition and method docstring
5. **Put tools in logical sections** — Slack tools together, GitHub tools together

### DON'T:
1. **Never import MCP-decorated functions** — `from src.mcp_servers.X import fn` breaks with `'FunctionTool' object is not callable`
2. **Never raise exceptions** — Return error dicts instead
3. **Never forget to register** the method in `__init__`
4. **Never use ambiguous names** — Be specific (`summarize_channel` not `summarize`)

## Input Schema Types

```python
# String
"param": {"type": "string", "description": "..."}

# Integer with Default
"hours": {"type": "integer", "description": "Hours to look back (default: 24)"}

# Array
"labels": {"type": "array", "items": {"type": "string"}, "description": "List of labels"}

# Enum (Restricted Values)
"state": {"type": "string", "enum": ["open", "closed", "all"], "description": "Issue state"}
```

## Testing

After adding the tool:

```python
# 1. Check registration
registry = ToolRegistry()
definitions = registry.get_tool_definitions()
tool_names = [t["name"] for t in definitions]
assert "your_tool" in tool_names

# 2. Test execution
result = await registry.execute_tool("your_tool", param1="value")
assert isinstance(result, dict)
```

## Success Criteria
- Tool appears in agent's tool definitions
- Tool executes without exceptions
- Tool returns proper dict structure
- Tool handles errors gracefully (returns error dict, doesn't raise)
