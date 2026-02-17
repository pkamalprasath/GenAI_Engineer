# Open Claw Project - Complete Beginner's Guide

---

## PART 1: How to Run the Project & Use the Bot (Step by Step)

---

### Step 1: Install Prerequisites

You need these installed on your computer before anything else:

| Tool        | What it does                        | Download from                        |
|-------------|-------------------------------------|--------------------------------------|
| Python 3.11+| Runs all the code                   | https://www.python.org/downloads/    |
| Poetry      | Manages Python packages             | https://python-poetry.org/docs/      |
| Git         | Version control (optional but good) | https://git-scm.com/downloads        |

**Check if they're installed** (open a terminal/command prompt):
```bash
python --version     # Should show 3.11 or higher
poetry --version     # Should show 1.x or 2.x
```

---

### Step 2: Install Project Dependencies

Open a terminal in the project folder:
```bash
cd d:\AI\KrishNaik_Academy\Coding\Vizuara\open_claw_proj

# Install all packages listed in pyproject.toml
poetry install
```

This installs everything the bot needs: slack-bolt, anthropic, chromadb, etc.

---

### Step 3: Create a Slack App (Detailed Walkthrough)

This is the most important step - you're creating the bot's identity on Slack.
Follow every sub-step carefully.

#### 3A. Go to Slack API Portal

- Open your browser and go to: **https://api.slack.com/apps**
- Sign in with the same account you use for your Slack workspace
- You'll land on the **"Your Apps"** page

#### 3B. Create the App

- Click the green **"Create New App"** button (top right)
- A popup appears with two options - click **"From scratch"**
- Fill in:
  - **App Name**: `My Assistant Bot` (or whatever you want to call it)
  - **Pick a workspace**: Select YOUR workspace from the dropdown
- Click **"Create App"**
- You'll land on the **"Basic Information"** page for your new app

#### 3C. Get the Signing Secret

You're already on the "Basic Information" page:

- Scroll down to the section called **"App Credentials"**
- You'll see **"Signing Secret"** - click **"Show"** to reveal it
- Copy this value and paste it into your `.env` file:
  ```
  SLACK_SIGNING_SECRET=paste-your-signing-secret-here
  ```

#### 3D. Enable Socket Mode

- In the **left sidebar**, click **"Socket Mode"**
- Toggle the switch to **ON**
- A popup asks you to create an App-Level Token:
  - **Token Name**: type `socket-token`
  - **Add Scope**: click "Add Scope" and select `connections:write`
  - Click **"Generate"**
- A token starting with `xapp-` appears - **copy it immediately**
- Paste it into your `.env` file:
  ```
  SLACK_APP_TOKEN=xapp-1-paste-your-full-token-here
  ```
- Click **"Done"**

#### 3E. Add Bot Permissions (OAuth Scopes)

- In the **left sidebar**, click **"OAuth & Permissions"**
- Scroll down to **"Scopes"** section
- Under **"Bot Token Scopes"**, click **"Add an OAuth Scope"** for EACH of these:

| Scope              | What it allows the bot to do                    |
|--------------------|-------------------------------------------------|
| `app_mentions:read` | Know when someone types @YourBot               |
| `channels:history`  | Read messages in public channels                |
| `channels:read`     | See the list of public channels                 |
| `chat:write`        | Send messages                                   |
| `commands`          | Respond to /slash commands                      |
| `groups:read`       | See private channels the bot is invited to      |
| `im:history`        | Read direct messages sent to the bot            |
| `im:read`           | See the list of DM conversations                |
| `im:write`          | Send direct messages                            |
| `reactions:write`   | Add emoji reactions to messages                 |
| `users:read`        | Look up user names and profile info             |

After adding all 11 scopes, your list should show all of them.

#### 3F. Install the App to Your Workspace

- Still on **"OAuth & Permissions"** page
- Scroll to the **top** - you'll see **"OAuth Tokens for Your Workspace"**
- Click the **"Install to Workspace"** button
- Slack shows a permission screen - click **"Allow"**
- A **Bot User OAuth Token** appears (starts with `xoxb-`)
- Copy it and paste into your `.env` file:
  ```
  SLACK_BOT_TOKEN=xoxb-paste-your-full-bot-token-here
  ```

#### 3G. Enable Event Subscriptions

- In the **left sidebar**, click **"Event Subscriptions"**
- Toggle the switch to **ON**
- Scroll down to **"Subscribe to bot events"**
- Click **"Add Bot User Event"** and add these 3 events:

| Event Name          | When it fires                                    |
|---------------------|--------------------------------------------------|
| `message.channels`  | Someone posts a message in a public channel      |
| `message.im`        | Someone sends a direct message to the bot        |
| `app_mention`       | Someone types @YourBot in a channel              |

- Click **"Save Changes"** at the bottom

#### 3H. Create Slash Commands

- In the **left sidebar**, click **"Slash Commands"**
- Click **"Create New Command"** and fill in for each:

**Command 1:**
- Command: `/bot-help`
- Request URL: `https://placeholder.com` (Socket Mode ignores this, but the field is required)
- Short Description: `Show available bot commands`
- Click **"Save"**

**Command 2:**
- Command: `/bot-status`
- Request URL: `https://placeholder.com`
- Short Description: `Check bot health status`
- Click **"Save"**

**Command 3:**
- Command: `/bot-summarize`
- Request URL: `https://placeholder.com`
- Short Description: `Summarize channel messages`
- Usage Hint: `#channel 24h`
- Click **"Save"**

**Command 4:**
- Command: `/bot-remind`
- Request URL: `https://placeholder.com`
- Short Description: `Set a reminder`
- Usage Hint: `Do something in 30 minutes`
- Click **"Save"**

#### 3I. Enable DMs with the Bot

- In the **left sidebar**, click **"App Home"**
- Scroll down to **"Show Tabs"**
- Make sure **"Messages Tab"** is toggled **ON**
- Check the box: **"Allow users to send Slash commands and messages from the messages tab"**

#### 3J. Invite the Bot to a Channel

