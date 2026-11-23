# Project Structure - Every File & Folder Explained

This document explains **every file and folder** in the project:
what it is, why it exists, and when it gets used.

---

## The Complete File Tree

```
open_claw_proj/
|
|-- .env                        # Your secret keys (never shared)
|-- .env.example                # Template showing what keys you need
|-- .gitignore                  # Tells Git which files to NOT track
|-- pyproject.toml              # Project settings + list of all packages needed
|-- README.md                   # Project overview for anyone who visits the repo
|-- ARCHITECTURE.md             # System design documentation
|-- SECURITY.md                 # Security practices documentation
|-- BUILD_SUMMARY.md            # Build and setup summary
|-- GUIDE.md                    # Beginner's guide (how to run + module docs)
|-- PROJECT_STRUCTURE.md        # This file!
|
|-- .venv/                      # Virtual environment (auto-generated, never edit)
|-- .github/                    # GitHub-specific config (CI/CD, templates)
|-- memory_store/               # Where the bot saves memories to disk
|
|-- config/                     # All configuration files
|   |-- __init__.py
|   |-- settings.py             # Loads environment variables
|   |-- logging.yaml            # Controls how logs look and where they go
|   |-- prompts/
|       |-- system_prompt.txt   # The AI's personality/instructions
|
|-- src/                        # ALL source code lives here
|   |-- __init__.py
|   |-- main.py                 # Entry point - starts the bot
|   |-- app.py                  # Assembles all the pieces into one app
|   |
|   |-- utils/                  # Shared helper tools
|   |   |-- __init__.py
|   |   |-- logger.py           # Logging setup
|   |   |-- exceptions.py       # Custom error types
|   |   |-- security.py         # Security utilities
|   |   |-- validators.py       # Input checking/sanitization
|   |
|   |-- slack/                  # Everything Slack-related
|   |   |-- __init__.py
|   |   |-- listeners/          # Receives events from Slack
|   |   |   |-- __init__.py
|   |   |   |-- messages.py     # Handles regular messages
|   |   |   |-- commands.py     # Handles /slash commands
|   |   |   |-- mentions.py     # Handles @bot mentions
|   |   |-- middleware/         # Security checks on every request
|   |   |   |-- __init__.py
|   |   |   |-- auth.py         # Authentication check
|   |   |   |-- rate_limit.py   # Spam prevention
|   |   |   |-- error_handler.py# Catches errors gracefully
|   |   |-- services/           # Actions the bot can perform
|   |   |   |-- __init__.py
|   |   |   |-- message_service.py  # Send/read/update messages
|   |   |-- formatters/         # Message formatting helpers
|   |       |-- __init__.py
|   |
|   |-- agent/                  # The AI brain
|   |   |-- __init__.py
|   |   |-- orchestrator.py     # Coordinates AI thinking
|   |   |-- tools.py            # External actions AI can take
|   |   |-- state.py            # Data shape for agent processing
|   |   |-- context_builder.py  # Gathers context for AI
|   |
|   |-- memory/                 # Remembering past conversations
|   |   |-- __init__.py
|   |   |-- manager.py          # Coordinates all memory types
|   |   |-- short_term.py       # Current conversation (in RAM)
|   |   |-- long_term.py        # Permanent memory (on disk)
|   |   |-- schemas.py          # Data shapes for memory entries
|   |   |-- retriever.py        # Searches across all memory
|   |
|   |-- rag/                    # Smart search through old messages
|   |   |-- __init__.py
|   |   |-- store.py            # Vector database (ChromaDB)
|   |   |-- indexer.py          # Puts messages into the database
|   |   |-- retriever.py        # Searches the database
|   |   |-- embeddings.py       # Converts text to numbers
|   |
|   |-- mcp_servers/            # Connections to external services
|   |   |-- __init__.py
|   |   |-- registry.py         # Lists all available connections
|   |   |-- slack_server.py     # Slack as an MCP tool
|   |   |-- github_client.py    # GitHub integration
|   |   |-- notion_client.py    # Notion integration
|   |
|   |-- services/               # Business logic
|       |-- __init__.py
|       |-- summarization.py    # AI-powered message summarization
|
|-- tests/                      # All tests live here
|   |-- __init__.py
|   |-- conftest.py             # Shared test setup (fixtures, env vars)
|   |-- unit/                   # Unit tests (test one thing at a time)
|   |   |-- __init__.py
|   |   |-- test_agent/         # Tests for src/agent/
|   |   |-- test_memory/        # Tests for src/memory/
|   |   |-- test_rag/           # Tests for src/rag/
|   |   |-- test_slack/         # Tests for src/slack/
|   |   |-- test_utils/         # Tests for src/utils/
|   |-- integration/            # Integration tests (test pieces together)
|       |-- __init__.py
```

