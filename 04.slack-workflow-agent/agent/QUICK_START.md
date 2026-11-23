# Quick Start: Slack Workflow Agent

> Setting up a Slack app and running the agent against a test workspace.

---

## Prerequisites

- Python 3.11+
- A Slack workspace where you can create apps (a test workspace is best)
- An Anthropic API key

---

## Step 1: Create Slack App

1. Go to https://api.slack.com/apps
2. Click **"Create New App"** → **"From scratch"**
3. Name it, for example, **"Slack Workflow Agent"**
4. Select your workspace
5. Click **"Create App"**

---

## Step 2: Configure Slack App

### OAuth & Permissions

1. Go to **"OAuth & Permissions"** (left sidebar)
2. Scroll to **"Scopes"** → **"Bot Token Scopes"**
3. Click **"Add an OAuth Scope"** and add these:
   ```
   channels:history
   channels:read
   chat:write
   chat:write.public
   commands
   im:history
   im:write
   reactions:write
   users:read
   app_mentions:read
   ```
4. Scroll up and click **"Install to Workspace"**
5. Click **"Allow"**
6. **Copy the Bot User OAuth Token** (starts with `xoxb-`)

### Socket Mode (for development)

1. Go to **"Socket Mode"** (left sidebar)
2. Toggle **"Enable Socket Mode"** → ON
3. Give it a name: "socket-connection"
4. Scopes: Check **"connections:write"**
5. Click **"Generate"**
6. **Copy the App-Level Token** (starts with `xapp-`)

### Event Subscriptions

1. Go to **"Event Subscriptions"** (left sidebar)
2. Toggle **"Enable Events"** → ON
3. Under **"Subscribe to bot events"**, add:
   - `message.im` (Direct messages)
   - `app_mention` (@mentions)
4. Click **"Save Changes"**

### Slash Commands

1. Go to **"Slash Commands"** (left sidebar)
2. Click **"Create New Command"** for each:
   - `/bot-help` (Description: "Show help")
   - `/bot-status` (Description: "Show bot status")
   - `/bot-summarize` (Description: "Summarize channel")
   - `/bot-remind` (Description: "Set a reminder")
3. Request URL can be blank (Socket Mode handles it)

### Get Signing Secret

1. Go to **"Basic Information"** (left sidebar)
2. Scroll to **"App Credentials"**
3. **Copy the Signing Secret**

---

## Step 3: Install Dependencies

```bash
cd 04.slack-workflow-agent/agent

# Using Poetry
poetry install

# OR using pip (Python 3.11+, in a virtual environment)
pip install -e .
```

---

## Step 4: Configure Environment

Copy the template, then edit `.env`:

```bash
cp .env.example .env
```


```bash
# REQUIRED - Slack credentials
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_APP_TOKEN=xapp-your-app-token-here
SLACK_SIGNING_SECRET=your-signing-secret-here

# REQUIRED - AI
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key-here

# Optional: enables the GitHub and Notion tools
GITHUB_TOKEN=ghp_your-github-token-here
NOTION_TOKEN=secret_your-notion-token-here

# Environment
ENVIRONMENT=development
LOG_LEVEL=INFO
```

---

## Step 5: Run the Bot

```bash
python src/main.py
```

**Expected output:**
```
[INFO] ================================================================================
[INFO] Slack Bot Assistant Starting
[INFO] ================================================================================
[INFO] Environment: development
[INFO] [OK] Slack Bolt app created successfully
[INFO] [OK] Scheduler started with 4 jobs: reminders (60s), RAG indexing (7200s), cleanup (weekly), heartbeat (5m)
[INFO] ⚡️ Bolt app is running in Socket Mode!
```

The bot is now running.

---

## Quick Test

### Test 1: Send a DM

1. Open Slack
2. Find your bot in the Apps section
3. Send: `Hello!`
4. The bot should reply

### Test 2: Use a Slash Command

In any channel, type:
```
/bot-help
```

You should see a help message with available commands.

### Test 3: Try Summarization

1. In a channel with messages, type:
   ```
   /bot-summarize #general 2
   ```
2. Bot will summarize the last 2 hours of messages

---

## Common Issues

### "invalid_auth" error
**Fix:** Check your tokens in `.env` are correct
- `SLACK_BOT_TOKEN` should start with `xoxb-`
- `SLACK_APP_TOKEN` should start with `xapp-`

### Bot doesn't respond to @mentions
**Fix:**
1. Invite bot to channel: `/invite @YourBot`
2. Check `app_mention` event is subscribed
3. Check Socket Mode is enabled

### Import errors
**Fix:** Install dependencies
```bash
poetry install
# OR
pip install -e .
```

### "No module named 'config'"
**Fix:** Run from the `agent/` folder:
```bash
cd 04.slack-workflow-agent/agent
python src/main.py
```

---

## Next Steps

- [docs/guides/E2E_TESTING_GUIDE.md](docs/guides/E2E_TESTING_GUIDE.md): manual test checklist for a test workspace
- [docs/guides/GUIDE.md](docs/guides/GUIDE.md): long-form, module-by-module walkthrough
- Check the logs (`logs/app.log`, `logs/error.log`) and the Slack app configuration if something does not work

---

## What the Bot Can Do

### Slash Commands
- `/bot-help` — Show help
- `/bot-status` — Show bot status
- `/bot-summarize #channel [hours]` — AI summary of channel
- `/bot-remind [message] in [time]` — Set reminder

### Direct Messaging
Send a DM and ask it to:
- Summarize any channel
- Detect issues/bugs in conversations
- Schedule reminders
- List channels
- Create GitHub issues (if configured)
- Search Notion (if configured)

### Automatic Background Jobs
- Reminder delivery (every 60s)
- RAG indexing (every 2h) — indexes messages for semantic search
- Cleanup old reminders (weekly)
- Health check heartbeat (every 5min)

