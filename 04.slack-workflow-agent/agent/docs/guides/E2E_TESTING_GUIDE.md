# End-to-End Testing Guide — Slack Bot Assistant

> Complete guide for testing the bot with a real Slack workspace.
> Follow this checklist to verify all functionalities work in production.

---

## Prerequisites

### 1. Slack Workspace Setup

**Required Slack App Configuration:**

1. **Create a Slack App** at https://api.slack.com/apps
   - Choose "From scratch"
   - Name: "Slack Bot Assistant" (or your preferred name)
   - Select your development workspace

2. **OAuth & Permissions** — Add Bot Token Scopes:
   ```
   channels:history       # Read messages in public channels
   channels:read          # View basic channel info
   chat:write            # Send messages
   chat:write.public     # Send messages to channels bot isn't in
   commands              # Receive slash command events
   groups:history        # Read messages in private channels
   groups:read           # View basic private channel info
   im:history            # Read DM messages
   im:read               # View DM info
   im:write              # Send DMs
   reactions:write       # Add emoji reactions
   users:read            # View user info
   ```

3. **Install to Workspace**
   - Click "Install to Workspace"
   - Authorize the app
   - Copy the **Bot User OAuth Token** (starts with `xoxb-`)

4. **Socket Mode** (for development)
   - Enable Socket Mode
   - Generate an **App-Level Token** with `connections:write` scope
   - Copy the token (starts with `xapp-`)

5. **Slash Commands** — Create commands:
   - `/bot-help` → Request URL: (not needed for Socket Mode)
   - `/bot-status` → Request URL: (not needed for Socket Mode)
   - `/bot-summarize` → Request URL: (not needed for Socket Mode)
   - `/bot-remind` → Request URL: (not needed for Socket Mode)

6. **Event Subscriptions** — Subscribe to bot events:
   - `message.im` — Direct messages
   - `app_mention` — @mentions in channels

7. **Signing Secret**
   - Go to "Basic Information"
   - Copy the **Signing Secret**

---

### 2. Update `.env` File

```bash
# Slack Configuration (REQUIRED)
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_APP_TOKEN=xapp-your-app-token-here
SLACK_SIGNING_SECRET=your-signing-secret-here

# AI Configuration (REQUIRED)
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Optional Integrations
OPENAI_API_KEY=sk-your-openai-key-here        # For embeddings
GITHUB_TOKEN=ghp_your-github-pat-here         # For GitHub integration
NOTION_TOKEN=secret_your-notion-token-here    # For Notion integration

# Environment
ENVIRONMENT=development
LOG_LEVEL=DEBUG

# Database
DATABASE_URL=sqlite:///./bot.db

# Memory & RAG
MEMORY_STORE_PATH=./memory_store
CHROMA_PERSIST_DIRECTORY=./chroma_db
RAG_INDEXING_FREQUENCY=7200  # 2 hours
RAG_MESSAGE_LIMIT=200

# Rate Limiting
RATE_LIMIT_PER_USER=10
RATE_LIMIT_PER_CHANNEL=30
```

---

## Running the Bot

### Start the Bot

```bash
# From project root
cd d:\AI\KrishNaik_Academy\Coding\Vizuara\open_claw_proj

# Activate virtual environment (if using one)
# python -m venv venv
# venv\Scripts\activate  # Windows
# source venv/bin/activate  # Mac/Linux

# Install dependencies (if not already installed)
poetry install
# OR
pip install -r requirements.txt

# Run the bot
python src/main.py
```