---

## PART 1: Root-Level Files

These sit in the top-level project folder. They configure the entire project.

---

### .env

```
Type: Environment file (no extension = hidden file convention)
Created by: YOU (manually, by copying .env.example)
Used when: Every time the bot starts - Python reads this to get your secret keys
```

**What it is:**
A plain text file holding all your secret passwords, tokens, and API keys.
Each line is a `KEY=VALUE` pair.

**Why it exists:**
You NEVER put passwords directly in code. If you did, anyone who reads
your code would see your passwords. Instead, passwords go in `.env` and
your code reads them at startup. The `.env` file is in `.gitignore` so
it never gets uploaded to GitHub.

**In this project:**
Holds Slack tokens, Anthropic API key, OpenAI key, GitHub token, Notion token,
and settings like environment mode and log level.

---

### .env.example

```
Type: Template file
Created by: Developer (you or the project creator)
Used when: Only once - when setting up the project for the first time
```

**What it is:**
A copy of `.env` but with FAKE placeholder values instead of real secrets.

**Why it exists:**
Since `.env` is hidden from Git, new developers need to know WHAT variables
are needed. This file shows every variable name with a description of
where to get the real value.

**In this project:**
Shows all 20+ variables the bot needs, organized by section (Slack, Anthropic,
OpenAI, GitHub, Notion, Database, Redis, RAG, Security, Memory).

---

### .gitignore

```
Type: Git configuration file
Created by: Developer (once, at project start)
Used when: Every time you run any Git command (add, commit, push, etc.)
```

**What it is:**
A list of file patterns that Git should completely ignore. These files
will never be tracked, committed, or pushed to GitHub.

**Why it exists:**
Some files should NEVER be in Git:
- `.env` (contains secrets)
- `__pycache__/` (auto-generated, different on every computer)
- `.venv/` (huge, can be recreated with `poetry install`)
- `memory_store/` (contains user data)
- `*.log` (logs are local to each machine)
- `.mypy_cache/` (tool cache, auto-generated)

Without `.gitignore`, you'd accidentally upload secrets or gigabytes of
unnecessary files.

**In this project:**
Ignores Python bytecode, virtual environments, secrets, IDE settings,
test caches, type checking caches, memory store data, ChromaDB files,
logs, and temporary files.

---

### pyproject.toml

```
Type: TOML configuration file (Tom's Obvious, Minimal Language)
Created by: Developer + Poetry
Used when: When installing packages (poetry install), running tools (pytest, black, ruff, mypy)
```

**What it is:**
The "master settings file" for the entire Python project. Contains:
1. **Project metadata** (name, version, description)
2. **Dependencies** (what packages are needed to run)
3. **Dev dependencies** (what packages are needed only for development)
4. **Tool settings** (how pytest, black, ruff, mypy should behave)

**Why it exists:**
Before `pyproject.toml`, Python had multiple config files (`setup.py`,
`requirements.txt`, `setup.cfg`, `tox.ini`). Now, everything is in
ONE file. Poetry uses this to manage the project.

**In this project:**
- Lists 14 runtime packages (slack-bolt, anthropic, chromadb, etc.)
- Lists 7 dev packages (pytest, black, ruff, mypy, etc.)
- Configures black for 100-char line width
- Configures pytest to find tests in `tests/` folder
- Configures mypy for strict type checking

---

### README.md

```
Type: Markdown documentation
Created by: Developer
Used when: When someone visits the project on GitHub - this is the first thing they see
```

**What it is:**
The "front page" of your project. Shows project description, how to set it up,
what it does, and how to contribute.

**Why it exists:**
Every project on GitHub needs a README. It's the first thing people read.
Without it, nobody knows what the project does or how to use it.

---

