# Skill: Add Scheduler Job

## Purpose
Add a periodic background job to APScheduler for automated tasks like reminders, indexing, cleanup, or health checks.

## When to Use
- Need periodic execution (every X seconds/minutes/hours)
- Need cron-style scheduling (specific days/times)
- Have a method that should run automatically
- Want monitoring/heartbeat functionality

## Prerequisites
- APScheduler installed: `pip install apscheduler`
- Async method to be called periodically
- Clear understanding of desired schedule

## Steps

### Step 1: Import APScheduler (if not already done)
```python
# In src/app.py, in create_app() function:
from apscheduler.schedulers.asyncio import AsyncIOScheduler
```

### Step 2: Create Scheduler Instance
```python
# After middleware/listener registration, before app return:
try:
    scheduler = AsyncIOScheduler()

    # Jobs will be added here

    scheduler.start()
    logger.info("[OK] Scheduler started with X jobs")
except Exception as e:
    logger.warning("Failed to start scheduler: %s", e)
```

### Step 3: Add Job
```python
# Inside the try block:

async def _job_function():
    """Periodic job: brief description."""
    try:
        # Call your service/method
        result = await service.method()
        if result:
            logger.info("Job completed: %d items processed", len(result))
    except Exception as e:
        logger.error("Job failed: %s", e)

# Schedule the job
scheduler.add_job(
    _job_function,
    "interval",  # OR "cron"
    seconds=60,  # For interval
    id="job_unique_id"
)
```

## Job Types

### Type 1: Interval-Based (Every N Seconds)
```python
# Every 60 seconds
scheduler.add_job(_deliver_reminders, "interval", seconds=60, id="reminder_delivery")

# Every 5 minutes
scheduler.add_job(_heartbeat, "interval", minutes=5, id="heartbeat")

# Every 2 hours
scheduler.add_job(_index_rag, "interval", hours=2, id="rag_indexing")
```

### Type 2: Cron-Based (Specific Times)
```python
# Every Sunday at midnight
scheduler.add_job(_cleanup, "cron", day_of_week="sun", hour=0, id="cleanup")

# Every day at 9 AM
scheduler.add_job(_daily_report, "cron", hour=9, minute=0, id="daily_report")

# First of every month at midnight
scheduler.add_job(_monthly, "cron", day=1, hour=0, id="monthly_task")
```

### Type 3: Dynamic Interval from Settings
```python
# Use configuration value
scheduler.add_job(
    _index_channels,
    "interval",
    seconds=settings.rag_indexing_frequency,  # e.g., 7200
    id="rag_indexing"
)
```

## Patterns

### Pattern 1: Reminder Delivery (Service Call)
```python
from src.services.reminder import ReminderService

reminder_service = ReminderService()

async def _deliver_reminders():
    """Periodic job: check for due reminders and deliver them."""
    try:
        results = await reminder_service.execute_due_reminders()
        if results:
            logger.info("Reminder delivery cycle: %d processed", len(results))
    except Exception as e:
        logger.error("Reminder delivery failed: %s", e)

scheduler.add_job(_deliver_reminders, "interval", seconds=60, id="reminder_delivery")
```

### Pattern 2: RAG Indexing (Multi-Step)
```python
async def _index_channels():
    """Periodic job: index recent messages from all channels."""
    try:
        from src.rag.indexer import ChannelIndexer
        indexer = ChannelIndexer()

        # Get list of channels
        from slack_sdk.web.async_client import AsyncWebClient
        slack_client = AsyncWebClient(token=settings.slack_bot_token)
        response = await slack_client.conversations_list(types="public_channel,private_channel")
        channels = response.get("channels", [])

        # Index each channel
        indexed_count = 0
        for channel in channels:
            channel_id = channel.get("id")
            if channel_id:
                try:
                    await indexer.index_channel(channel_id)
                    indexed_count += 1
                except Exception as e:
                    logger.warning("Failed to index channel %s: %s", channel_id, e)

        logger.info("RAG indexing cycle: %d channels indexed", indexed_count)
    except Exception as e:
        logger.error("RAG indexing failed: %s", e)

scheduler.add_job(_index_channels, "interval", seconds=settings.rag_indexing_frequency, id="rag_indexing")
```

### Pattern 3: Cleanup (Conditional Execution)
```python
async def _cleanup_reminders():
    """Periodic job: remove old delivered/cancelled reminders."""
    try:
        removed = await reminder_service.cleanup_old_reminders(days=30)
        if removed > 0:
            logger.info("Reminder cleanup: %d old reminders removed", removed)
    except Exception as e:
        logger.error("Reminder cleanup failed: %s", e)

scheduler.add_job(_cleanup_reminders, "cron", day_of_week="sun", hour=0, id="reminder_cleanup")
```

