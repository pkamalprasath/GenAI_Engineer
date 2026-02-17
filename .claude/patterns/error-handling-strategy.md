# Pattern: Error Handling Strategy

## Layered Error Handling for Agent Systems

### Core Principle

**Tools return dicts, Services raise exceptions, Listeners handle both.**

---

## Layer 1: Tools (Agent-Facing)

### Rule: Tools Must NEVER Raise Exceptions

**Why:**
- Agent orchestrator expects dict responses
- Exceptions break the ReAct loop
- Agent can't reason about error types
- Entire conversation crashes

### ❌ Wrong: Raising Exceptions

```python
# In tools.py
async def _get_channel_messages(channel_id: str, hours: int):
    slack_client = AsyncWebClient(token=settings.slack_bot_token)
    response = await slack_client.conversations_history(channel=channel_id)

    # If API fails, exception propagates → breaks agent ❌
    return response["messages"]
```

**What happens:**
```
Agent: "Show me messages from #general"
  → Tool raises SlackApiError
  → Orchestrator crashes
  → User sees: "Internal error" ❌
```

---

### ✅ Right: Return Error Dicts

```python
# In tools.py
async def _get_channel_messages(channel_id: str, hours: int):
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

    except SlackApiError as e:
        logger.error("Slack API error: %s", e.response["error"])
        return {
            "success": False,
            "error": f"Slack API error: {e.response['error']}",
            "error_type": "slack_api_error"
        }

    except Exception as e:
        logger.error("Unexpected error fetching messages: %s", e)
        return {
            "success": False,
            "error": str(e),
            "error_type": "unexpected_error"
        }
```

**What happens:**
```
Agent: "Show me messages from #general"
  → Tool returns {"success": False, "error": "channel_not_found"}
  → Agent sees the error dict
  → Agent responds: "I couldn't access #general. Do you have the right channel?" ✅
```

---

### Standard Tool Response Format

```python
# Success response
{
    "success": True,
    "data": <actual_result>,
    "<result_key>": <result_value>,  # e.g., "messages", "summary", "issue_id"
    "count": <optional_count>
}

# Error response
{
    "success": False,
    "error": "<human_readable_message>",
    "error_type": "<error_category>",  # Optional: "api_error", "validation_error", etc.
    "details": <optional_additional_info>
}
```

**Examples:**

```python
# Successful message fetch
{
    "success": True,
    "messages": [...],
    "count": 42
}

# Successful summarization
{
    "success": True,
    "summary": "The team discussed...",
    "message_count": 42
}

# Channel not found
{
    "success": False,
    "error": "Channel not found or bot not invited",
    "error_type": "channel_not_found"
}

# API rate limited
{
    "success": False,
    "error": "Rate limit exceeded, try again in 60 seconds",
    "error_type": "rate_limit",
    "retry_after": 60
}
```

---

## Layer 2: Services (Business Logic)

### Rule: Services CAN Raise Exceptions

**Why:**
- Services are called by controlled code (slash commands, tools)
- Caller can handle exceptions appropriately
- Easier to write business logic without defensive returns

### Example: ReminderService

```python
# In src/services/reminder.py
class ReminderService:
    async def schedule_reminder(
        self,
        user_id: str,
        channel_id: str,
        message: str,
        deliver_at: datetime
    ) -> dict:
        """Schedule a reminder. Can raise exceptions."""

        # Validate input (raise on invalid)
        if deliver_at <= datetime.now(timezone.utc):
            raise ValueError("Reminder time must be in the future")

        # Generate ID
        reminder_id = str(uuid.uuid4())

        # Create reminder object
        reminder = {
            "id": reminder_id,
            "user_id": user_id,
            "channel_id": channel_id,
            "message": message,
            "deliver_at": deliver_at.isoformat(),
            "status": "pending"
        }

        # Save (could raise IOError)
        self._save_reminder(reminder)

        # Return success (or exception was raised)
        return {
            "success": True,
            "reminder_id": reminder_id,
            "deliver_at": deliver_at.isoformat()
        }
```

**Caller must handle:**