### ARCHITECTURE.md, SECURITY.md, BUILD_SUMMARY.md, GUIDE.md

```
Type: Markdown documentation files
Created by: Developer
Used when: When someone needs to understand the project deeply
```

**What they are:**
- **ARCHITECTURE.md** - System design: how the modules connect, data flow
- **SECURITY.md** - Security practices: how the project stays safe
- **BUILD_SUMMARY.md** - Summary of build/setup process
- **GUIDE.md** - Complete beginner's guide (how to run + every module explained)

**Why they exist:**
Code alone doesn't explain WHY things are built a certain way. These docs
fill that gap. They're like textbooks for the project.

---

## PART 2: Auto-Generated Folders (Don't Edit These)

These folders are created automatically by tools. You never manually
create or edit files inside them.

---

### .venv/

```
Type: Python virtual environment
Created by: poetry install (or python -m venv)
Used when: Every time you run Python code - it uses packages from here
Size: Very large (hundreds of MB)
```

**What it is:**
A complete, isolated copy of Python with all your project's packages installed.

**Why it exists:**
Different projects need different package versions. Project A might need
`slack-bolt 1.20` while Project B needs `slack-bolt 1.18`. Virtual
environments keep each project's packages separate.

**Contains:**
- `Scripts/python.exe` - The Python interpreter for this project
- `Lib/site-packages/` - All installed packages (slack-bolt, anthropic, chromadb, etc.)
- `pyvenv.cfg` - Points to the base Python installation

**Never commit to Git** - it's in `.gitignore` because anyone can recreate it
with `poetry install`.

---

### __pycache__/ (found in many folders)

```
Type: Python bytecode cache
Created by: Python automatically, when you run any .py file
Used when: Python checks here first before re-reading source files (faster startup)
```

**What it is:**
When you run `example.py`, Python compiles it to bytecode (`example.cpython-313.pyc`)
and stores it in `__pycache__/`. Next time, Python loads the faster bytecode
instead of re-reading the source.

**Why it exists:**
Performance. Bytecode loads faster than parsing source code each time.

**The numbers in the filename:**
`settings.cpython-313.pyc` means "settings.py compiled with CPython version 3.13"

**Never edit these** - Python regenerates them automatically. They're in `.gitignore`.

---

### .mypy_cache/, .pytest_cache/, .ruff_cache/

```
Type: Tool caches
Created by: mypy, pytest, ruff (respectively) when you run them
Used when: Tools check here to avoid re-processing unchanged files
```

**What they are:**
- `.mypy_cache/` - MyPy (type checker) remembers which files it already checked
- `.pytest_cache/` - Pytest remembers which tests failed last time
- `.ruff_cache/` - Ruff (linter) remembers which files it already linted

**Why they exist:**
Speed. Re-checking unchanged files wastes time. Caches skip them.

**Never edit these** - all auto-generated, all in `.gitignore`.

---

### memory_store/

```
Type: Data directory
Created by: The bot at runtime (when it saves memories)
Used when: Bot writes memories (MEMORY.md, daily logs) and ChromaDB stores vectors
```

**What it is:**
The bot's "brain storage" on disk. Contains:
- `MEMORY.md` - Curated long-term memories
- `YYYY-MM-DD.md` - Daily interaction logs
- `chroma_db/` - Vector database files for RAG search

**Why it exists:**
Short-term memory (RAM) is lost when the bot restarts. Long-term memory
needs to survive restarts, so it's saved to files on disk.

**Contains `.gitkeep`:**
The folder needs to exist for the bot to work, but its contents are
private user data. `.gitkeep` is an empty file that makes Git track
the folder without tracking its contents. The `.gitignore` has:
```
memory_store/        # Ignore everything inside
!memory_store/.gitkeep  # Except this one file
```

---

## PART 3: config/ Folder

This folder holds everything that configures HOW the bot behaves,
but contains no actual bot logic.

---

### config/__init__.py

```
Type: Python package marker
Created by: Developer
Used when: Whenever Python imports anything from the config/ folder
```

**What it is:**
An empty (or near-empty) file that tells Python: "This folder is a package.
You can import from it."

**Why it exists:**
Without `__init__.py`, Python treats the folder as just a folder, not an
importable package. You wouldn't be able to write `from config.settings import settings`.

