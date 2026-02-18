# Rules: Slack Bot Development

## 10 Critical Rules (learned from production issues)

---

### Rule 1: Never Import FastMCP-Decorated Functions Directly

```python
# WRONG
from src.mcp_servers.slack_server import get_channel_messages
result = await get_channel_messages(channel_id, hours)  # 'FunctionTool' not callable!

# RIGHT
from slack_sdk.web.async_client import AsyncWebClient
slack_client = AsyncWebClient(token=settings.slack_bot_token)
response = await slack_client.conversations_history(channel=channel_id, limit=100)
```

**See:** [rules/fastmcp-integration.md](fastmcp-integration.md)

---

### Rule 2: Share Stateful Instances via Dependency Injection

```python
# WRONG — Two separate MemoryManager instances → conversation memory broken
class Orchestrator:
    def __init__(self):
        self.context_builder = ContextBuilder()  # Creates its own MemoryManager
        self.memory_manager = MemoryManager()    # Different instance!

# RIGHT
class Orchestrator:
    def __init__(self):
        self.memory_manager = MemoryManager()
        self.context_builder = ContextBuilder(memory_manager=self.memory_manager)
```

Applies to: MemoryManager, DB connections, Redis clients, vector stores, schedulers.

---

### Rule 3: Always Configure Scheduler Jobs for Periodic Tasks

```python
# WRONG — ReminderService.execute_due_reminders() exists but is never called!

# RIGHT
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

async def _deliver_reminders():
    try:
        results = await reminder_service.execute_due_reminders()
        if results:
            logger.info("Reminder delivery: %d processed", len(results))
    except Exception as e:
        logger.error("Reminder delivery failed: %s", e)

scheduler.add_job(_deliver_reminders, "interval", seconds=60, id="reminder_delivery")
scheduler.start()
logger.info("[OK] Scheduler started with 1 jobs")
```

---

### Rule 4: Slash Commands Use Services — Never Duplicate Logic

```python
# WRONG — Slash command bypasses ReminderService, sends directly to Slack
@app.command("/bot-remind")
async def handle_remind(ack, command, client):
    await ack()
    await client.chat_scheduleMessage(...)  # ReminderService never knows!

# RIGHT
@app.command("/bot-remind")
async def handle_remind(ack, command, client):
    await ack()
    service = ReminderService()
    result = await service.schedule_reminder(...)
    if result["success"]:
        await client.chat_postMessage(channel=command["channel_id"], text="Reminder set!")
```

Pattern: slash command → thin handler (parse, ack) → service layer → format response.

---

### Rule 5: Tools Return Dicts, Never Raise Exceptions

```python
# WRONG — Exception breaks agent's ReAct loop
async def _get_channel_messages(channel_id: str):
    response = await slack_client.conversations_history(channel=channel_id)
    return response["messages"]  # Raises if API fails!

# RIGHT
async def _get_channel_messages(channel_id: str):
    try:
        response = await slack_client.conversations_history(channel=channel_id)
        messages = response.get("messages", [])
        return {"success": True, "messages": messages, "count": len(messages)}
    except Exception as e:
        logger.error("Tool failed: %s", e)
        return {"success": False, "error": str(e)}
```

---

### Rule 6: Register All Tools in ToolRegistry

```python
# WRONG — Service exists but agent can't use it (no tool registered)
class SummarizationService:
    async def summarize_messages(self, messages, channel): ...
# Agent says "I don't have that capability"

# RIGHT
# In ToolRegistry.__init__():
self.tools["summarize_channel"] = self._summarize_channel
self._definitions.append({
    "name": "summarize_channel",
    "description": "Generate AI summary of recent channel messages",
    "input_schema": {
        "type": "object",
        "properties": {
            "channel_id": {"type": "string", "description": "Slack channel ID"},
            "hours": {"type": "integer", "description": "Hours to look back (default: 24)"}
        },
        "required": ["channel_id"]
    }
})
```

---

### Rule 7: Validate Environment Variables at Startup

```python
# In settings.py
@field_validator("github_token")
@classmethod
def validate_github_token(cls, v: Optional[str]) -> Optional[str]:
    if v:
        valid_prefixes = ("ghp_", "github_pat_", "gho_", "ghu_", "ghs_")
        if not v.startswith(valid_prefixes):
            warnings.warn(f"GitHub token may be invalid (expected prefix: {valid_prefixes})", UserWarning)
    return v
```

Catch configuration errors at startup, not at runtime when a user triggers a feature.

---

### Rule 8: Log Scheduler Job Status on Startup

```python
# WRONG — Silent start (impossible to tell if jobs are running)
scheduler.start()

# RIGHT — Explicit startup log
scheduler.start()
logger.info("[OK] Scheduler started with 4 jobs: reminders (60s), RAG (2h), cleanup (weekly), heartbeat (5m)")
```

---

### Rule 9: Use Conditional Tool Registration for Optional Integrations

```python
# In ToolRegistry.__init__():

if settings.github_token:
    self.tools["create_github_issue"] = self._create_github_issue
    self._definitions.append({"name": "create_github_issue", ...})
    logger.info("GitHub tools registered")

if settings.notion_token:
    self.tools["search_notion"] = self._search_notion
    self._definitions.append({"name": "search_notion", ...})
    logger.info("Notion tools registered")
```

Agent only offers tools it can actually use. Startup logs show what's enabled.

---

### Rule 10: Implement Cleanup Jobs for Growing Data Stores

```python
# WRONG — reminders.json grows indefinitely (delivered reminders never removed)

# RIGHT
class ReminderService:
    async def cleanup_old_reminders(self, days: int = 30) -> int:
        """Remove delivered/cancelled reminders older than N days."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        # Remove old entries and return count removed

# In scheduler:
async def _cleanup_reminders():
    try:
        removed = await reminder_service.cleanup_old_reminders(days=30)
        if removed > 0:
            logger.info("Cleanup: %d old reminders removed", removed)
    except Exception as e:
        logger.error("Cleanup failed: %s", e)

scheduler.add_job(_cleanup_reminders, "cron", day_of_week="sun", hour=0, id="cleanup")
```

---

## Summary Checklist

When building a Slack bot with agent capabilities:

- [ ] Use Slack SDK directly (not MCP-decorated imports)
- [ ] Share stateful instances (MemoryManager, DB connections)
- [ ] Configure scheduler for ALL periodic tasks
- [ ] Slash commands delegate to service layer
- [ ] Tools return dicts (never raise exceptions)
- [ ] All tools registered in ToolRegistry with JSON schema
- [ ] Validate environment variables at startup
- [ ] Log scheduler status on startup
- [ ] Conditionally register optional tools (GitHub, Notion)
- [ ] Implement cleanup jobs for growing data stores
