# Rules: Slack Bot Development

## Critical Rules Learned from Production Issues

### Rule 1: Never Import FastMCP-Decorated Functions Directly

**Context:** Problem #13 - All agent tools were broken due to importing MCP functions

**WRONG:**
```python
# In tools.py
from src.mcp_servers.slack_server import get_channel_messages

async def _get_channel_messages(channel_id: str, hours: int):
    # FAILS: 'FunctionTool' object is not callable
    result = await get_channel_messages(channel_id, hours)
```

**RIGHT:**
```python
# In tools.py
from slack_sdk.web.async_client import AsyncWebClient
from config.settings import settings

async def _get_channel_messages(channel_id: str, hours: int):
    slack_client = AsyncWebClient(token=settings.slack_bot_token)
    response = await slack_client.conversations_history(
        channel=channel_id,
        limit=100
    )
    return response.get("messages", [])
```

**Why:**
- FastMCP's `@mcp.tool()` decorator wraps functions in `FunctionTool` objects
- These objects are NOT directly callable
- MCP servers should only expose tools to external MCP clients
- Internal code should use the underlying SDK directly

**Exception:**
- If you need MCP functionality, use the MCP client protocol, not direct imports

---

### Rule 2: Share Stateful Instances via Dependency Injection

**Context:** Problem #5 - Separate MemoryManager instances caused zero conversation history

**WRONG:**
```python
# In orchestrator.py
class Orchestrator:
    def __init__(self):
        self.context_builder = ContextBuilder()  # Creates its own MemoryManager
        self.memory_manager = MemoryManager()     # Different instance!
```

**RIGHT:**
```python
# In orchestrator.py
class Orchestrator:
    def __init__(self):
        self.memory_manager = MemoryManager()
        self.context_builder = ContextBuilder(memory_manager=self.memory_manager)

# In context_builder.py
class ContextBuilder:
    def __init__(self, memory_manager: MemoryManager = None):
        self.memory_manager = memory_manager or MemoryManager()
```

**Why:**
- Stateful components (MemoryManager, database connections, caches) must be shared
- Creating separate instances breaks state synchronization
- Dependency injection makes testing easier

**Applies to:**
- MemoryManager
- Database connections
- Redis clients
- Vector store clients
- Any component with mutable state

---

### Rule 3: Always Configure Scheduler Jobs for Periodic Tasks

**Context:** Problems #7, #10 - Reminders never delivered, RAG never indexed

**WRONG:**
```python
# Having ReminderService.execute_due_reminders() but never calling it
# Having RAG indexer but never running it
```

**RIGHT:**
```python
# In src/app.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

# Reminder delivery
async def _deliver_reminders():
    try:
        results = await reminder_service.execute_due_reminders()
        if results:
            logger.info("Reminder delivery: %d processed", len(results))
    except Exception as e:
        logger.error("Reminder delivery failed: %s", e)

scheduler.add_job(_deliver_reminders, "interval", seconds=60, id="reminder_delivery")

# RAG indexing
scheduler.add_job(_index_channels, "interval", hours=2, id="rag_indexing")

scheduler.start()
logger.info("[OK] Scheduler started with 2 jobs")
```

**Why:**
- Services don't self-execute - you must call them
- Periodic tasks require a scheduler (APScheduler, Celery, etc.)
- Manual execution doesn't scale

**Requirements:**
- Wrap job logic in try/except to prevent scheduler crashes
- Use unique job IDs
- Log job completion/failure
- Make scheduler startup non-fatal

---

### Rule 4: Slash Commands Should Use Services, Not Duplicate Logic

**Context:** Problem #1 - /bot-remind bypassed ReminderService

**WRONG:**
```python
# In commands.py
@app.command("/bot-remind")
async def handle_remind(ack, command, client):
    await ack()
    # Directly use Slack API
    await client.chat_scheduleMessage(
        channel=command["channel_id"],
        text=message,
        post_at=timestamp
    )
    # ReminderService never knows about this!
```

**RIGHT:**
```python
# In commands.py
from src.services.reminder import ReminderService

@app.command("/bot-remind")
async def handle_remind(ack, command, client):
    await ack()

    service = ReminderService()
    result = await service.schedule_reminder(
        user_id=command["user_id"],
        channel_id=command["channel_id"],
        message=message,
        deliver_at=timestamp
    )

    if result["success"]:
        await client.chat_postMessage(...)
```

**Why:**
- Single source of truth for business logic
- Services handle persistence, validation, logging
- Agent and slash commands use the same code path
- Easier to test and maintain

**Pattern:**
1. Slash command → thin handler (parse input, ack)
2. Service layer → business logic
3. Return result → format response

---

### Rule 5: Tools Must Return Dicts, Never Raise Exceptions

**Context:** All tools needed error handling for agent reliability

**WRONG:**
```python
async def _get_channel_messages(channel_id: str):
    response = await slack_client.conversations_history(channel=channel_id)
    # Raises exception if API fails - breaks agent execution
    return response["messages"]
```

**RIGHT:**
```python
async def _get_channel_messages(channel_id: str):
    try:
        response = await slack_client.conversations_history(channel=channel_id)
        messages = response.get("messages", [])
        return {"success": True, "messages": messages, "count": len(messages)}
    except Exception as e:
        logger.error("Failed to fetch messages: %s", e)
        return {"success": False, "error": str(e), "messages": []}
```

**Why:**
- Agent orchestrator expects dicts, not exceptions
- Exceptions break ReAct loop
- Error dicts allow agent to retry or adapt strategy

**Pattern:**
```python
try:
    result = await operation()
    return {"success": True, "data": result}
except Exception as e:
    logger.error("Tool failed: %s", e)
    return {"success": False, "error": str(e)}
```

---

### Rule 6: Register All Tools in ToolRegistry

