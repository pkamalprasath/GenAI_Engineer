Scaffold a new Slack Bot project using the Bolt framework based on the open_claw_slack_bot project patterns.

## Usage
`/slack-bot-new <project-name> [--socket | --http]`

Default mode is `--socket` (Socket Mode, recommended for development).

## Steps to Perform

### 1. Create Project Structure

Create the following folder layout:
```
<project-name>/
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
├── app.py              # Main entry point
├── config.py           # Configuration loader
├── handlers/
│   ├── __init__.py
│   ├── events.py       # app_mention, message handlers
│   ├── actions.py      # button/select action handlers
│   └── commands.py     # slash command handlers
└── utils/
    ├── __init__.py
    └── helpers.py
```

### 2. Generate requirements.txt

```
slack-bolt>=1.18.0
slack-sdk>=3.27.0
python-dotenv>=1.0.0
```

Add to requirements.txt if using LangChain integration:
```
langchain>=0.2.0
langchain-openai>=0.1.0
openai>=1.30.0
```

### 3. Generate .env.example

```bash
# ============================================================
# <Project Name> Slack Bot — Environment Variables
# ============================================================
# SETUP:
#   1. cp .env.example .env
#   2. Fill in your actual values
#   3. NEVER commit .env to git
# ============================================================

# --- Slack (required) ---
# Get tokens from: https://api.slack.com/apps → Your App → Settings
SLACK_BOT_TOKEN="xoxb-your-bot-token-here"
SLACK_APP_TOKEN="xapp-your-app-level-token-here"   # Socket Mode only
SLACK_SIGNING_SECRET="your-signing-secret-here"

# --- OpenAI (if using LangChain) ---
# Get from: https://platform.openai.com/api-keys
OPENAI_API_KEY="your-openai-api-key-here"
```

### 4. Generate app.py

Use Socket Mode by default:
```python
import os
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from handlers.events import register_event_handlers
from handlers.actions import register_action_handlers
from handlers.commands import register_command_handlers

load_dotenv()

app = App(token=os.environ["SLACK_BOT_TOKEN"])

register_event_handlers(app)
register_action_handlers(app)
register_command_handlers(app)

if __name__ == "__main__":
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    handler.start()
```

### 5. Generate config.py

```python
import os
from dotenv import load_dotenv

load_dotenv()

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")
```

### 6. Generate handlers/events.py

**CRITICAL RULES for Slack event handlers** (learned from open_claw_slack_bot):

1. **Always include `next` parameter** in middleware functions — forgetting it causes the app to hang silently with no error message.
2. **Use `app_mention` NOT `message` for bot triggers** — `message` fires on every message including DMs; `app_mention` only fires when `@BotName` is mentioned.
3. **Always wrap Slack API calls in try/except SlackApiError** — Slack API errors are silent otherwise.
4. **Never call `say()` twice** in the same handler — causes "already acknowledged" errors.
5. **Check `event.get("bot_id")` before processing** — filters out echoed bot messages.

```python
from slack_sdk.errors import SlackApiError

def register_event_handlers(app):

    @app.event("app_mention")
    def handle_mention(event, say, client, logger):
        """Fires when @BotName is mentioned in a channel."""
        # Skip messages from bots (prevent loops)
        if event.get("bot_id"):
            return

        user = event.get("user")
        text = event.get("text", "")
        channel = event.get("channel")

        # Strip the bot mention from text
        # Format: "<@U12345> your message here"
        user_message = text.split(">", 1)[-1].strip() if ">" in text else text

        try:
            say(f"Hello <@{user}>! You said: {user_message}")
        except SlackApiError as e:
            logger.error(f"Slack API error: {e.response['error']}")

    @app.event("message")
    def handle_dm(event, say, logger):
        """Fires on direct messages to the bot (channel_type: 'im')."""
        if event.get("bot_id") or event.get("subtype"):
            return

        if event.get("channel_type") == "im":
            user = event.get("user")
            try:
                say(f"Hi <@{user}>! This is a DM handler.")
            except SlackApiError as e:
                logger.error(f"Slack API error: {e.response['error']}")
```

### 7. Generate handlers/actions.py

```python
from slack_sdk.errors import SlackApiError

def register_action_handlers(app):

    @app.action("button_click")
    def handle_button(ack, body, say, logger):
        ack()  # Always acknowledge actions within 3 seconds
        user = body["user"]["id"]
        try:
            say(f"<@{user}> clicked the button!")
        except SlackApiError as e:
            logger.error(f"Slack API error: {e.response['error']}")
```

### 8. Generate handlers/commands.py

```python
from slack_sdk.errors import SlackApiError

def register_command_handlers(app):

    @app.command("/hello")
    def handle_hello(ack, respond, command, logger):
        ack()  # Always acknowledge slash commands within 3 seconds
        user = command["user_id"]
        try:
            respond(f"Hello <@{user}>!")
        except SlackApiError as e:
            logger.error(f"Slack API error: {e.response['error']}")
```

### 9. Generate .gitignore

Include standard Python + Slack Bot exclusions:
```
__pycache__/
*.py[cod]
venv/
.venv/
.env
.env.*
!.env.example
*.log
.idea/
.vscode/
.claude/
```

### 10. Generate README.md

Include sections:
- Project overview
- Features list
- Tech stack table
- Setup instructions (Slack App creation → OAuth scopes → Socket Mode → env vars → run)
- Slack App Required Scopes table
- Project structure tree
- Common issues / troubleshooting

### 11. Slack App Setup Reminder

Print a reminder to the user:

```
=== Slack App Setup Checklist ===
Go to https://api.slack.com/apps → Create New App → From Scratch

OAuth & Permissions → Bot Token Scopes (minimum):
  - app_mentions:read
  - chat:write
  - im:history
  - im:read
  - im:write

Event Subscriptions → Subscribe to bot events:
  - app_mention
  - message.im

Socket Mode → Enable Socket Mode → Create App-Level Token
  Scope: connections:write

Install App to Workspace → Copy Bot Token (xoxb-...)
Copy: Bot Token, App-Level Token, Signing Secret → into .env
```

### 12. Report

Show:
- All files created with their paths
- Slack App setup checklist
- How to run: `python app.py`
- Any warnings about missing env vars
