# Quick Start Guide — Slack Bot Assistant

> Get your bot running in 5 minutes!

---

## Prerequisites

✅ Python 3.11+
✅ Slack workspace (admin access to create apps)
✅ Anthropic API key (for Claude)

---

## Step 1: Create Slack App (2 minutes)

1. Go to https://api.slack.com/apps
2. Click **"Create New App"** → **"From scratch"**
3. Name it **"Slack Bot Assistant"**
4. Select your workspace
5. Click **"Create App"**

---

## Step 2: Configure Slack App (3 minutes)

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

## Step 3: Install Dependencies (1 minute)

```bash
cd d:\AI\KrishNaik_Academy\Coding\Vizuara\open_claw_proj

# Using Poetry (recommended)
poetry install

# OR using pip
pip install -r requirements.txt
```

---

## Step 4: Configure Environment (1 minute)

Edit `.env` file:

```bash
# REQUIRED - Slack credentials
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_APP_TOKEN=xapp-your-app-token-here
SLACK_SIGNING_SECRET=your-signing-secret-here

# REQUIRED - AI
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key-here

# Optional (for full functionality)
OPENAI_API_KEY=sk-your-openai-key-here
GITHUB_TOKEN=ghp_your-github-token-here
NOTION_TOKEN=secret_your-notion-token-here

# Environment
ENVIRONMENT=development
LOG_LEVEL=INFO
```

---

## Step 5: Run the Bot! (30 seconds)

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
[INFO] [OK] Scheduler started with 4 jobs
[INFO] ⚡️ Bolt app is running in Socket Mode!
```

**✅ Bot is now running!**

---

## Quick Test

### Test 1: Send a DM

1. Open Slack
2. Find your bot in the Apps section
3. Send: `Hello!`
4. Bot should respond within seconds

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
pip install -r requirements.txt
```

### "No module named 'config'"
**Fix:** Run from project root:
```bash
cd d:\AI\KrishNaik_Academy\Coding\Vizuara\open_claw_proj
python src/main.py
```

---

## Next Steps

✅ **Working?** Great! Read the full guide:
- [docs/guides/E2E_TESTING_GUIDE.md](docs/guides/E2E_TESTING_GUIDE.md) — Complete testing checklist
- [docs/development/TEST_RESULTS.md](docs/development/TEST_RESULTS.md) — Integration test results
- [docs/development/FIXES_SUMMARY.md](docs/development/FIXES_SUMMARY.md) — All features & fixes

❌ **Not working?** Check:
- [docs/development/PROBLEMS.md](docs/development/PROBLEMS.md) — Known issues and solutions
- Logs for error messages
- Slack app configuration

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
- ⏰ Reminder delivery (every 60s)
- 🔍 RAG indexing (every 2h) — indexes messages for semantic search
- 🧹 Cleanup old reminders (weekly)
- 💓 Health check heartbeat (every 5min)

---

**Enjoy your AI-powered Slack bot! 🤖✨**