```python
# In tools.py (wraps service)
async def _schedule_reminder(user_id: str, channel_id: str, message: str, time_str: str):
    try:
        service = ReminderService()

        # Parse time (could raise ValueError)
        deliver_at = parse_time(time_str)

        # Call service (could raise ValueError, IOError)
        result = await service.schedule_reminder(
            user_id, channel_id, message, deliver_at
        )

        return result  # {"success": True, ...}

    except ValueError as e:
        # Invalid input
        return {
            "success": False,
            "error": f"Invalid input: {str(e)}",
            "error_type": "validation_error"
        }

    except Exception as e:
        # Unexpected error
        logger.error("Failed to schedule reminder: %s", e)
        return {
            "success": False,
            "error": "Failed to schedule reminder",
            "error_type": "unexpected_error"
        }
```

---

## Layer 3: Listeners (Slack Event Handlers)

### Rule: Listeners Handle All Errors, Always Respond to User

**Why:**
- Slack expects a response
- User shouldn't see cryptic errors
- Failed ack() causes Slack to retry (infinite loop)

### Example: Slash Command Handler

```python
# In src/slack/listeners/commands.py
@app.command("/bot-remind")
async def handle_remind(ack, command, client, logger):
    """Slash command: schedule a reminder."""

    # ALWAYS acknowledge first (3-second timeout)
    await ack()

    try:
        # Parse command text
        message, time_str = parse_remind_command(command["text"])

        # Call service (can raise exceptions)
        service = ReminderService()
        result = await service.schedule_reminder(
            user_id=command["user_id"],
            channel_id=command["channel_id"],
            message=message,
            deliver_at=parse_time(time_str)
        )

        # Success response
        if result["success"]:
            await client.chat_postMessage(
                channel=command["channel_id"],
                text=f"✅ Reminder set for {result['deliver_at']}"
            )
        else:
            # Service returned error dict
            await client.chat_postMessage(
                channel=command["channel_id"],
                text=f"❌ Failed to set reminder: {result['error']}"
            )

    except ValueError as e:
        # Invalid input (bad time format, etc.)
        logger.warning("Invalid reminder command: %s", e)
        await client.chat_postMessage(
            channel=command["channel_id"],
            text=f"❌ Invalid command: {str(e)}\n\nUsage: `/bot-remind [message] in [time]`"
        )

    except Exception as e:
        # Unexpected error
        logger.error("Reminder command failed: %s", e, exc_info=True)
        await client.chat_postMessage(
            channel=command["channel_id"],
            text="❌ An unexpected error occurred. Please try again later."
        )
```

**Critical rules:**
- Always `await ack()` first (within 3 seconds)
- Always send a response to user (success or error)
- Log all errors with appropriate level
- Never let exceptions propagate to Slack framework

---

## Layer 4: Scheduled Jobs (Background Tasks)

### Rule: Jobs Must NEVER Crash the Scheduler

**Why:**
- Unhandled exceptions can crash APScheduler
- All jobs stop running (reminders, indexing, cleanup)
- Bot becomes non-functional

### Example: Reminder Delivery Job

```python
# In src/app.py
async def _deliver_reminders():
    """Periodic job: deliver due reminders."""
    try:
        service = ReminderService()
        results = await service.execute_due_reminders()

        if results:
            logger.info("Reminder delivery cycle: %d processed", len(results))

    except Exception as e:
        # Log error but DON'T let it propagate
        logger.error("Reminder delivery failed: %s", e, exc_info=True)
        # Job will retry on next cycle

scheduler.add_job(_deliver_reminders, "interval", seconds=60, id="reminder_delivery")
```

**Pattern:**
```python
async def _job_function():
    """Periodic job: <description>."""
    try:
        # Do work
        result = await do_work()

        # Log success
        if result:
            logger.info("Job completed: %d items", len(result))

    except Exception as e:
        # CRITICAL: Catch ALL exceptions
        logger.error("Job failed: %s", e, exc_info=True)
        # Don't re-raise!
```

---

## Error Logging Levels

### When to Use Each Level

**DEBUG:** Detailed execution traces (not errors)
```python
logger.debug("Fetching messages from channel %s", channel_id)
logger.debug("Agent reasoning: %s", reasoning_trace)
```

**INFO:** Normal operations (successful events)
```python
logger.info("Reminder delivered to user %s", user_id)
logger.info("RAG indexing: 15 channels indexed")
logger.info("[OK] Scheduler started with 4 jobs")
```