**Expected Output:**
```
[INFO] ================================================================================
[INFO] Slack Bot Assistant Starting
[INFO] ================================================================================
[INFO] Environment: development
[INFO] Log Level: DEBUG
[INFO] ================================================================================
[INFO] [OK] Auth middleware registered
[INFO] [OK] Rate limit middleware registered
[INFO] [OK] Error handler middleware registered
[INFO] [OK] Message listener registered
[INFO] [OK] Command listeners registered (4 commands)
[INFO] [OK] Mention listener registered
[INFO] [OK] Global error handler registered
[INFO] [OK] Scheduler started with 4 jobs: reminders (60s), RAG indexing (7200s), cleanup (weekly), heartbeat (5m)
[INFO] [OK] Slack Bolt app created successfully
[INFO]   Bot Token: xoxb-****
[INFO]   Environment: development
[INFO] ⚡️ Bolt app is running in Socket Mode!
```

**If you see errors:**
- Check `.env` file has correct tokens
- Verify Slack app is installed to workspace
- Check internet connection

---

## E2E Test Checklist

### Phase 1: Basic Connectivity ✅

#### Test 1.1: Bot Responds to DM
**Steps:**
1. In Slack, send a DM to the bot: `Hello!`
2. Bot should respond within a few seconds

**Expected:**
- Bot replies with a greeting
- Response appears in a thread
- Hourglass emoji (⏳) appears while processing
- Checkmark emoji (✅) appears when done

**Check Logs:**
```
[INFO] Received DM from user U123456
[INFO] Executing tool: ...
[INFO] Posted message to C123456
```

**❌ If fails:**
- Check bot has `im:history` and `im:write` scopes
- Check `src/slack/listeners/messages.py` for errors
- Verify tokens in `.env` are correct

---

#### Test 1.2: Bot Responds to @mention
**Steps:**
1. In a public channel, invite the bot: `/invite @YourBot`
2. Mention the bot: `@YourBot what can you do?`

**Expected:**
- Bot replies in a thread
- Eyes emoji (👀) while processing
- Checkmark emoji (✅) when done

**Check Logs:**
```
[INFO] Mentioned in channel C123456 by user U123456
```

**❌ If fails:**
- Check bot has `app_mention` event subscription
- Check bot is in the channel
- Check `src/slack/listeners/mentions.py`

---

### Phase 2: Slash Commands ✅

#### Test 2.1: `/bot-help`
**Steps:**
1. Type `/bot-help` in any channel

**Expected Output:**
```
🤖 Slack Bot Assistant - Available Commands

/bot-help - Show this help message
/bot-status - Show bot status and system info
/bot-summarize #channel [hours] - Summarize channel messages
/bot-remind [message] in [time] - Set a reminder

Examples:
  /bot-summarize #general 24
  /bot-remind Review PR in 30 minutes
```

**❌ If fails:**
- Check slash command is registered in Slack app settings
- Check `src/slack/listeners/commands.py:handle_help_command`

---

#### Test 2.2: `/bot-status`
**Steps:**
1. Type `/bot-status` in any channel

**Expected Output:**
```
✅ Slack Bot Status

Bot Status: Online
Version: 0.1.0
Environment: development
Uptime: 5 minutes

Integrations:
✅ Slack API: Connected
✅ Claude AI: Available
✅ Memory System: Active
✅ RAG System: Active
❌ GitHub: Not configured
❌ Notion: Not configured

Last Health Check: Just now
```

**❌ If fails:**
- Check `src/slack/listeners/commands.py:handle_status_command`

---