### Pattern 4: Heartbeat (Status Logging)
```python
import time
bot_start_time = time.time()

async def _heartbeat():
    """Periodic job: log health status and uptime."""
    try:
        uptime_seconds = int(time.time() - bot_start_time)
        uptime_hours = uptime_seconds / 3600

        health_status = {
            "uptime_hours": round(uptime_hours, 2),
            "reminder_service": "ok",
            "slack_connection": "ok",
        }

        logger.info("Heartbeat: %s", health_status)
    except Exception as e:
        logger.error("Heartbeat failed: %s", e)

scheduler.add_job(_heartbeat, "interval", minutes=5, id="heartbeat")
```

## Critical Rules

### ✅ DO:
1. **Wrap job logic in try/except** — Don't let job failures crash scheduler
   ```python
   async def _job():
       try:
           await do_work()
       except Exception as e:
           logger.error("Job failed: %s", e)
   ```

2. **Log job completion** — For monitoring and debugging
   ```python
   logger.info("Job completed: %d items processed", count)
   ```

3. **Use unique job IDs** — Prevents duplicate jobs
   ```python
   id="reminder_delivery"  # Unique identifier
   ```

4. **Make scheduler start non-fatal** — Bot can still function without jobs
   ```python
   try:
       scheduler.start()
   except Exception as e:
       logger.warning("Failed to start scheduler: %s", e)
   ```

5. **Log scheduler status on startup** — Confirm jobs are running
   ```python
   logger.info("[OK] Scheduler started with 4 jobs: reminders (60s), RAG (2h), cleanup (weekly), heartbeat (5m)")
   ```

### ❌ DON'T:
1. **Don't let exceptions propagate** — Wrap in try/except

2. **Don't block the event loop** — Use async/await properly

3. **Don't run CPU-intensive tasks** — Offload to thread pool if needed

4. **Don't forget to call scheduler.start()** — Jobs won't run otherwise

5. **Don't use mutable state without locks** — Could cause race conditions

## Common Intervals

| Frequency | Config | Use Case |
|-----------|--------|----------|
| 1 minute | `seconds=60` | Reminder delivery |
| 5 minutes | `minutes=5` | Heartbeat/health checks |
| 1 hour | `hours=1` | Hourly reports |
| 2 hours | `hours=2` | RAG indexing |
| Daily 9am | `cron, hour=9, minute=0` | Daily summaries |
| Weekly Sun | `cron, day_of_week="sun", hour=0` | Weekly cleanup |

## Testing

### Verify Scheduler Started
```python
# Check startup logs:
[INFO] [OK] Scheduler started with 4 jobs: reminders (60s), RAG (2h), cleanup (weekly), heartbeat (5m)
```

### Verify Job Runs
```python
# For interval jobs, wait for the interval and check logs:
[INFO] Reminder delivery cycle: 1 processed
[INFO] Heartbeat: {'uptime_hours': 0.08, 'reminder_service': 'ok'}

# For cron jobs, wait for the scheduled time or test manually:
await _cleanup_reminders()  # Manual test
```

### Force Job Execution (Testing)
```python
# In a separate test script:
scheduler.get_job("reminder_delivery").func()  # Call directly
```

## Example: Complete Job Addition

```python
# In src/app.py, create_app() function, before return statement:

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from src.services.reminder import ReminderService

    scheduler = AsyncIOScheduler()
    reminder_service = ReminderService()

    # Job 1: Reminder delivery
    async def _deliver_reminders():
        try:
            results = await reminder_service.execute_due_reminders()
            if results:
                logger.info("Reminder delivery: %d processed", len(results))
        except Exception as e:
            logger.error("Reminder delivery failed: %s", e)

    scheduler.add_job(_deliver_reminders, "interval", seconds=60, id="reminder_delivery")

    # Job 2: Heartbeat
    import time
    bot_start_time = time.time()

    async def _heartbeat():
        try:
            uptime = round((time.time() - bot_start_time) / 3600, 2)
            logger.info("Heartbeat: uptime=%sh", uptime)
        except Exception as e:
            logger.error("Heartbeat failed: %s", e)

    scheduler.add_job(_heartbeat, "interval", minutes=5, id="heartbeat")

    # Start scheduler
    scheduler.start()
    logger.info("[OK] Scheduler started with 2 jobs")

except Exception as e:
    logger.warning("Failed to start scheduler: %s", e)
```

## Success Criteria
- Scheduler starts without errors
- Startup logs confirm number of jobs
- Job executes on schedule (check logs)
- Job failures don't crash scheduler
- Bot continues functioning if scheduler fails
