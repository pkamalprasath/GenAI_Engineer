# Pattern: Error Handling Strategy

## Core Principle

**Tools return dicts. Services raise exceptions. Listeners handle both.**

---

## Layer 1: Tools (Agent-Facing) — NEVER Raise Exceptions

The agent orchestrator expects dict responses. Exceptions break the ReAct loop — the entire conversation crashes.

```python
# WRONG
async def _get_channel_messages(channel_id: str, hours: int):
    response = await slack_client.conversations_history(channel=channel_id)
    return response["messages"]  # Raises if API fails → breaks agent!

# RIGHT
async def _get_channel_messages(channel_id: str, hours: int):
    try:
        slack_client = AsyncWebClient(token=settings.slack_bot_token)
        response = await slack_client.conversations_history(channel=channel_id, limit=100)
        messages = response.get("messages", [])
        return {"success": True, "messages": messages, "count": len(messages)}
    except SlackApiError as e:
        logger.error("Slack API error: %s", e.response["error"])
        return {"success": False, "error": f"Slack API error: {e.response['error']}", "error_type": "slack_api_error"}
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return {"success": False, "error": str(e), "error_type": "unexpected_error"}
```

### Standard Tool Response Format

```python
# Success
{"success": True, "data": <result>, "<result_key>": <value>, "count": <optional>}

# Error
{"success": False, "error": "<human_readable_message>", "error_type": "<category>"}
```

---

## Layer 2: Services (Business Logic) — CAN Raise Exceptions

Services are called by controlled code (tools, slash commands). Caller handles exceptions.

```python
class ReminderService:
    async def schedule_reminder(self, user_id, channel_id, message, deliver_at) -> dict:
        if deliver_at <= datetime.now(timezone.utc):
            raise ValueError("Reminder time must be in the future")  # OK to raise here

        reminder_id = str(uuid.uuid4())
        self._save_reminder({...})  # Could raise IOError

        return {"success": True, "reminder_id": reminder_id}
```

Caller (tool) wraps and converts exceptions to dicts:

```python
async def _schedule_reminder(self, ...):
    try:
        result = await service.schedule_reminder(...)
        return result  # {"success": True, ...}
    except ValueError as e:
        return {"success": False, "error": f"Invalid input: {str(e)}", "error_type": "validation_error"}
    except Exception as e:
        logger.error("Failed: %s", e)
        return {"success": False, "error": "Failed to schedule reminder"}
```

---

## Layer 3: Listeners (Slack Event Handlers) — Always ack(), Always Respond

```python
@app.command("/bot-remind")
async def handle_remind(ack, command, client, logger):
    await ack()  # ALWAYS first — Slack 3-second timeout

    try:
        message, time_str = parse_remind_command(command["text"])
        result = await service.schedule_reminder(...)

        if result["success"]:
            await client.chat_postMessage(channel=command["channel_id"], text="Reminder set!")
        else:
            await client.chat_postMessage(channel=command["channel_id"], text=f"Failed: {result['error']}")

    except ValueError as e:
        await client.chat_postMessage(channel=command["channel_id"], text=f"Invalid command: {str(e)}")
    except Exception as e:
        logger.error("Command failed: %s", e, exc_info=True)
        await client.chat_postMessage(channel=command["channel_id"], text="An unexpected error occurred.")
```

Critical rules:
- Always `await ack()` first (within 3 seconds)
- Always send a response to user (success OR error)
- Log all errors with appropriate level
- Never let exceptions propagate to Slack framework

---

## Layer 4: Scheduled Jobs — Never Crash the Scheduler

Unhandled exceptions stop ALL scheduler jobs.

```python
async def _deliver_reminders():
    try:
        service = ReminderService()
        results = await service.execute_due_reminders()
        if results:
            logger.info("Reminder delivery: %d processed", len(results))
    except Exception as e:
        logger.error("Reminder delivery failed: %s", e, exc_info=True)
        # DO NOT re-raise — job retries on next cycle

scheduler.add_job(_deliver_reminders, "interval", seconds=60)
```

---

## Logging Levels

```python
logger.debug("Fetching messages from channel %s", channel_id)   # Execution traces
logger.info("Reminder delivered to user %s", user_id)           # Normal success
logger.warning("GitHub token may be invalid")                    # Non-fatal issue
logger.error("Slack API error: %s", error_message)               # Failure needing attention
logger.critical("Unable to start Slack bot: %s", e)             # System-level failure
```

---

## Checklist

### Tools
- [ ] All logic in `try/except`
- [ ] Return `{"success": True, ...}` on success
- [ ] Return `{"success": False, "error": "..."}` on failure
- [ ] NEVER raise exceptions
- [ ] Log errors with `logger.error()`

### Services
- [ ] Can raise exceptions (document which ones)
- [ ] Caller always handles exceptions

### Listeners
- [ ] Always `ack()` within 3 seconds
- [ ] Wrap in `try/except`
- [ ] Always respond to user
- [ ] Never let exceptions propagate to Slack

### Scheduled Jobs
- [ ] Wrap entire job in `try/except`
- [ ] Log errors but don't re-raise
- [ ] Let job retry on next cycle
