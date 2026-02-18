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

## Steps

### Step 1: Import APScheduler
```python
# In src/app.py, in create_app() function:
from apscheduler.schedulers.asyncio import AsyncIOScheduler
```

### Step 2: Create Scheduler + Add Jobs + Start
```python
try:
    scheduler = AsyncIOScheduler()

    async def _job_function():
        """Periodic job: brief description."""
        try:
            result = await service.method()
            if result:
                logger.info("Job completed: %d items processed", len(result))
        except Exception as e:
            logger.error("Job failed: %s", e)  # Never re-raise!

    scheduler.add_job(_job_function, "interval", seconds=60, id="job_unique_id")
    scheduler.start()
    logger.info("[OK] Scheduler started with 1 jobs: job_function (60s)")

except Exception as e:
    logger.warning("Failed to start scheduler: %s", e)  # Non-fatal
```

## Job Types

### Interval-Based
```python
scheduler.add_job(_deliver_reminders, "interval", seconds=60, id="reminder_delivery")
scheduler.add_job(_heartbeat,         "interval", minutes=5,  id="heartbeat")
scheduler.add_job(_index_rag,         "interval", hours=2,    id="rag_indexing")
```

### Cron-Based
```python
scheduler.add_job(_cleanup,       "cron", day_of_week="sun", hour=0,          id="cleanup")
scheduler.add_job(_daily_report,  "cron", hour=9, minute=0,                   id="daily_report")
scheduler.add_job(_monthly,       "cron", day=1, hour=0,                      id="monthly_task")
```

### Dynamic from Settings
```python
scheduler.add_job(_index_channels, "interval", seconds=settings.rag_indexing_frequency, id="rag_indexing")
```

## Job Patterns

### Pattern 1: Service Call (Reminders)
```python
reminder_service = ReminderService()

async def _deliver_reminders():
    try:
        results = await reminder_service.execute_due_reminders()
        if results:
            logger.info("Reminder delivery: %d processed", len(results))
    except Exception as e:
        logger.error("Reminder delivery failed: %s", e)

scheduler.add_job(_deliver_reminders, "interval", seconds=60, id="reminder_delivery")
```

### Pattern 2: Multi-Step (RAG Indexing)
```python
async def _index_channels():
    try:
        indexer = ChannelIndexer()
        slack_client = AsyncWebClient(token=settings.slack_bot_token)
        response = await slack_client.conversations_list(types="public_channel,private_channel")
        channels = response.get("channels", [])

        indexed_count = 0
        for channel in channels:
            channel_id = channel.get("id")
            if channel_id:
                try:
                    await indexer.index_channel(channel_id)
                    indexed_count += 1
                except Exception as e:
                    logger.warning("Failed to index channel %s: %s", channel_id, e)

        logger.info("RAG indexing: %d channels indexed", indexed_count)
    except Exception as e:
        logger.error("RAG indexing failed: %s", e)

scheduler.add_job(_index_channels, "interval", seconds=settings.rag_indexing_frequency, id="rag_indexing")
```

### Pattern 3: Cleanup (Conditional Execution)
```python
async def _cleanup_reminders():
    try:
        removed = await reminder_service.cleanup_old_reminders(days=30)
        if removed > 0:
            logger.info("Reminder cleanup: %d old reminders removed", removed)
    except Exception as e:
        logger.error("Reminder cleanup failed: %s", e)

scheduler.add_job(_cleanup_reminders, "cron", day_of_week="sun", hour=0, id="reminder_cleanup")
```

### Pattern 4: Heartbeat
```python
import time
bot_start_time = time.time()

async def _heartbeat():
    try:
        uptime_hours = round((time.time() - bot_start_time) / 3600, 2)
        logger.info("Heartbeat: uptime=%sh", uptime_hours)
    except Exception as e:
        logger.error("Heartbeat failed: %s", e)

scheduler.add_job(_heartbeat, "interval", minutes=5, id="heartbeat")
```

## Critical Rules

### DO:
1. **Wrap all job logic in try/except** — Uncaught exceptions can crash APScheduler, stopping ALL jobs
2. **Log job completion** — For monitoring: `logger.info("Job completed: %d items", count)`
3. **Use unique job IDs** — Prevents duplicate jobs on restart
4. **Make scheduler start non-fatal** — Bot should function even if scheduler fails
5. **Log scheduler startup** — `logger.info("[OK] Scheduler started with N jobs: ...")`

### DON'T:
1. **Never let exceptions propagate out of job functions** — Wrap in try/except
2. **Never block the event loop** — Use async/await properly
3. **Never forget to call scheduler.start()**
4. **Never use mutable state without locks** — Race conditions in periodic jobs

## Common Intervals Reference

| Frequency | Config | Use Case |
|---|---|---|
| 1 minute | `seconds=60` | Reminder delivery |
| 5 minutes | `minutes=5` | Heartbeat/health checks |
| 2 hours | `hours=2` | RAG indexing |
| Daily 9am | `cron, hour=9, minute=0` | Daily summaries |
| Weekly Sun | `cron, day_of_week="sun", hour=0` | Weekly cleanup |

## Success Criteria
- Scheduler starts without errors
- Startup logs confirm number of jobs and their frequency
- Job executes on schedule (visible in logs)
- Job failures don't crash scheduler (other jobs keep running)
- Bot continues functioning if scheduler fails to start