**Every `__init__.py` in the project serves this same purpose.** There are
26 of them. Some are completely empty; some import key items for convenience.

---

### config/settings.py

```
Type: Python module
Created by: Developer
Used when: At startup AND throughout the entire application lifetime
```

**What it is:**
Reads all environment variables from `.env` and makes them available
as `settings.variable_name` throughout the entire codebase.

**Why it exists:**
Instead of writing `os.environ.get("SLACK_BOT_TOKEN")` in 20 different files,
you write it once here and every file does `settings.slack_bot_token`.

**Why Pydantic:**
The `Settings` class uses Pydantic which:
- Validates types (ensures a number is really a number)
- Validates formats (ensures bot tokens start with `xoxb-`)
- Provides defaults (if `LOG_LEVEL` not set, defaults to `"INFO"`)
- Fails fast (crashes at startup if a required value is missing, not 20 minutes later)

**In this project:**
Manages 40+ settings for Slack, Anthropic, OpenAI, GitHub, Notion, RAG,
memory, security, database, and Redis.

---

### config/logging.yaml

```
Type: YAML configuration file
Created by: Developer
Used when: At startup - logger.py reads this to set up the logging system
```

**What it is:**
Controls everything about logging:
- **Formatters**: What each log line looks like (timestamp, module name, level, message)
- **Handlers**: Where logs go (console, rotating files, error files)
- **Loggers**: How much detail each module shows (DEBUG for agent, INFO for slack)

**Why YAML not Python:**
Configuration should be separate from code. YAML is easier to read and
edit than Python dictionaries. You can change log levels without touching code.

**Why "rotating" files:**
Without rotation, log files grow forever until your disk is full.
Rotating files: when a file reaches 10MB, start a new one. Keep 5 old files.
Total max: ~50MB of logs.

---

### config/prompts/system_prompt.txt

```
Type: Plain text file
Created by: Developer
Used when: When the AI agent processes a message - this text is sent as the "system prompt"
```

**What it is:**
Instructions that tell Claude (the AI) WHO it is and HOW to behave.
Like a job description for the AI.

**Why it exists:**
The system prompt shapes the AI's personality and capabilities. Keeping it
in a separate file (not hardcoded in Python) means you can tweak the AI's
behavior without changing any code.

**In this project:**
Tells Claude it's a Slack assistant, lists its tools (Slack, GitHub, Notion),
defines its personality (friendly, concise), and sets guidelines for
summarization, issue creation, and memory usage.

---

## PART 4: src/ Folder (All Source Code)

This is where ALL the actual application code lives.

---

### src/__init__.py

```
Package marker - makes src/ importable.
```

### src/main.py

```
Type: Entry point / startup script
Used when: You start the bot (python -m src.main)
```

**Purpose:** The very first file that runs. It:
1. Sets up the Python path
2. Initializes logging
3. Loads configuration
4. Creates the Slack app (calls `app.py`)
5. Starts the server (Socket Mode for dev, HTTP for production)
6. Handles shutdown signals (Ctrl+C)

**Analogy:** The ignition key of a car. It doesn't do much itself, but
it starts everything else.

---

### src/app.py

```
Type: Application factory
Used when: Called by main.py once at startup
```

**Purpose:** Assembles all the pieces into one working application:
1. Creates the Slack Bolt AsyncApp object
2. Attaches middleware (auth, rate limiting, error handling)
3. Attaches event listeners (messages, commands, mentions)
4. Attaches the global error handler

**Analogy:** The assembly line in a factory. Individual parts come in
(middleware, listeners), and a complete app comes out.

**Why a factory function?**
`create_app()` returns a new app each time. This is critical for
testing - you can create a fresh app for each test without leftover
state from previous tests.

---

### src/utils/ (Utility Modules)

These are helper modules used by MANY other modules. They have no
business logic - just tools that make other code easier to write.

---

#### src/utils/logger.py

```
Used when: Imported by every single module in the project
Purpose: Set up and provide loggers
```

Every module does `from src.utils.logger import get_logger` then
`logger = get_logger(__name__)`. This gives each module its own named
logger that can be configured independently.

---

#### src/utils/exceptions.py

```
Used when: Whenever an error happens anywhere in the project
Purpose: Define specific error types so they can be handled differently
```