**Context:** Problem #9 - Missing critical tools (summarize_channel, list_channels, etc.)

**WRONG:**
```python
# Tool exists in tools.py but not registered
async def _summarize_channel(channel_id: str, hours: int):
    # Implementation exists but agent can't use it
    pass
```

**RIGHT:**
```python
# In ToolRegistry.__init__()
self.tools["summarize_channel"] = {
    "function": self._summarize_channel,
    "description": "Generate AI summary of channel messages",
    "parameters": {
        "type": "object",
        "properties": {
            "channel_id": {"type": "string", "description": "Channel ID"},
            "hours": {"type": "integer", "description": "Hours to look back"}
        },
        "required": ["channel_id"]
    }
}
```

**Why:**
- Unregistered tools are invisible to the agent
- Agent uses tool list to decide capabilities
- Missing tools = degraded user experience

**Checklist:**
1. Implement tool method
2. Add to ToolRegistry.tools dict
3. Provide JSON schema
4. Write clear description
5. Test with agent

---

### Rule 7: Validate Environment Variables at Startup

**Context:** Problem #8 - Invalid GitHub tokens cause silent failures

**WRONG:**
```python
# In settings.py
github_token: Optional[str] = None  # No validation
```

**RIGHT:**
```python
# In settings.py
import warnings

@field_validator("github_token")
@classmethod
def validate_github_token(cls, v: Optional[str]) -> Optional[str]:
    if v:
        valid_prefixes = ("ghp_", "github_pat_", "gho_", "ghu_", "ghs_")
        if not v.startswith(valid_prefixes):
            warnings.warn(
                f"GitHub token may be invalid (should start with {valid_prefixes})",
                UserWarning
            )
    return v
```

**Why:**
- Catch configuration errors at startup, not runtime
- Invalid tokens cause confusing failures later
- Warnings guide users to fix issues

**Validate:**
- Token format (prefixes)
- Required vs optional keys
- Mutually exclusive configs
- URL formats

---

### Rule 8: Log Scheduler Job Status on Startup

**Context:** Problem #7/#10 - Users couldn't tell if jobs were running

**WRONG:**
```python
scheduler = AsyncIOScheduler()
scheduler.add_job(_job1, "interval", seconds=60)
scheduler.add_job(_job2, "interval", hours=2)
scheduler.start()
# Silent - no indication jobs are running
```

**RIGHT:**
```python
scheduler = AsyncIOScheduler()
scheduler.add_job(_deliver_reminders, "interval", seconds=60, id="reminder_delivery")
scheduler.add_job(_index_channels, "interval", hours=2, id="rag_indexing")
scheduler.add_job(_cleanup_reminders, "cron", day_of_week="sun", hour=0, id="cleanup")
scheduler.add_job(_heartbeat, "interval", minutes=5, id="heartbeat")
scheduler.start()

logger.info("[OK] Scheduler started with 4 jobs: reminders (60s), RAG (2h), cleanup (weekly), heartbeat (5m)")
```

**Why:**
- Users need confirmation jobs are running
- Debugging is easier with clear startup logs
- Format shows job names and frequencies

**Log Format:**
```
[OK] Scheduler started with N jobs: job1 (freq1), job2 (freq2), ...
```

---

### Rule 9: Use Conditional Tool Registration for Optional Integrations

**Context:** GitHub and Notion tools should only register if tokens are configured

**WRONG:**
```python
# Always register, fail at runtime if token missing
self.tools["create_github_issue"] = {...}
```

**RIGHT:**
```python
# In ToolRegistry.__init__()
if settings.github_token:
    self.tools["create_github_issue"] = {...}
    self.tools["list_github_issues"] = {...}
    logger.info("GitHub tools registered")

if settings.notion_token:
    self.tools["create_notion_page"] = {...}
    self.tools["search_notion"] = {...}
    logger.info("Notion tools registered")
```

**Why:**
- Clearer agent capabilities (doesn't offer tools it can't use)
- Startup logs show what's enabled
- Reduces confusing error messages

---

### Rule 10: Implement Cleanup Jobs for Growing Data Stores

**Context:** Problem #11 - reminders.json grows indefinitely

**WRONG:**
```python
# Only add/execute reminders, never remove old ones
```

**RIGHT:**
```python
# In ReminderService
async def cleanup_old_reminders(self, days: int = 30) -> int:
    """Remove delivered/cancelled reminders older than N days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    # Remove old reminders
    return removed_count

# In app.py scheduler
async def _cleanup_reminders():
    try:
        removed = await reminder_service.cleanup_old_reminders(days=30)
        if removed > 0:
            logger.info("Reminder cleanup: %d old reminders removed", removed)
    except Exception as e:
        logger.error("Reminder cleanup failed: %s", e)

scheduler.add_job(_cleanup_reminders, "cron", day_of_week="sun", hour=0, id="cleanup")
```

**Why:**
- Prevents unbounded file/database growth
- Keeps JSON files manageable
- Improves performance (less data to scan)

**Apply to:**
- Reminders (delivered/cancelled)
- Logs (rotate and purge)
- Temporary files
- Cache entries

---

## Summary Checklist

When building a Slack bot with agent capabilities:

- [ ] Use Slack SDK directly, not MCP-decorated imports
- [ ] Share stateful instances (MemoryManager, DB connections)
- [ ] Configure scheduler for all periodic tasks
- [ ] Slash commands use service layer (don't duplicate logic)
- [ ] Tools return dicts (never raise exceptions)
- [ ] All tools registered in ToolRegistry
- [ ] Validate environment variables at startup
- [ ] Log scheduler status on startup
- [ ] Conditionally register optional tools
- [ ] Implement cleanup jobs for growing data

**Result:** Robust, maintainable Slack bot that actually works in production.