- Open **Slack** (the app, not the API portal)
- Go to any channel (e.g., #general)
- Type: `/invite @My Assistant Bot` (use your bot's actual name)
- The bot now appears in that channel's member list

#### Your `.env` should now have these 3 Slack values:
```env
SLACK_BOT_TOKEN=xoxb-YOUR-BOT-TOKEN-HERE
SLACK_APP_TOKEN=xapp-1-A1234567890-1234567890123-abc123def456...
SLACK_SIGNING_SECRET=abc123def456ghi789...
```

---

### Step 4: Get API Keys (Detailed for Each Service)

#### 4A. Anthropic API Key (Claude AI - the bot's brain)

This is **required**. The bot uses Claude to understand messages and generate responses.

**Create an Account:**
- Go to **https://console.anthropic.com/**
- Click **"Sign Up"** (or "Log In" if you already have an account)
- Sign up with email or Google account
- Verify your email if prompted

**Add Credits (pay-as-you-go):**
- After login, you land on the dashboard
- Click **"Billing"** in the left sidebar (or top menu)
- Add a payment method (credit card)
- Add credits - minimum $5 is enough to start
- **Pricing**: Claude Sonnet costs about $3 per million input tokens, $15 per million output tokens
- For testing/development, $5 lasts a very long time

**Generate the API Key:**
- Click **"API Keys"** in the left sidebar
- Click **"Create Key"**
- Give it a name: `slack-bot-key`
- Copy the key (starts with `sk-ant-api03-...`)
- **You can only see this key ONCE** - if you lose it, you need to create a new one

**Paste into `.env`:**
```env
ANTHROPIC_API_KEY=sk-ant-api03-paste-your-full-key-here
```

---

#### 4B. OpenAI API Key (for text embeddings/search)

This is **required for the RAG search feature**. It converts text into numbers (vectors) so the bot
can find similar past conversations. It does NOT power the chat - Claude does that.

**Create an Account:**
- Go to **https://platform.openai.com/**
- Click **"Sign Up"** (or "Log In")
- Sign up with email, Google, or Microsoft account

**Add Credits:**
- Click your profile icon (top right) > **"Billing"**
- Click **"Add payment method"**
- Add $5 credit (embeddings are extremely cheap - about $0.02 per million tokens)

**Generate the API Key:**
- Go to **https://platform.openai.com/api-keys**
- Click **"+ Create new secret key"**
- Name it: `slack-bot-embeddings`
- Copy the key (starts with `sk-...`)
- **You can only see this key ONCE**

**Paste into `.env`:**
```env
OPENAI_API_KEY=sk-proj-paste-your-full-key-here
```

---

#### 4C. GitHub Token (OPTIONAL - for GitHub integration)

This lets the bot create issues, read repos, etc. on GitHub.
**Skip this entirely if you don't need GitHub features** - the bot works fine without it.

**Go to Token Settings:**
- Go to **https://github.com/settings/tokens**
- Or navigate manually: GitHub > click your avatar (top right) > **Settings** > **Developer settings** (bottom of left sidebar) > **Personal access tokens** > **Tokens (classic)**

**Generate Token:**
- Click **"Generate new token"** > **"Generate new token (classic)"**
- GitHub asks for your password - enter it
- Fill in:
  - **Note**: `slack-bot-github`
  - **Expiration**: 90 days (you can always generate a new one later)
  - **Select scopes** (check these boxes):
    - `repo` (full control of repositories - needed to create issues)
    - `read:org` (read organization info)
- Click **"Generate token"**
- Copy the token (starts with `ghp_...`)
- **You can only see this ONCE**

**Paste into `.env`:**
```env
GITHUB_TOKEN=ghp_paste-your-full-token-here
```

---

#### 4D. Notion Token (OPTIONAL - for Notion integration)

This lets the bot create pages and search in your Notion workspace.
**Skip this entirely if you don't use Notion** - the bot works fine without it.

**Create a Notion Integration:**
- Go to **https://www.notion.so/my-integrations**
- Sign in with your Notion account
- Click **"+ New integration"**
- Fill in:
  - **Name**: `Slack Bot`
  - **Associated workspace**: Select your workspace
  - **Logo**: Optional (skip it)
- Click **"Submit"**

**Copy the Token:**
- After creation, you'll see the **"Internal Integration Secret"**
- Click **"Show"** then **"Copy"**
- It starts with `secret_...`

**Connect to a Notion Page (important!):**
- Go to any Notion page you want the bot to access
- Click the **"..."** menu (top right of the page)
- Click **"Add connections"**
- Search for **"Slack Bot"** (your integration name)
- Click it to connect
- The bot can ONLY access pages where you explicitly add this connection
- Repeat for any other pages you want the bot to reach

**Paste into `.env`:**
```env
NOTION_TOKEN=secret_paste-your-full-token-here
```

---

### Step 5: Create the .env File

Copy the example and fill in your real tokens:
```bash
# In the project folder:
copy .env.example .env
```

Open `.env` in a text editor and replace the placeholder values:
```env
# REQUIRED - From Step 3
SLACK_BOT_TOKEN=xoxb-your-actual-bot-token
SLACK_APP_TOKEN=xapp-your-actual-app-token
SLACK_SIGNING_SECRET=your-actual-signing-secret

# REQUIRED - From Step 4
ANTHROPIC_API_KEY=sk-ant-your-actual-key
OPENAI_API_KEY=sk-your-actual-openai-key

# OPTIONAL
GITHUB_TOKEN=ghp_your-token-if-you-have-one
NOTION_TOKEN=secret_your-token-if-you-have-one

# Leave these as-is for development
ENVIRONMENT=development
LOG_LEVEL=INFO
PORT=3000
CHROMA_PERSIST_DIRECTORY=./memory_store/chroma_db
MEMORY_STORE_PATH=./memory_store
```

---

### Step 6: Run the Bot

```bash
# Activate the virtual environment
poetry shell

# Start the bot
python -m src.main
```

You should see output like:
```
============================================================
Starting Slack Bot Assistant
Environment: development
============================================================
Creating Slack Bolt app...
[OK] Middleware registered
[OK] Event listeners registered
[OK] Slack Bolt app created successfully
Starting in Socket Mode (development)...
Slack bot is running! Press Ctrl+C to stop.
```

---

### Step 7: Use the Bot in Slack

Now go to Slack and try these:

| Action                          | What happens                         |
|---------------------------------|--------------------------------------|
| Send a DM to the bot            | Bot replies with your message echoed |
| Type `@YourBot hello` in a channel | Bot responds to the mention       |
| Type `/bot-help`                | Shows all available commands         |
| Type `/bot-status`              | Shows bot health status              |
| Type `/bot-summarize #general 24h` | Summarization placeholder         |
| Type `/bot-remind Review PR in 1 hour` | Reminder placeholder           |

---

### Step 8: Stop the Bot

Press `Ctrl+C` in the terminal. The bot shuts down gracefully.

---

### Step 9: Run Tests (Optional - for developers)

```bash
# Run all 189 tests
poetry run pytest tests/ -v

# Run with coverage report
poetry run pytest tests/ --cov=src --cov-report=term-missing

# Run only specific module tests
poetry run pytest tests/unit/test_slack/ -v
poetry run pytest tests/unit/test_memory/ -v
```

---

### Troubleshooting

| Problem                           | Solution                                            |
|-----------------------------------|-----------------------------------------------------|
| `ModuleNotFoundError`             | Run `poetry install` again                          |
| `Token validation failed`         | Check your `.env` tokens are correct                |
| `UnicodeEncodeError` on Windows   | Already fixed - use latest code                     |
| Bot doesn't respond in channel    | Make sure you invited it: `/invite @BotName`        |
| Bot doesn't respond to DMs        | Enable `im:read` and `im:write` scopes in Slack app|
| `sqlite3` error on Python 3.13    | Already fixed - DLL patch is in place               |
| `Connection refused`              | Check Socket Mode is enabled in Slack app settings  |

---
---

## PART 2: Module-by-Module Documentation (Beginner-Friendly)

---

### What Does This Project Do? (The Goal)

This project is an **intelligent Slack bot** that:
1. Listens to messages and commands in your Slack workspace
2. Uses AI (Claude by Anthropic) to understand and respond
3. Remembers past conversations (short-term and long-term memory)
4. Can search through old messages intelligently (RAG - Retrieval Augmented Generation)
5. Can connect to GitHub and Notion to perform actions

Think of it as a smart assistant that lives inside your Slack workspace.

---

### Project Structure Overview

```
open_claw_proj/
|
|-- config/              <-- Settings and configuration
|   |-- settings.py      <-- All environment variables in one place
|   |-- logging.yaml     <-- How logs are formatted and stored
|
|-- src/                 <-- All the actual code
|   |-- main.py          <-- "Press play" - starts everything
|   |-- app.py           <-- Builds the Slack app with all parts connected
|   |
|   |-- utils/           <-- Helper tools used everywhere
|   |   |-- logger.py
|   |   |-- exceptions.py
|   |   |-- security.py
|   |   |-- validators.py
|   |
|   |-- slack/           <-- Everything Slack-related
|   |   |-- listeners/   <-- "Ears" - listens for events
|   |   |-- services/    <-- "Hands" - sends messages, reacts
|   |   |-- middleware/   <-- "Security guard" - checks before processing
|   |
|   |-- agent/           <-- The AI brain
|   |   |-- orchestrator.py
|   |   |-- tools.py
|   |   |-- state.py
|   |   |-- context_builder.py
|   |
|   |-- memory/          <-- Remembering things
|   |   |-- manager.py
|   |   |-- short_term.py
|   |   |-- long_term.py
|   |   |-- schemas.py
|   |   |-- retriever.py
|   |
|   |-- rag/             <-- Smart search through old messages
|   |   |-- store.py
|   |   |-- indexer.py
|   |   |-- retriever.py
|   |
|   |-- mcp_servers/     <-- Connections to external tools
|   |   |-- registry.py
|   |   |-- slack_server.py
|   |   |-- github_client.py
|   |   |-- notion_client.py
|   |
|   |-- services/        <-- Business logic (future)
|
|-- tests/               <-- Tests to make sure code works
|   |-- conftest.py      <-- Shared test setup
|   |-- unit/            <-- Individual module tests
```

---

### MODULE 1: config/settings.py

**Goal:** Keep ALL configuration in ONE place, loaded from environment variables.

**Why this exists:**
Imagine you have 20+ passwords/tokens/settings scattered across 15 files.
If you need to change one, you'd have to find it first! This file solves
that by loading everything from your `.env` file into a single `settings` object.

```
How it works:
.env file  -->  settings.py reads it  -->  Any file can do: settings.slack_bot_token
```

**Key parts explained:**

```python
class Settings(BaseSettings):
```
- `BaseSettings` is from `pydantic-settings` library
- It automatically reads values from your `.env` file
- If a value is missing and required, it raises an error immediately (fail-fast)

```python
slack_bot_token: str
```
- This is a "field" - it says "I need a value called SLACK_BOT_TOKEN from the environment"
- `str` means it must be text
- If you forget to put it in `.env`, the app crashes at startup with a clear error

```python
environment: str = "development"
```
- The `= "development"` means "if nobody provides this, use 'development' as default"

```python
@field_validator("slack_bot_token")
def validate_slack_bot_token(cls, v):
    if not v.startswith("xoxb-"):
        raise ValueError("Bot token must start with 'xoxb-'")
    return v
```
- A "validator" - checks that the token format is correct BEFORE the app starts
- Catches typos early (e.g., you accidentally pasted the wrong token)

```python
@property
def use_socket_mode(self) -> bool:
    return self.environment == "development"
```
- A "computed property" - calculated from other values, not stored
- In development mode, use WebSocket (no public URL needed)
- In production, use HTTP (needs a public URL)

```python
settings = Settings()
```
- Creates ONE global settings object
- Every file imports this same object: `from config.settings import settings`

---

### MODULE 2: config/logging.yaml

**Goal:** Control what gets logged, where, and how detailed.

**Why this exists:**
When something goes wrong, logs help you figure out what happened.
This file controls:
- What gets printed to your terminal (console)
- What gets saved to files (for later investigation)
- How much detail each module shows

**Key parts explained:**

```yaml
formatters:
  simple:
    format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```
- Defines what each log line looks like
- `%(asctime)s` = timestamp (when it happened)
- `%(name)s` = which module (e.g., "src.slack.listeners")
- `%(levelname)s` = severity (DEBUG, INFO, WARNING, ERROR)
- `%(message)s` = the actual message

```yaml
handlers:
  rotating_file:
    maxBytes: 10485760     # 10MB
    backupCount: 5         # Keep 5 old files
```
- Logs go to a file, but files don't grow forever
- When a file reaches 10MB, it starts a new one
- Keeps the last 5 files, deletes older ones

```yaml
loggers:
  src.agent:
    level: DEBUG           # Show everything (very detailed)
  src.slack:
    level: INFO            # Show important stuff only
  slack_sdk:
    level: WARNING         # Only show problems
```
- Different modules log at different detail levels
- DEBUG = everything (useful for fixing bugs)
- INFO = normal operations ("Bot started", "Message received")
- WARNING = something unusual ("Rate limit approaching")
- ERROR = something broke ("Failed to send message")

---

### MODULE 3: src/main.py

**Goal:** The starting point - like pressing "Play" on the bot.

**Why this exists:**
Every program needs an entry point. This file:
1. Sets up logging first (so we can see what's happening)
2. Loads the settings
3. Creates the Slack app
4. Starts listening for events
5. Handles graceful shutdown (cleanup when you press Ctrl+C)

**Key parts explained:**

```python
sys.path.insert(0, str(Path(__file__).parent.parent))
```
- Tells Python "also look in the project root folder when importing modules"
- Without this, `import src.app` wouldn't work

```python
setup_logging()
logger = get_logger(__name__)
```
- Sets up the logging system BEFORE anything else
- `__name__` gives the module name (e.g., "src.main") so logs show which file they came from

```python
def handle_shutdown(signum, frame):
    logger.info("Shutdown signal received, cleaning up...")
    sys.exit(0)
```
- When you press Ctrl+C, the operating system sends a "signal"
- This function catches it and exits cleanly
- Without this, the program might crash with an ugly error

```python
async def main() -> None:
```
- `async` means this function can do multiple things at once (handle many Slack events)
- This is critical for a bot - you don't want it to freeze while handling one message

```python
if settings.use_socket_mode:
    handler = AsyncSocketModeHandler(app=app, app_token=settings.slack_app_token)
    await handler.start_async()
```
- Socket Mode = uses a WebSocket connection (like a phone call that stays open)
- Perfect for development because you don't need a public URL
- Production uses HTTP (like a mailbox that receives requests)

```python
await asyncio.Event().wait()
```
- "Stay running forever until someone stops me"
- Without this, the program would start and immediately exit

---

### MODULE 4: src/app.py

**Goal:** Build the Slack app by connecting all the pieces together.

**Why this exists:**
Think of this as an assembly line:
1. Create the Slack app object
2. Attach security checks (middleware)
3. Attach event handlers (listeners)
4. Attach error handling

This uses the **Factory Pattern** - a function that builds and returns a
fully configured object. This is great for testing because you can create
multiple app instances with different configurations.

**Key parts explained:**

```python
def create_app() -> AsyncApp:
```
- "Factory function" - builds a complete app and returns it
- `-> AsyncApp` means it returns an AsyncApp object (type hint for clarity)

```python
app = AsyncApp(
    token=settings.slack_bot_token,
    signing_secret=settings.slack_signing_secret,
)
```
- Creates the Slack Bolt app
- `token` = the bot's identity card (how Slack knows who's calling)
- `signing_secret` = used to verify that incoming requests are really from Slack

```python
app.middleware(auth_middleware)
app.middleware(rate_limit_middleware)
app.middleware(error_handler_middleware)
```
- **Middleware** = code that runs BEFORE every event handler
- Order matters! Auth checks first, then rate limiting, then error handling
- Like airport security: ID check -> luggage scan -> boarding

```python
messages.register_listeners(app)
commands.register_listeners(app)
mentions.register_listeners(app)
```
- Connects the "ears" (listeners) to the app
- Each module handles a different type of Slack event

```python
@app.error
async def global_error_handler(error, body, logger):
```
- Catches ANY error that wasn't handled elsewhere
- Prevents the entire bot from crashing because of one bad request
- Like a safety net under a tightrope walker

---

### MODULE 5: src/utils/logger.py

**Goal:** Set up logging so every module can report what it's doing.

**Key parts explained:**

```python
def setup_logging():
    config_path = Path(__file__).parent.parent.parent / "config" / "logging.yaml"
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    logging.config.dictConfig(config)
```
- Reads the YAML config file
- Applies it to Python's logging system
- Creates the logs directory if it doesn't exist

```python
def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
```
- Every module calls `get_logger(__name__)` to get its own named logger
- This way, log messages show which module produced them

```python
def log_function_call(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        logger.debug(f"Calling {func.__name__}")
        result = await func(*args, **kwargs)
        logger.debug(f"{func.__name__} completed")
        return result
    return wrapper
```
- A **decorator** - adds logging to any function automatically
- Usage: put `@log_function_call` above a function and it logs when that function starts and finishes
- `*args, **kwargs` = "accept whatever arguments the original function accepts"

---

### MODULE 6: src/utils/exceptions.py

**Goal:** Define all possible errors so we can handle each one differently.

**Why this exists:**
Instead of every error being a generic "something went wrong", we create
specific error types. This lets us:
- Show the user a helpful message ("Channel not found" vs "Error 500")
- Log the right amount of detail
- Decide whether to retry or give up

**Key parts explained:**

```python
class SlackBotError(Exception):
    def __init__(self, message: str, details: dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)
```
- The BASE error - all other errors inherit from this
- `message` = human-readable description
- `details` = extra info for debugging (dictionary)
- `super().__init__()` = tells Python's built-in Exception about the message

```python
class RateLimitError(SlackAPIError):
    def __init__(self, retry_after: int = 30):
        self.retry_after = retry_after
        super().__init__("Rate limited", error_code="rate_limited")
```
- Specific error for when Slack says "slow down!"
- `retry_after` = how many seconds to wait before trying again
- Inherits from `SlackAPIError` which inherits from `SlackBotError` (hierarchy)

**The hierarchy looks like:**
```
SlackBotError (base)
  |-- ConfigurationError
  |     |-- TokenError
  |-- SlackAPIError
  |     |-- RateLimitError
  |     |-- ChannelNotFoundError
  |-- AgentError
  |     |-- ToolExecutionError
  |-- MemoryError
  |-- RAGError
  |-- MCPError
  |-- ValidationError
  |-- ServiceError
```

```python
def handle_exception(error, logger, user_message=None):
```
- Utility function for consistent error handling everywhere
- Logs the full technical error
- Returns a safe, user-friendly message (never leaks internal details)

---

### MODULE 7: src/utils/security.py

**Goal:** Protect the bot from attacks and keep secrets safe.

**Key parts explained:**

```python
def verify_slack_signature(signing_secret, timestamp, body, signature):
    if abs(time.time() - float(timestamp)) > 300:  # 5 minutes
        return False
    sig_basestring = f"v0:{timestamp}:{body}"
    my_signature = "v0=" + hmac.new(
        signing_secret.encode(), sig_basestring.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(my_signature, signature)
```
- Verifies that an incoming request REALLY came from Slack (not an attacker)
- **Timestamp check**: Rejects requests older than 5 minutes (prevents replay attacks)
- **HMAC-SHA256**: Creates a "digital signature" using the signing secret
- `hmac.compare_digest()`: Compares signatures safely (prevents timing attacks)

```python
def mask_token(token: str, visible_chars: int = 4) -> str:
    return token[:visible_chars] + "***"
```
- When logging tokens, hides most of it: `xoxb-abc***`
- So if someone reads your logs, they can't steal your tokens

```python
class RateLimiter:
    def is_allowed(self, key: str) -> bool:
        now = time.time()
        # Remove requests older than the window
        self.requests[key] = [t for t in self.requests[key] if now - t < self.window]
        if len(self.requests[key]) >= self.max_requests:
            return False
        self.requests[key].append(now)
        return True
```
- Prevents spam/abuse by limiting requests
- **How it works**: Keeps a list of timestamps for each user
- If too many requests in the time window, blocks new ones
- Like a bouncer counting how many times someone enters

```python
def sanitize_for_logging(data: dict) -> dict:
```
- Takes a dictionary and replaces sensitive values with "***REDACTED***"
- Catches fields named: token, password, secret, api_key, credentials
- So you can safely log entire request objects

---

### MODULE 8: src/utils/validators.py

**Goal:** Check that all input data is correct and safe before using it.

**Why this exists:**
Users can send ANYTHING to your bot. Validators ensure:
- Channel IDs look like real Slack IDs
- Messages aren't too long
- Nobody is trying to inject malicious code

**Key parts explained:**

```python
def validate_channel_id(channel_id: str) -> bool:
    if not channel_id or len(channel_id) < 2:
        return False
    return channel_id[0] in ("C", "G", "D") and channel_id[1:].isalnum()
```
- Slack channel IDs always start with C (public), G (private), or D (DM)
- Rest must be letters/numbers
- Returns True/False

```python
def sanitize_text(text: str) -> str:
    text = html.escape(text)                               # <script> -> &lt;script&gt;
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)  # Remove control chars
    text = re.sub(r"\s+", " ", text).strip()               # Normalize whitespace
    return text
```
- **html.escape**: Converts dangerous HTML characters to safe versions
- **Control characters**: Removes invisible characters that could cause issues
- **Whitespace**: Collapses multiple spaces/tabs into single spaces

```python
def detect_injection_attempt(text: str) -> bool:
    patterns = [
        r"<script",           # XSS attack
        r"(?:SELECT|INSERT|UPDATE|DELETE|DROP)\s",  # SQL injection
        r"(?:;|\|)\s*(?:cat|ls|rm|curl|wget)",     # Command injection
        r"\.\./",             # Path traversal
    ]
```
- Checks if someone is trying to hack through the bot
- **XSS**: Injecting JavaScript into messages
- **SQL Injection**: Trying to run database commands
- **Command Injection**: Trying to run shell commands
- **Path Traversal**: Trying to access files outside the project

---

### MODULE 9: src/slack/listeners/messages.py

**Goal:** Listen for messages in Slack and decide how to respond.

**How the flow works:**
```
User sends message in Slack
  --> Slack sends event to bot
    --> This listener receives it
      --> Decides: Should I respond?
        --> If DM: Yes, respond
        --> If @mention in channel: Yes, respond
        --> If random channel message: No, ignore
```

**Key parts explained:**

```python
async def handle_message_event(event, say, client, logger):
```
- `event` = the message data from Slack (who sent it, what they said, where)
- `say` = a function to send a reply back
- `client` = the Slack API client (for more complex operations)
- `logger` = for logging what happened

```python
if event.get("bot_id"):
    return
```
- **Bot loop prevention**: If a bot sent this message, ignore it
- Without this, the bot could respond to itself forever!

```python
channel = event.get("channel", "")
is_dm = channel.startswith("D")
```
- Slack DM channels always start with "D"
- If it's a DM, the user is talking directly to the bot, so always respond

```python
await client.reactions_add(channel=channel, timestamp=ts, name="hourglass_flowing_sand")
```
- Adds an hourglass emoji to the message while processing
- Visual feedback so the user knows the bot is working

```python
await say(text=f"I heard you say: {text}", thread_ts=event.get("thread_ts"))
```
- `say()` sends a reply
- `thread_ts` = if the message was in a thread, reply in the same thread

---

### MODULE 10: src/slack/listeners/commands.py

**Goal:** Handle slash commands (things typed with a `/` prefix).

**Key parts explained:**

```python
async def handle_help_command(ack, command, client, logger):
    await ack()  # MUST acknowledge within 3 seconds!
```
- `ack()` = tells Slack "I received the command"
- Slack requires this within 3 seconds or it shows an error to the user
- Always call `ack()` FIRST, then process

```python
help_text = (
    "*Available Commands:*\n"
    "- `/bot-help` - Show this help message\n"
    "- `/bot-status` - Check bot status\n"
    ...
)
await client.chat_postMessage(channel=command["channel_id"], text=help_text)
```
- Builds a formatted help message using Slack's markdown (`*bold*`, etc.)
- `command["channel_id"]` = which channel the command was typed in
- Sends the response to that same channel

```python
async def handle_summarize_command(ack, command, client, context, logger):
    text = command.get("text", "")  # e.g., "#general 24h"
```
- `command["text"]` = everything the user typed AFTER the command
- `/bot-summarize #general 24h` -> text = "#general 24h"
- Currently a placeholder - will use AI summarization in Phase 7

---

### MODULE 11: src/slack/listeners/mentions.py

**Goal:** Respond when someone @mentions the bot in a channel.

**Key parts explained:**

```python
mention_text = re.sub(r"<@[A-Z0-9]+>", "", event.get("text", "")).strip()
```
- When someone types `@BotName hello`, Slack sends `<@U12345> hello`
- This regex removes the `<@U12345>` part, leaving just "hello"
- `re.sub(pattern, replacement, text)` = find and replace using pattern

```python
if not mention_text:
    await say(text="Hi! Try typing `/bot-help` to see what I can do.", ...)
    return
```
- If someone just types `@BotName` with nothing else, show help
- Good UX (user experience) - guide the user to useful commands

---

### MODULE 12: src/slack/services/message_service.py

**Goal:** A clean interface for all Slack message operations.

**Why this exists (Service Pattern):**
Instead of calling the Slack API directly everywhere (messy, hard to test),
we create a "service" class that wraps all the API calls. This way:
- All message logic is in one place
- Easy to test (just mock the service)
- Can add validation/logging in one place

**Key parts explained:**

```python
class MessageService:
    def __init__(self, client: AsyncWebClient):
        self.client = client
```
- **Dependency Injection**: The class receives the Slack client from outside
- This means in tests, you can pass a fake/mock client
- The service doesn't create its own connection - it uses what it's given

```python
async def post_message(self, channel: str, text: str, thread_ts: str = None, blocks: list = None):
    try:
        return await self.client.chat_postMessage(
            channel=channel, text=text, thread_ts=thread_ts, blocks=blocks
        )
    except SlackApiError as e:
        if e.response["error"] == "channel_not_found":
            raise ChannelNotFoundError(channel)
        raise
```
- `channel` = where to send
- `text` = what to send
- `thread_ts` = optional thread reply (None = new message)
- `blocks` = optional rich formatting (buttons, images, etc.)
- Catches Slack errors and converts them to our custom errors

```python
async def get_messages_in_timeframe(self, channel: str, hours: int = 24):
    oldest = str(time.time() - (hours * 3600))
    return await self.get_messages(channel, oldest=oldest)
```
- **Convenience method**: Instead of calculating timestamps yourself
- `hours * 3600` converts hours to seconds (Slack uses Unix timestamps)
- "Get me all messages from the last 24 hours" = much easier to use

```python
async def add_reaction(self, channel, timestamp, emoji):
    try:
        await self.client.reactions_add(channel=channel, timestamp=timestamp, name=emoji)
    except SlackApiError:
        pass  # Silently ignore (e.g., already_reacted)
```
- Adding reactions can fail for harmless reasons (already added that emoji)
- We silently ignore these failures instead of crashing

---

### MODULE 13: src/slack/middleware/ (auth, rate_limit, error_handler)

**Goal:** Run security/safety checks on EVERY incoming request.

**What is middleware?**
Think of middleware as security checkpoints. Every Slack event must pass
through ALL middleware before reaching your handler:

```
Slack Event --> [Auth Check] --> [Rate Limit Check] --> [Error Handler] --> Your Code
```

**auth.py** - Authentication middleware:
```python
async def auth_middleware(req, resp, next):
    if body.get("event", {}).get("bot_id"):
        return  # Skip bot messages entirely
    await next()  # Continue to next middleware
```
- `next()` passes the request to the next middleware/handler
- If you DON'T call `next()`, the request stops here (blocked)

**rate_limit.py** - Rate limiting middleware:
```python
async def rate_limit_middleware(req, resp, next):
    user_id = body.get("event", {}).get("user", "unknown")
    if not rate_limiter.is_allowed(f"user:{user_id}"):
        return  # Block - too many requests
    await next()
```
- 10 requests per minute per user, 30 per channel
- Prevents one user from overwhelming the bot
- Returns silently (doesn't respond with error to avoid spam)

**error_handler.py** - Error handling middleware:
```python
async def error_handler_middleware(req, resp, next):
    try:
        await next()
    except RateLimitError as e:
        logger.warning(f"Rate limited: {e}")
    except ValidationError as e:
        logger.warning(f"Bad input: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
```
- Wraps everything in try/except
- Different error types get different handling
- User-friendly messages sent back (never expose internal errors)

---

### MODULE 14: src/agent/orchestrator.py

**Goal:** The AI "brain" - takes a message, thinks about it, and produces a response.

**How the AI agent works:**
```
User message
  --> Build context (memory + past conversations)
    --> Send to Claude AI with tools available
      --> Claude decides: respond with text OR use a tool
        --> If tool used: execute tool, send result back to Claude
          --> Claude produces final response
```

**Key parts explained:**

```python
class AgentOrchestrator:
    def __init__(self):
        self.client = AsyncAnthropic()
        self.tool_registry = ToolRegistry()
        self.context_builder = ContextBuilder()
        self.memory_manager = MemoryManager()
```
- **Orchestrator** = the conductor of an orchestra
- It coordinates: AI client, tools, context, and memory
- Each component does one thing well

```python
async def process_message(self, message, user_id, channel_id):
    context = await self.context_builder.build_context(user_id, channel_id, message)
    system_prompt = self._build_system_prompt(context)
    response = await self.client.messages.create(
        model="claude-sonnet-4-5-20250514",
        system=system_prompt,
        messages=context["conversation_history"] + [{"role": "user", "content": message}],
        tools=self.tool_registry.get_tool_definitions(),
    )
```
- Builds context from memory and RAG
- Creates a system prompt that tells Claude its role and gives it context
- Sends to Claude with the conversation history and available tools
- Claude can either reply with text or call a tool

```python
def _build_system_prompt(self, context):
    prompt = "You are a helpful Slack assistant with access to tools..."
    if context["memory_context"]:
        prompt += f"\n\nMemory about this user:\n{context['memory_context']}"
    if context["rag_context"]:
        prompt += f"\n\nRelevant past conversations:\n{context['rag_context']}"
    return prompt
```
- The "system prompt" tells Claude WHO it is and WHAT it knows
- Memory context = what the bot remembers about this user
- RAG context = relevant old conversations found by searching

---

### MODULE 15: src/agent/tools.py

**Goal:** Define what external actions the AI can take.

**What are "tools" in AI?**
Claude (the AI) can do more than just talk. It can call "tools" -
predefined functions that interact with the real world. For example:
- Read Slack messages
- Post a message
- Create a GitHub issue
- Create a Notion page

**Key parts explained:**

```python
class ToolRegistry:
    def __init__(self):
        self.tools = {}
        self._register_builtin_tools()
```
- A "registry" = a catalog of available tools
- Registers all tools at startup

```python
def get_tool_definitions(self):
    return [
        {
            "name": "get_channel_messages",
            "description": "Get recent messages from a Slack channel",
            "input_schema": {
                "type": "object",
                "properties": {
                    "channel_id": {"type": "string", "description": "The channel ID"},
                    "hours": {"type": "integer", "description": "Hours to look back"},
                },
                "required": ["channel_id"],
            },
        },
        ...
    ]
```
- Returns tool descriptions in **Claude's expected format**
- Claude reads these descriptions to decide which tool to use
- `input_schema` tells Claude what parameters each tool needs

```python
async def execute_tool(self, tool_name, **kwargs):
    if tool_name not in self.tools:
        raise ToolNotFoundError(tool_name)
    return await self.tools[tool_name](**kwargs)
```
- When Claude decides to use a tool, this function runs it
- `**kwargs` = pass all named parameters through to the tool function

---

### MODULE 16: src/agent/state.py

**Goal:** Define the shape of data that flows through the agent system.

**Key parts explained:**

```python
class AgentState(TypedDict):
    user_message: str          # What the user said
    user_id: str               # Who said it
    channel_id: str            # Where they said it
    conversation_history: list # Previous messages
    memory_context: str        # What we remember about this user
    rag_context: str           # Relevant old conversations
    rag_enabled: bool          # Is RAG search turned on?
    selected_tools: list       # Which tools Claude chose to use
    tool_results: list         # Results from running those tools
    agent_response: str        # The final response
    iteration_count: int       # How many tool-use rounds so far
    max_iterations: int        # Maximum allowed (prevents infinite loops)
```
- `TypedDict` = a dictionary with a fixed structure
- Like a form with specific fields that must be filled in
- Helps catch bugs: if you misspell a field name, the type checker warns you

---

### MODULE 17: src/agent/context_builder.py

**Goal:** Gather all relevant information before asking Claude to respond.

**Why context matters:**
If you ask Claude "What did we discuss yesterday?" without providing
yesterday's conversation, Claude has no idea. The context builder
gathers everything the AI needs to give a good answer.

```python
class ContextBuilder:
    def __init__(self):
        self.short_term = ShortTermMemory()
        self.long_term = LongTermMemory()
        self.rag_retriever = SemanticRetriever()
```
- Connects to all three sources of information

```python
async def build_context(self, user_id, channel_id, query):
    # 1. Recent conversation (last 10 messages)
    history = self.short_term.get_context(user_id, channel_id)

    # 2. Long-term memory about the user
    memory = self.long_term.read_memory()

    # 3. Search old conversations for relevant info
    rag_results = await self.rag_retriever.retrieve(query)
    rag_context = self.rag_retriever.format_context_for_prompt(rag_results)

    return {
        "conversation_history": history.messages[-10:],
        "memory_context": memory[:1000],
        "rag_context": rag_context,
    }
```
- Combines 3 sources into one context package
- Limits: 10 recent messages, 1000 chars of memory, top-5 search results
- These limits prevent the context from getting too large (Claude has token limits)

---

### MODULE 18: src/memory/manager.py

**Goal:** Coordinate short-term and long-term memory together.

```python
class MemoryManager:
    def __init__(self):
        self.short_term = ShortTermMemory()
        self.long_term = LongTermMemory()
```

```python
async def store_interaction(self, user_id, channel_id, user_message, bot_response):
    # Save to short-term (in-memory, fast, temporary)
    self.short_term.add_message(user_id, channel_id, "user", user_message)
    self.short_term.add_message(user_id, channel_id, "assistant", bot_response)

    # Save to long-term (on disk, permanent)
    self.long_term.write_daily_log(f"User {user_id}: {user_message}\nBot: {bot_response}")
```
- Every conversation is saved in BOTH places
- Short-term = fast lookup for current conversation
- Long-term = permanent record for future reference

---

### MODULE 19: src/memory/short_term.py

**Goal:** Remember the current conversation (like human short-term memory).

**Why this exists:**
When chatting with someone, you remember what was said 5 minutes ago.
Short-term memory does the same for the bot - it keeps track of the
current conversation so responses make sense in context.

```python
class ShortTermMemory:
    def __init__(self):
        self.contexts = {}  # Dictionary: "user:channel" -> ConversationContext
```
- Stored in memory (RAM) - fast but lost when bot restarts
- Each user+channel combo has its own conversation context

```python
def add_message(self, user_id, channel_id, role, content):
    key = f"{user_id}:{channel_id}"
    context = self.get_context(user_id, channel_id)
    context.messages.append({
        "role": role,         # "user" or "assistant"
        "content": content,
        "timestamp": datetime.now().isoformat()
    })
```
- `role` = who said it ("user" = human, "assistant" = bot)
- Messages are stored in order (like a chat log)

---

### MODULE 20: src/memory/long_term.py

**Goal:** Remember things permanently (like writing notes in a notebook).

**Why this exists:**
Short-term memory is lost when the bot restarts. Long-term memory
saves important information to files on disk.

Two file types:
1. **MEMORY.md** - Curated important facts (like a personal notebook)
2. **Daily logs** (YYYY-MM-DD.md) - Everything that happened each day

```python
def write_to_memory(self, content, mode="append"):
    memory_file = self.base_path / "MEMORY.md"
    if mode == "append":
        with open(memory_file, "a") as f:
            f.write(f"\n[{datetime.now().isoformat()}] {content}")
    else:
        with open(memory_file, "w") as f:
            f.write(content)
```
- `mode="append"` = add to end of file (don't erase what's there)
- `mode="overwrite"` = replace entire file
- Timestamps every entry so you know when things were remembered

```python
def write_daily_log(self, content):
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = self.base_path / f"{today}.md"
```
- Creates one file per day: `2026-02-09.md`
- All interactions from that day go into that file

---

### MODULE 21: src/memory/schemas.py

**Goal:** Define the exact shape of memory data (like a database schema).

```python
class MemoryEntry(BaseModel):
    id: str                              # Unique identifier
    content: str                         # The actual memory text
    timestamp: datetime = Field(default_factory=datetime.now)  # When it was created
    source: str                          # Where it came from ("conversation", "daily_log")
    metadata: dict = Field(default_factory=dict)               # Extra info
    importance: int = Field(default=3, ge=1, le=5)             # 1=low, 5=critical
```
- `BaseModel` (from Pydantic) = validates data automatically
- `Field(default=3, ge=1, le=5)` = default is 3, must be between 1 and 5
- `ge` = "greater than or equal", `le` = "less than or equal"
- If you try to set importance=10, Pydantic raises an error

---

### MODULE 22: src/memory/retriever.py

**Goal:** Search across all memory stores to find relevant information.

```python
class MemoryRetriever:
    def search(self, query, user_id=None, channel_id=None):
        results = []

        # Search short-term memory
        if user_id and channel_id:
            context = self.short_term.get_context(user_id, channel_id)
            for msg in context.messages:
                if query.lower() in msg["content"].lower():
                    results.append({"source": "short_term", "content": msg["content"]})

        # Search long-term memory
        memory = self.long_term.read_memory()
        if memory and query.lower() in memory.lower():
            results.append({"source": "long_term", "content": memory})

        # Search daily logs
        for log_date in self.long_term.get_all_daily_logs():
            log = self.long_term.read_daily_log(log_date)
            if log and query.lower() in log.lower():
                results.append({"source": "daily_log", "content": log, "date": log_date})

        return results
```
- Simple keyword search across all memory types
- Searches: current conversation, permanent memory file, and all daily logs
- Returns a list of matches with their source

---

### MODULE 23: src/rag/store.py

**Goal:** Store text as mathematical vectors for smart searching.

**What is a Vector Store?**
Normal search = exact word matching ("python" finds "python" but not "programming")
Vector search = meaning matching ("python" also finds "coding language" and "programming")

```python
class VectorStore:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=settings.chroma_persist_directory)
        self.collection = self.client.get_or_create_collection(
            name="slack_conversations",
            metadata={"hnsw:space": "cosine"}
        )
```
- **ChromaDB** = a database designed for vector search
- `PersistentClient` = saves to disk (survives restarts)
- `cosine` = measures how similar two vectors are (0 = opposite, 1 = identical)
- `HNSW` = algorithm for fast approximate nearest neighbor search

```python
def add_documents(self, documents, metadatas, ids):
    self.collection.add(documents=documents, metadatas=metadatas, ids=ids)
```
- ChromaDB automatically converts text to vectors using a built-in model
- `metadatas` = extra info attached to each document (channel_id, user, etc.)
- `ids` = unique identifier for each document (for updating/deleting later)

```python
def query(self, query_text, n_results=5, where=None):
    return self.collection.query(query_texts=[query_text], n_results=n_results, where=where)
```
- "Find the 5 most similar documents to this query"
- `where={"channel_id": "C123"}` = only search in a specific channel

---

### MODULE 24: src/rag/indexer.py

**Goal:** Take Slack messages and store them in the vector database.

**What is "indexing"?**
Like creating an index in a book - you process the content once so
it can be found quickly later.

```python
class ConversationIndexer:
    async def index_messages(self, channel_id, messages):
        documents = []
        metadatas = []
        ids = []

        for msg in messages[:self.message_limit]:
            text = msg.get("text", "").strip()
            if not text:
                continue
            documents.append(text)
            metadatas.append({"channel_id": channel_id, "user": msg.get("user", ""), ...})
            ids.append(f"{channel_id}_{msg['ts']}")

        self.vector_store.add_documents(documents=documents, metadatas=metadatas, ids=ids)
        return len(documents)
```
- Takes a list of Slack messages
- Extracts the text and metadata from each
- Stores them in the vector database for future searching
- `message_limit` (200) prevents indexing too many messages at once

```python
async def reindex_channel(self, channel_id, messages):
    self.vector_store.delete_by_channel(channel_id)
    return await self.index_messages(channel_id, messages)
```
- Deletes old data for a channel, then re-indexes fresh
- Useful when messages are edited or deleted

---

### MODULE 25: src/rag/retriever.py

**Goal:** Search the vector database and format results for the AI.

```python
class SemanticRetriever:
    async def retrieve(self, query, channel_id=None, n_results=5):
        where = {"channel_id": channel_id} if channel_id else None
        results = self.vector_store.query(query, n_results=n_results, where=where)

        filtered = []
        for i, doc in enumerate(results["documents"][0]):
            distance = results["distances"][0][i]
            similarity = 1 - distance
            if similarity >= 0.7:  # Only keep relevant results
                filtered.append({"text": doc, "similarity": similarity, ...})
        return filtered
```
- Queries the vector store for similar messages
- **Similarity threshold (0.7)**: Only returns results that are at least 70% similar
- Prevents returning irrelevant results

```python
def format_context_for_prompt(self, results):
    if not results:
        return ""
    context = "# Relevant Past Conversations\n\n"
    for r in results:
        context += f"- (similarity: {r['similarity']:.2f}) {r['text']}\n"
    return context
```
- Formats search results into text that Claude can read
- Shows the similarity score so Claude knows how relevant each result is

---

### MODULE 26: src/mcp_servers/ (registry, slack_server, github_client, notion_client)

**Goal:** Connect the bot to external services (GitHub, Notion, etc.)

**What is MCP?**
MCP (Model Context Protocol) is a standard way for AI to interact with
external tools. Think of it as "USB ports for AI" - a universal way to
plug in different services.

**registry.py** - Keeps track of all available MCP connections:
```python
class MCPRegistry:
    def __init__(self):
        self.github = GitHubMCPClient()
        self.notion = NotionMCPClient()
```

**slack_server.py** - Makes Slack features available as MCP tools:
```python
@mcp.tool()
async def get_channel_messages(channel_id: str, hours: int = 24) -> str:
    """Get recent messages from a Slack channel."""
    ...
```
- `@mcp.tool()` = decorator that registers this function as an MCP tool
- AI can call this tool to read Slack messages

**github_client.py** - GitHub integration:
```python
class GitHubMCPClient:
    async def create_issue(self, repo, title, body, labels=None):
        """Create a GitHub issue."""
```
- AI can create GitHub issues from Slack conversations
- Currently a placeholder (Phase 5)

**notion_client.py** - Notion integration:
```python
class NotionMCPClient:
    async def create_page(self, parent_id, title, content):
        """Create a Notion page."""
```
- AI can create Notion pages from Slack conversations
- Currently a placeholder (Phase 5)

---

### How Everything Connects (The Big Picture)

```
USER types in Slack
       |
       v
[Slack sends event to Bot]
       |
       v
[MIDDLEWARE CHAIN]
  auth.py        --> Is this request legit?
  rate_limit.py  --> Too many requests?
  error_handler.py --> Catch any errors
       |
       v
[LISTENERS - "The Ears"]
  messages.py    --> Regular messages
  commands.py    --> /slash commands
  mentions.py    --> @bot mentions
       |
       v
[MESSAGE SERVICE - "The Hands"]
  message_service.py --> Send replies, add reactions
       |
       v
[AGENT ORCHESTRATOR - "The Brain"]
  orchestrator.py --> Decides what to do
       |
       v
[CONTEXT BUILDER - "The Memory Recall"]
  context_builder.py --> Gathers all relevant info
       |
   +---+---+---+
   |       |       |
   v       v       v
[SHORT]  [LONG]  [RAG]
memory   memory  search
   |       |       |
   +---+---+---+
       |
       v
[CLAUDE AI - "The Thinker"]
  Processes message with full context
  May use TOOLS (GitHub, Notion, Slack)
       |
       v
[RESPONSE sent back to user in Slack]
```

---

### Development Phases (What's Done, What's Coming)

| Phase | Name                  | Status       | What it does                                    |
|-------|-----------------------|--------------|-------------------------------------------------|
| 1     | Foundation            | Done         | Project structure, config, logging, exceptions  |
| 2     | Slack Integration     | Done         | Listeners, commands, middleware, message service |
| 3     | Memory System         | Done         | Short-term, long-term, retriever                |
| 4     | RAG System            | Done         | Vector store, indexer, semantic retriever        |
| 5     | MCP Servers           | Partial      | Registry ready, GitHub/Notion are placeholders  |
| 6     | Agent System          | Partial      | Orchestrator ready, needs real tool integration  |
| 7     | Business Logic        | Placeholder  | Summarization, reminders, issue detection       |
| 8     | Advanced Security     | Placeholder  | Token rotation, audit logging                   |
| 9     | Testing & QA          | Done (189)   | Unit tests for all modules                      |
| 10    | Documentation         | This file!   | You're reading it                               |

---

### Glossary (Terms Used in the Code)

| Term                 | Meaning                                                    |
|----------------------|------------------------------------------------------------|
| **async/await**      | Lets code do multiple things at once (not blocking)        |
| **middleware**       | Code that runs before every request (like a security gate) |
| **factory pattern**  | A function that builds and returns a configured object     |
| **dependency injection** | Passing dependencies in from outside (for testability) |
| **decorator**        | `@something` above a function - adds behavior to it       |
| **TypedDict**        | A dictionary with a fixed set of typed fields              |
| **Pydantic**         | Library that validates data automatically                  |
| **HMAC**             | Hash-based Message Authentication Code (security)          |
| **RAG**              | Retrieval Augmented Generation (search + AI)               |
| **MCP**              | Model Context Protocol (standard way AI uses tools)        |
| **Vector/Embedding** | Text converted to numbers for similarity search            |
| **ChromaDB**         | Database for storing and searching text vectors            |
| **Socket Mode**      | WebSocket connection to Slack (no public URL needed)       |
| **Slack Bolt**       | Framework for building Slack bots (by Slack)               |
| **AsyncApp**         | Async version of Slack Bolt's App class                    |