Instead of generic `Exception("something broke")`, this defines
`ChannelNotFoundError`, `RateLimitError`, `ToolExecutionError`, etc.
The middleware can then show different messages for different errors.

---

#### src/utils/security.py

```
Used when: Middleware checks (every request) + logging (token masking)
Purpose: Verify requests are genuine, prevent abuse, protect secrets
```

Provides: signature verification, token masking for logs, rate limiting,
secure ID generation, sensitive data redaction.

---

#### src/utils/validators.py

```
Used when: Before processing any user input (messages, commands)
Purpose: Check that input data is safe and correctly formatted
```

Validates: Slack channel IDs, user IDs, timestamps, text length,
URL formats. Detects injection attacks (SQL, XSS, command injection).

---

### src/slack/ (Slack Integration Layer)

Everything that talks to Slack, organized by responsibility.

---

#### src/slack/listeners/ (The "Ears")

```
Used when: A Slack event arrives (someone sent a message, typed a command, @mentioned the bot)
Purpose: Receive events and decide what to do
```

- **messages.py** - Fires when any message is posted. Checks: Is it a DM?
  Is the bot mentioned? Is it a bot message (ignore)? Then responds.
- **commands.py** - Fires when someone types `/bot-help`, `/bot-status`,
  `/bot-summarize`, or `/bot-remind`. Must acknowledge within 3 seconds.
- **mentions.py** - Fires when someone types `@BotName` in a channel.
  Strips the @mention, processes the remaining text.

---

#### src/slack/middleware/ (The "Security Guards")

```
Used when: EVERY incoming request, BEFORE it reaches a listener
Purpose: Run checks that apply to all requests
```

Requests flow through middleware in order:

```
Request --> auth.py --> rate_limit.py --> error_handler.py --> Listener
```

- **auth.py** - Verifies the request is legitimate. Blocks bot self-loops.
- **rate_limit.py** - Checks if this user/channel has sent too many requests.
  10/min per user, 30/min per channel.
- **error_handler.py** - Wraps everything in try/except. If a listener crashes,
  this catches the error and sends a friendly message instead of crashing.

---

#### src/slack/services/ (The "Hands")

```
Used when: The bot needs to DO something in Slack (send message, add reaction, etc.)
Purpose: Wrap Slack API calls with validation and error handling
```

- **message_service.py** - Post messages, reply in threads, add reactions,
  schedule messages, delete messages, fetch message history.

**Why a service layer?** Instead of calling `client.chat_postMessage()` directly
in 10 different places, you call `service.post_message()` once. If you need
to change how messages are posted (add logging, validation, etc.), you
change it in ONE place.

---

#### src/slack/formatters/

```
Used when: Before sending rich messages back to Slack
Purpose: Format messages with blocks, attachments, and layouts
```

Currently has only `__init__.py` (placeholder for future rich formatting).

---

### src/agent/ (The AI Brain)

This is where the AI thinking happens. It takes a user message and
produces an intelligent response.

---

#### src/agent/orchestrator.py

```
Used when: A user message needs an AI-powered response
Purpose: Coordinate the entire AI response pipeline
```

The "conductor" that orchestrates:
1. Build context (memories + past conversations)
2. Send to Claude with tools available
3. If Claude uses a tool, execute it and send the result back
4. Return the final text response

---

#### src/agent/tools.py

```
Used when: Claude decides to take an action (read messages, create issue, etc.)
Purpose: Register and execute external tools the AI can use
```

Tools are described in a format Claude understands. When Claude says
"I want to use get_channel_messages with channel_id=C123", this module
finds and executes that function.

---

#### src/agent/state.py

```
Used when: During agent processing - tracks the current state of thinking
Purpose: Define the data shape that flows through the agent pipeline
```

A TypedDict that holds: user message, user ID, channel ID,
conversation history, memory context, RAG context, tool choices,
tool results, and the final response.

---

#### src/agent/context_builder.py

```
Used when: Before sending a message to Claude
Purpose: Gather all relevant information so Claude can give a good response
```

Combines three sources:
1. Short-term memory (recent conversation)
2. Long-term memory (permanent notes)
3. RAG search results (relevant old messages)

---

### src/memory/ (The Memory System)

How the bot remembers things across conversations and restarts.