#### Test 2.3: `/bot-summarize`
**Steps:**
1. In a channel with messages, type: `/bot-summarize #general 2`
   (where #general is a channel with at least a few messages)

**Expected:**
- Processing message appears
- After 5-10 seconds, summary appears
- Summary includes:
  - Main topics discussed
  - Key decisions or action items
  - Important questions raised

**Check Logs:**
```
[INFO] Summarize command for channel C123456, hours=2
[INFO] Retrieved 47 messages from C123456
[INFO] Summarizing 47 messages from general
[INFO] Summary generated successfully
```

**❌ If fails:**
- Check `ANTHROPIC_API_KEY` is valid
- Check channel has messages in the time window
- Check `src/services/summarization.py` logs
- Verify bot has `channels:history` scope

---

#### Test 2.4: `/bot-remind`
**Steps:**
1. Type: `/bot-remind Check deployment in 2 minutes`
2. Wait 2 minutes

**Expected:**
- Immediate confirmation: `Got it! I'll remind you in 2 minutes: "Check deployment"`
- Includes reminder ID for cancellation
- After 2 minutes, reminder appears as a message

**Check Logs:**
```
[INFO] Remind command from user U123456: Check deployment in 2 minutes
[INFO] Reminder a1b2c3d4 scheduled for user U123456 at 1234567890
[INFO] Reminder delivery cycle: 1 processed
[INFO] Delivered reminder a1b2c3d4 to C123456
```

**❌ If fails:**
- Check `src/services/reminder.py` logs
- Verify scheduler is running (check startup logs)
- Check `reminders.json` file exists in `memory_store/`

---

### Phase 3: Agent Tool Execution ✅

#### Test 3.1: Summarize Channel (via agent)
**Steps:**
1. Send DM to bot: `Please summarize #general from the last 6 hours`

**Expected:**
- Bot uses `summarize_channel` tool
- Returns summary with message count and timeframe

**Check Logs:**
```
[INFO] Executing tool: summarize_channel
[INFO] Retrieved 123 messages from C123456
[INFO] Summarizing 123 messages from general
[INFO] Tool summarize_channel completed successfully
```

**❌ If fails:**
- Check tool is registered: look for "summarize_channel" in startup logs
- Check `src/agent/tools.py:_summarize_channel`
- Verify no import errors from MCP functions

---

#### Test 3.2: List Channels
**Steps:**
1. Send DM to bot: `What channels are you in?`

**Expected:**
- Bot uses `list_channels` tool
- Lists all channels bot is a member of
- Shows channel names (not just IDs)

**Check Logs:**
```
[INFO] Executing tool: list_channels
[INFO] Retrieved 15 channels
```

**❌ If fails:**
- Check `channels:read` scope
- Check `src/agent/tools.py:_list_channels`

---

#### Test 3.3: Schedule Reminder (via agent)
**Steps:**
1. Send DM: `Remind me to check the logs in 3 minutes`

**Expected:**
- Bot uses `schedule_reminder` tool
- Confirms with reminder ID
- After 3 minutes, reminder delivered

**Check Logs:**
```
[INFO] Executing tool: schedule_reminder
[INFO] Reminder xyz123 scheduled for user U123456 at 1234567890
```

---

#### Test 3.4: Detect Issues
**Steps:**
1. Create a test channel with some bug-related messages:
   - "The login page is broken on mobile Safari"
   - "API returns 500 errors when uploading files"
2. Send DM to bot: `Analyze #test-bugs for issues`

**Expected:**
- Bot uses `detect_issues` tool
- Returns list of detected issues with:
  - Title
  - Description
  - Severity (critical/high/medium/low)
  - Suggested labels

**Check Logs:**
```
[INFO] Executing tool: detect_issues
[INFO] Analyzing 5 messages from #test-bugs for issues
[INFO] Detected 2 issues in #test-bugs
```

---

#### Test 3.5: GitHub Integration (if configured)
**Steps:**
1. Send DM: `Create a GitHub issue in owner/repo: "Test issue" with body "Testing from Slack bot"`

**Expected:**
- Bot uses `create_github_issue` tool
- Returns GitHub issue URL
- Issue appears in GitHub repository

**Check Logs:**
```
[INFO] Executing tool: create_github_issue
[INFO] Created GitHub issue #42 in owner/repo
```

**❌ If fails:**
- Verify `GITHUB_TOKEN` in `.env`
- Check token has `repo` scope
- Check repository exists and token has access

---

### Phase 4: Memory & Context ✅

#### Test 4.1: Conversation Memory
**Steps:**
1. Send DM to bot: `My name is Alice`
2. Wait for response
3. Send: `What's my name?`

**Expected:**
- Bot remembers "Alice" from previous message
- Response references earlier conversation

**Check Logs:**
```
[INFO] Storing interaction for user U123456, channel C123456
[INFO] Retrieved 2 conversation history messages
```

**❌ If fails:**
- This would indicate Problem #5 wasn't fully fixed
- Check `src/memory/manager.py` and `src/agent/context_builder.py`
- Verify shared MemoryManager instance

---

#### Test 4.2: Long-term Memory Persistence
**Steps:**
1. Send DM: `Remember that I prefer daily standup summaries`
2. **Restart the bot**
3. Send DM: `What do you remember about my preferences?`

**Expected:**
- Bot retrieves preference from `memory_store/MEMORY.md`
- Response includes "daily standup summaries"

**Check Files:**
```bash
# Check memory files created
ls memory_store/
# Should see:
# MEMORY.md
# memory/YYYY-MM-DD.md
# USER.md
```

---

### Phase 5: Background Jobs ✅

#### Test 5.1: Heartbeat Logs
**Steps:**
1. Let bot run for 10+ minutes
2. Check logs for heartbeat entries

**Expected:**
- Heartbeat log every 5 minutes
- Shows uptime and service status

**Check Logs:**
```
[INFO] Heartbeat: {'uptime_hours': 0.17, 'reminder_service': 'ok', 'slack_connection': 'ok'}
[INFO] Heartbeat: {'uptime_hours': 0.25, 'reminder_service': 'ok', 'slack_connection': 'ok'}
```

**❌ If fails:**
- Check APScheduler started (see startup logs)
- Check `src/app.py` scheduler configuration

---

#### Test 5.2: Reminder Delivery (60s cycle)
**Steps:**
1. Schedule a reminder: `/bot-remind Test in 1 minute`
2. Watch logs for delivery

**Expected:**
- After 60-120 seconds, reminder delivered
- Log shows "Reminder delivery cycle: 1 processed"

**Check Logs:**
```
[INFO] Reminder delivery cycle: 1 processed
[INFO] Delivered reminder abc123 to C123456
```

**❌ If fails:**
- Scheduler not running
- Check `reminders.json` has pending reminder
- Check `src/services/reminder.py:execute_due_reminders`

---

#### Test 5.3: RAG Indexing (2h cycle)
**Steps:**
1. Let bot run for 2+ hours
2. Check logs for indexing activity

**Expected:**
- After 2 hours, indexing job runs
- Logs show channels being indexed

**Check Logs:**
```
[INFO] RAG indexing cycle: 5 channels indexed
[INFO] Indexed channel C123456 (45 messages)
```

**Check Files:**
```bash
# ChromaDB files should be created
ls chroma_db/
# Should see database files
```

**❌ If fails:**
- Wait for 2-hour mark (or adjust `RAG_INDEXING_FREQUENCY` in `.env`)
- Check `src/rag/indexer.py` for errors
- Verify `OPENAI_API_KEY` if using OpenAI embeddings

---

#### Test 5.4: RAG Retrieval (after indexing)
**Steps:**
1. After RAG indexing completes
2. Send DM: `What did we discuss about the deployment yesterday?`
   (assuming "deployment" was mentioned in indexed messages)

**Expected:**
- Bot's response references specific past messages
- Context includes semantic matches from vector store

**Check Logs:**
```
[INFO] Retrieved 3 relevant contexts
[DEBUG] RAG retrieval returned 3 results
```

---

### Phase 6: Error Handling & Edge Cases ✅

#### Test 6.1: Rate Limiting
**Steps:**
1. Rapidly send 15 messages to bot (exceeds 10/min limit)

**Expected:**
- First 10 messages processed
- Messages 11-15 get rate limit response
- After 1 minute, limit resets

**Check Logs:**
```
[WARNING] Rate limit exceeded for user U123456
```

---

#### Test 6.2: Invalid Commands
**Steps:**
1. Try: `/bot-summarize invalid-channel 999`
2. Try: `/bot-remind malformed text`

**Expected:**
- Helpful error messages
- No crashes or exceptions
- Bot remains responsive

---

#### Test 6.3: Long Messages
**Steps:**
1. Send a very long message (2000+ characters)

**Expected:**
- Bot handles gracefully
- May truncate or summarize
- No crashes

---

## Troubleshooting

### Bot Not Responding

**Check:**
1. Bot is running (`python src/main.py` shows no errors)
2. Socket Mode is enabled in Slack app
3. Bot is invited to channel (for @mentions)
4. `.env` tokens are correct

**Logs to check:**
```
[ERROR] Failed to receive WebSocket message
[ERROR] Slack API error: invalid_auth
```

---

### Tools Not Working

**Check:**
1. Tool is registered in startup logs
2. No import errors from MCP functions
3. Slack SDK can access Slack API

**Logs to check:**
```
[ERROR] Tool execution raised: ...
[ERROR] 'FunctionTool' object is not callable
```

If you see "FunctionTool not callable", Problem #13 wasn't fully fixed.

---

### Scheduler Not Running

**Check:**
1. APScheduler installed: `pip list | grep -i apscheduler`
2. No errors in startup logs
3. Heartbeat logs appear every 5 minutes

**Logs to check:**
```
[ERROR] Failed to start scheduler: ...
[WARNING] Failed to start reminder scheduler: ...
```

---

### Memory Not Persisting

**Check:**
1. `memory_store/` directory exists and is writable
2. Files are being created:
   - `memory_store/MEMORY.md`
   - `memory_store/memory/YYYY-MM-DD.md`

**Logs to check:**
```
[ERROR] Failed to save memory: ...
[WARNING] Memory file not found: ...
```

---

## Performance Benchmarks

### Expected Response Times

| Operation | Expected Time | Notes |
|-----------|---------------|-------|
| Simple DM reply | 1-3 seconds | No tool calls |
| Summarization | 5-15 seconds | Depends on message count |
| Issue detection | 10-30 seconds | Depends on message count |
| List channels | <1 second | Slack API call |
| GitHub issue creation | 2-5 seconds | GitHub API call |

---

## Success Criteria

### ✅ All Tests Must Pass

- [ ] Bot responds to DMs
- [ ] Bot responds to @mentions
- [ ] All 4 slash commands work
- [ ] Agent tools execute successfully
- [ ] Summarization works
- [ ] Reminders deliver on time
- [ ] Memory persists across restarts
- [ ] RAG indexing completes (after 2h)
- [ ] All 4 scheduler jobs running
- [ ] No crashes or exceptions
- [ ] Error handling works gracefully

### 📊 Metrics to Track

- **Uptime:** Should run for 24+ hours without crashing
- **Memory usage:** Should stay below 500MB
- **Response latency:** <5 seconds for simple queries
- **Scheduler reliability:** All jobs run on schedule
- **Error rate:** <1% of requests fail

---

## Next Steps After E2E Testing

### If All Tests Pass ✅
1. Review logs for any warnings
2. Optimize any slow operations
3. Consider production deployment
4. Set up external monitoring (Datadog, Sentry)

### If Tests Fail ❌
1. Check PROBLEMS.md for known issues
2. Run integration tests: `python test_integration.py`
3. Enable DEBUG logging
4. Review error stack traces
5. Check Slack app configuration

---

## Production Readiness Checklist

- [ ] All E2E tests passing
- [ ] No errors in 24h run
- [ ] Memory usage stable
- [ ] Logs clean (no warnings)
- [ ] Rate limiting working
- [ ] Error handling tested
- [ ] Documentation complete
- [ ] Monitoring set up
- [ ] Backup strategy defined
- [ ] Rollback plan ready

---

**Good luck with testing! 🚀**

If you encounter issues not covered here, check:
- [PROBLEMS.md](PROBLEMS.md) for known issues
- [TEST_RESULTS.md](TEST_RESULTS.md) for integration test results
- [FIXES_SUMMARY.md](FIXES_SUMMARY.md) for all fixes applied