**WARNING:** Non-fatal issues (degraded service, retries)
```python
logger.warning("GitHub token may be invalid")
logger.warning("Failed to index channel %s, will retry", channel_id)
logger.warning("Rate limit approaching (80% used)")
```

**ERROR:** Failures that need attention
```python
logger.error("Slack API error: %s", error_message)
logger.error("Failed to deliver reminder %s: %s", reminder_id, e)
logger.error("Database connection lost: %s", e, exc_info=True)
```

**CRITICAL:** System-level failures (rarely used)
```python
logger.critical("Unable to start Slack bot: %s", e)
logger.critical("All API keys invalid, bot non-functional")
```

---

## Complete Flow Example

### User Request: "Summarize #general from last 24 hours"

**Layer 1: Tool (summarize_channel)**
```python
async def _summarize_channel(channel_id: str, hours: int = 24):
    try:
        # Call service
        service = SummarizationService()
        summary = await service.summarize_messages(channel_id, hours)

        # Return success dict
        return {
            "success": True,
            "summary": summary,
            "channel_id": channel_id
        }

    except Exception as e:
        logger.error("Summarization tool failed: %s", e)
        # Return error dict (don't raise!)
        return {
            "success": False,
            "error": f"Failed to summarize channel: {str(e)}"
        }
```

**Layer 2: Service (SummarizationService)**
```python
async def summarize_messages(self, channel_id: str, hours: int):
    # Fetch messages (can raise SlackApiError)
    messages = await self._fetch_messages(channel_id, hours)

    # Validate (can raise ValueError)
    if not messages:
        raise ValueError("No messages found in timeframe")

    # Call Claude API (can raise AnthropicError)
    summary = await self._call_claude(messages)

    # Return result (or exception was raised)
    return summary
```

**Layer 3: Orchestrator**
```python
async def chat(self, conversation_id: str, user_message: str):
    try:
        # Agent decides to use summarize_channel tool
        tool_result = await self.tool_registry.execute_tool(
            "summarize_channel",
            channel_id="C123",
            hours=24
        )

        # Tool returns dict (never raises)
        if tool_result["success"]:
            # Use summary in response
            summary = tool_result["summary"]
            return f"Here's the summary: {summary}"
        else:
            # Tool returned error dict
            return f"I couldn't summarize the channel: {tool_result['error']}"

    except Exception as e:
        # Unexpected error (shouldn't happen if tools follow pattern)
        logger.error("Orchestrator error: %s", e, exc_info=True)
        return "I encountered an unexpected error. Please try again."
```

---

## Testing Error Handling

### Test Tools Return Error Dicts

```python
@pytest.mark.asyncio
async def test_tool_returns_error_dict_on_failure():
    """Tools should return error dicts, not raise exceptions."""

    # Mock Slack client to raise error
    with patch("slack_sdk.web.async_client.AsyncWebClient") as mock_client:
        mock_client.return_value.conversations_history.side_effect = SlackApiError(
            message="channel_not_found",
            response={"error": "channel_not_found"}
        )

        # Call tool
        registry = ToolRegistry()
        result = await registry.execute_tool("get_channel_messages", channel_id="INVALID")

        # Should return error dict, not raise
        assert result["success"] is False
        assert "error" in result
        assert "channel_not_found" in result["error"]
```

---

## Summary Checklist

### Tools
- [ ] Wrap all logic in try/except
- [ ] Return success dict on success: `{"success": True, ...}`
- [ ] Return error dict on failure: `{"success": False, "error": "..."}`
- [ ] NEVER raise exceptions
- [ ] Log errors with logger.error()

### Services
- [ ] Can raise exceptions (ValueError, custom exceptions)
- [ ] Document which exceptions can be raised
- [ ] Return success dicts when successful
- [ ] Caller handles exceptions

### Listeners (Slash Commands, Events)
- [ ] Always ack() within 3 seconds
- [ ] Wrap all logic in try/except
- [ ] Always respond to user (success or error)
- [ ] Log all errors
- [ ] Never let exceptions propagate to Slack

### Scheduled Jobs
- [ ] Wrap entire job in try/except
- [ ] Log errors but don't re-raise
- [ ] Let job retry on next cycle
- [ ] Never crash the scheduler

**Result:** Robust error handling at every layer, user always gets feedback, system never crashes.