---

#### src/memory/manager.py

```
Used when: After every interaction (stores it) and before every response (recalls context)
Purpose: Coordinate short-term and long-term memory together
```

The "brain manager" - when a conversation happens, it saves to both
short-term (fast, temporary) and long-term (slow, permanent).

---

#### src/memory/short_term.py

```
Used when: During active conversations
Purpose: Remember what was said in the current conversation
```

Stored in RAM (computer's working memory). Fast but lost on restart.
Each user+channel combination has its own conversation context.

---

#### src/memory/long_term.py

```
Used when: Writing permanent memories and reading them later
Purpose: Save important information that survives bot restarts
```

Writes to files on disk:
- `MEMORY.md` - Curated important facts
- `YYYY-MM-DD.md` - Daily logs of all interactions

---

#### src/memory/schemas.py

```
Used when: When creating or validating memory entries
Purpose: Define the exact shape of memory data
```

Like a form template - ensures every memory entry has an ID, content,
timestamp, source, importance level (1-5), and metadata.

---

#### src/memory/retriever.py

```
Used when: When searching for something across all memory stores
Purpose: Search short-term, long-term, and daily logs in one call
```

A unified search that looks across all memory types using keyword matching.

---

### src/rag/ (Smart Search)

RAG = Retrieval Augmented Generation. It lets the AI find and use
relevant old conversations when answering questions.

---

#### src/rag/store.py

```
Used when: Adding documents to search index OR searching for similar documents
Purpose: Store and search text using vector similarity (meaning-based search)
```

Wraps ChromaDB (a vector database). Unlike keyword search ("python" only
finds "python"), vector search understands MEANING ("python" also finds
"programming language" and "coding").

---

#### src/rag/indexer.py

```
Used when: Periodically, to index new Slack messages into the search database
Purpose: Take Slack messages and store them so they can be searched later
```

Takes raw messages, extracts the text and metadata, and adds them to
the vector store. Like creating a book's index.

---

#### src/rag/retriever.py

```
Used when: Before the AI responds - to find relevant past conversations
Purpose: Search the vector database and format results for the AI
```

Queries the vector store, filters by relevance (70% similarity threshold),
and formats results as text that Claude can read.

---

#### src/rag/embeddings.py

```
Used when: When text needs to be converted to vectors for storage/search
Purpose: Convert text to numbers using OpenAI's embedding model
```

Uses OpenAI's `text-embedding-3-small` model. "Hello world" becomes
a list of 1536 numbers that represent its meaning. Similar texts get
similar numbers, which is how semantic search works.

---

### src/mcp_servers/ (External Tool Connections)

MCP = Model Context Protocol. A standard way for AI to use external tools.

---

#### src/mcp_servers/registry.py

```
Used when: At startup - registers all available external connections
Purpose: Central catalog of all MCP clients/tools
```

Initializes GitHub and Notion clients and lists what tools are available.

---

#### src/mcp_servers/slack_server.py

```
Used when: When the AI agent needs to interact with Slack
Purpose: Expose Slack operations as MCP-compatible tools
```

Wraps Slack operations (get messages, post message, schedule message,
list channels) in the MCP tool format so the AI can use them.

---

#### src/mcp_servers/github_client.py

```
Used when: When the AI needs to create a GitHub issue or read issues
Purpose: Connect to GitHub's API through MCP
```

Currently a placeholder - will create issues and list issues in Phase 5.

---

#### src/mcp_servers/notion_client.py

```
Used when: When the AI needs to create a Notion page or search
Purpose: Connect to Notion's API through MCP
```

Currently a placeholder - will create pages and search in Phase 5.

---

### src/services/ (Business Logic)

Higher-level features that combine multiple modules to do something useful.

---

#### src/services/summarization.py

```
Used when: /bot-summarize command is invoked
Purpose: Take a list of messages and produce an AI-powered summary
```

Sends messages to Claude with a prompt asking for: main topics,
key decisions, action items, and important questions. Returns
the summary text.

---

## PART 5: tests/ Folder

All test code lives here. Tests verify that the source code works correctly.

---

### tests/conftest.py

```
Type: Pytest configuration file (special name recognized by pytest)
Used when: Before ANY test runs - pytest loads this automatically
Purpose: Set up shared test configuration and reusable test helpers
```

**What it does:**
1. Adds the project root to Python's path
2. Sets fake environment variables (so tests don't need real API keys)
3. Defines shared "fixtures" (pre-built objects that tests can reuse)

**What are fixtures?**
Instead of every test creating its own mock Slack client, `conftest.py`
defines `mock_slack_client()` once. Any test can use it by adding
`mock_slack_client` as a parameter:
```python
async def test_something(mock_slack_client):
    # mock_slack_client is automatically provided by conftest.py
```

---

### tests/unit/ (Unit Tests)

```
Type: Test directory
Used when: You run pytest
Purpose: Test each module in isolation
```

**What "unit" means:**
Each test checks ONE small piece of code. Mocks/fakes replace everything
external (no real API calls, no real database).

The folder structure **mirrors** the `src/` structure:
```
src/agent/orchestrator.py   -->  tests/unit/test_agent/test_orchestrator.py
src/memory/short_term.py    -->  tests/unit/test_memory/test_short_term.py
src/utils/validators.py     -->  tests/unit/test_utils/test_validators.py
```

This convention makes it easy to find the tests for any module.

---

### tests/unit/test_*/ folders

Each subfolder contains `__init__.py` (package marker) and `test_*.py` files.

**Test file naming convention:**
- Files MUST start with `test_` (so pytest can find them)
- Classes MUST start with `Test` (so pytest recognizes them)
- Methods MUST start with `test_` (so pytest runs them)

```python
# tests/unit/test_slack/test_commands.py
class TestHelpCommand:                        # Class starts with "Test"
    async def test_acknowledges_command(self): # Method starts with "test_"
```

---

### tests/integration/

```
Type: Integration test directory
Used when: Testing multiple modules working together
Purpose: Verify modules integrate correctly
```

Currently has only `__init__.py` - placeholder for future integration
tests that will test real Slack connections, actual API calls, etc.

---

## PART 6: Special Files & Patterns

---

### __init__.py (appears 26 times)

```
Purpose: Marks a folder as a Python "package" (importable module)
```

**Without it:**
```python
from src.utils.logger import get_logger  # ERROR: src.utils is not a package
```

**With it:**
```python
from src.utils.logger import get_logger  # Works!
```

Some `__init__.py` files are empty. Some import key items for convenience:
```python
# src/memory/__init__.py might contain:
from .manager import MemoryManager
# Now you can do: from src.memory import MemoryManager
# Instead of: from src.memory.manager import MemoryManager
```

---

### .gitkeep (in memory_store/)

```
Purpose: Force Git to track an empty directory
```

Git doesn't track empty folders. But the bot needs `memory_store/` to exist.
`.gitkeep` is a convention - an empty file whose only job is to make Git
track the folder.

---

### Files ending in .pyc (in __pycache__/)

```
Purpose: Compiled Python bytecode (faster loading)
Pattern: filename.cpython-313.pyc = filename.py compiled with Python 3.13
```

Never edit, never commit. Automatically regenerated.

---

## Quick Reference: "When Does Each File Run?"

| When                    | Files involved                                      |
|-------------------------|-----------------------------------------------------|
| You type `poetry install` | `pyproject.toml` (reads dependencies)             |
| You type `python -m src.main` | `main.py` -> `settings.py` -> `logging.yaml` -> `app.py` -> all listeners + middleware |
| A Slack message arrives | `auth.py` -> `rate_limit.py` -> `error_handler.py` -> `messages.py` |
| A /slash command arrives | `auth.py` -> `rate_limit.py` -> `error_handler.py` -> `commands.py` |
| Bot needs AI response   | `orchestrator.py` -> `context_builder.py` -> `short_term.py` + `long_term.py` + `retriever.py` |
| Bot saves a conversation | `manager.py` -> `short_term.py` + `long_term.py`  |
| RAG search happens      | `retriever.py` (rag) -> `store.py` -> `embeddings.py` |
| You type `pytest`       | `conftest.py` -> all `test_*.py` files              |
| You type `black .`      | `pyproject.toml` [tool.black] section               |
| You type `ruff check .` | `pyproject.toml` [tool.ruff] section                |
| You type `mypy src/`    | `pyproject.toml` [tool.mypy] section                |
