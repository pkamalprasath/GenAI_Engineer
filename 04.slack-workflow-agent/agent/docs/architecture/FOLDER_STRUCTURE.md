# Project Folder Structure

> This document explains the organization of the Slack Bot Assistant project. Perfect for developers contributing to the repository.

---

## Root Level Files

```
open_claw_proj/
├── README.md                 # Main project documentation (START HERE)
├── QUICK_START.md            # 5-minute setup guide
├── FOLDER_STRUCTURE.md       # This file - directory organization
├── pyproject.toml            # Python project configuration (Poetry)
├── .env.example              # Environment variables template
├── .gitignore                # Git ignore rules
└── .env                       # (NOT committed) Local environment variables
```

---

## Directory Structure

### `.claude/` - Claude Code Learning Materials
Developer knowledge base and patterns discovered during development.

```
.claude/
├── README.md                          # How to use this knowledge base
├── agents/
│   ├── integration-tester.md          # Integration testing patterns
│   └── bug-hunter.md                  # Systematic bug discovery
├── skills/
│   ├── add-agent-tool.md              # How to add new tools
│   ├── add-scheduler-job.md           # How to add periodic jobs
│   └── debug-agent-tools.md           # Debug tool issues
├── patterns/
│   ├── shared-state-management.md     # Dependency injection patterns
│   ├── error-handling-strategy.md     # Layered error handling
│   └── testing-async-services.md      # Testing async code
└── rules/
    ├── slack-bot-development.md       # 10 critical Slack bot rules
    └── fastmcp-integration.md         # FastMCP gotchas and patterns
```

**Purpose:** Educational materials. Reference when building similar projects.

---

### `src/` - Application Source Code
Main application logic and bot implementation.

```
src/
├── main.py                            # Entry point - starts the bot
├── app.py                             # Flask/Slack Bolt app initialization
│
├── agent/                             # AI Agent & Tool System
│   ├── __init__.py
│   ├── orchestrator.py                # Main agent brain (ReAct pattern)
│   ├── context_builder.py             # Builds context for agent prompts
│   ├── tools.py                       # All tool implementations (15+ tools)
│   └── memory.py                      # Conversation memory management
│
├── slack/                             # Slack Event Handlers
│   ├── listeners/
│   │   ├── messages.py                # Handle direct messages (DMs)
│   │   ├── commands.py                # Handle slash commands (/bot-*)
│   │   └── mentions.py                # Handle @mentions and reactions
│   └── middleware/
│       └── auth.py                    # Slack request authentication
│
├── services/                          # Business Logic Services
│   ├── summarization.py               # AI-powered summarization
│   ├── issue_detection.py             # Bug/issue detection
│   ├── reminder.py                    # Reminder scheduling & delivery
│   └── __init__.py
│
├── rag/                               # RAG (Retrieval-Augmented Generation)
│   ├── indexer.py                     # ChromaDB vector store indexing
│   └── retriever.py                   # Semantic search retrieval
│
├── utils/                             # Utility Functions
│   ├── slack_helpers.py               # Slack SDK wrappers
│   ├── message_parser.py              # Parse Slack messages
│   └── time_utils.py                  # Time/date utilities
│
└── mcp_servers/                       # MCP Server Implementations
    ├── slack_server.py                # Slack MCP server (external interface)
    ├── github_server.py               # GitHub MCP server
    └── notion_server.py               # Notion MCP server
```

**Key Patterns:**
- `orchestrator.py` - Agent decision-making (ReAct pattern)
- `tools.py` - All agent tools (use Slack SDK directly, not MCP imports)
- `services/` - Business logic (can raise exceptions)
- `listeners/` - Event handlers (must always respond to Slack)

---

### `config/` - Configuration & Settings
Application configuration and secrets management.

```
config/
├── settings.py                        # Pydantic settings (env variables)
├── logging.yaml                       # Logging configuration
└── prompts/                           # AI Prompts
    ├── agent_system.md                # Agent system prompt
    ├── summarization.md               # Summarization prompt
    └── issue_detection.md             # Issue detection prompt
```

**Key Files:**
- `settings.py` - Single source of truth for all configuration
- Validates environment variables at startup (fail-fast pattern)

---

### `memory_store/` - Runtime Data (NOT Committed)
Local storage for user data, reminders, and vector database.

```
memory_store/
├── reminders.json                     # Scheduled reminders (cleared for GitHub)
├── memory/                            # Conversation history
│   └── *.json                         # Per-conversation memory files
├── chroma_db/                         # Vector database
│   └── (ChromaDB persistent storage)
└── agent_state.db                     # SQLite state database (dev only)
```

**Note:** These files contain user data. The `.gitignore` prevents accidental commits.

---

### `logs/` - Application Logs (NOT Committed)
Runtime logs from bot execution.

```
logs/
├── app.log                            # Application logs
└── error.log                          # Error logs
```

**Note:** Cleared before GitHub commits. Logs are generated at runtime.

---

### `tests/` - Test Suite
Automated testing for quality assurance.

```
tests/
├── test_integration.py                # Integration tests (all services)
├── unit/                              # Unit tests
│   ├── test_agent.py
│   ├── test_tools.py
│   ├── test_services.py
│   └── ...
├── integration/                       # Integration tests
│   ├── test_slack_api.py
│   ├── test_orchestrator.py
│   └── ...
└── fixtures/                          # Test data
    ├── sample_messages.py
    ├── mock_slack_responses.py
    └── ...
```

**Run Tests:**
```bash
pytest tests/                          # Run all tests
pytest tests/test_integration.py       # Run integration tests
pytest tests/ -v                       # Verbose output
```

---

### `scripts/` - Utility Scripts
One-off scripts for development and deployment.

```
scripts/
├── setup.sh                           # Initial setup script
├── install_dependencies.sh            # Install packages
├── create_slack_app.sh                # Slack app creation helper
└── deploy.sh                          # Deployment script
```

---

## File Organization by Type

### Documentation Files
```
README.md                              # Main documentation
QUICK_START.md                         # Setup guide (5 minutes)
FOLDER_STRUCTURE.md                    # This file
ARCHITECTURE.md                        # System architecture
PROJECT_STRUCTURE.md                   # Detailed structure
E2E_TESTING_GUIDE.md                   # End-to-end testing
TEST_RESULTS.md                        # Test coverage report
FIXES_SUMMARY.md                       # Bug fixes and improvements
PROBLEMS.md                            # Known issues tracker
```

### Configuration Files
```
pyproject.toml                         # Poetry configuration
.env.example                           # Environment template
config/settings.py                     # Pydantic settings
config/logging.yaml                    # Logger config
```

### Ignore Files (for Git)
```
.gitignore                             # Git ignore rules
.env                                   # Local secrets (not committed)
```

---

## Development Workflow

### 1. Adding a New Tool
1. Implement method in `src/agent/tools.py`
2. Register in `ToolRegistry.__init__()`
3. Add JSON schema for parameters
4. Write tests in `tests/unit/test_tools.py`
5. Reference: `.claude/skills/add-agent-tool.md`

### 2. Adding a Scheduled Job
1. Create job function in `src/app.py`
2. Register with APScheduler
3. Add error handling
4. Log job status on startup
5. Reference: `.claude/skills/add-scheduler-job.md`

### 3. Adding a New Service
1. Create `src/services/new_service.py`
2. Implement business logic
3. Can raise exceptions (caller handles them)
4. Write tests in `tests/unit/test_services.py`
5. Reference in appropriate tool

### 4. Testing Changes
1. Run `pytest tests/`
2. Check coverage: `pytest --cov tests/`
3. Run integration tests: `pytest tests/test_integration.py`
4. Reference: `.claude/patterns/testing-async-services.md`

---

## Key Architecture Patterns

### Error Handling (Layered)
```
Tools (agent-facing)
  ↓ Returns error dicts, never raises
Services (business logic)
  ↓ Can raise exceptions
Listeners (Slack handlers)
  ↓ Catch ALL exceptions, always respond
Background Jobs (APScheduler)
  ↓ Catch ALL exceptions, never crash scheduler
```

### State Management
- **Shared:** `MemoryManager`, database connections (via dependency injection)
- **Per-request:** Request context, temporary variables
- Reference: `.claude/patterns/shared-state-management.md`

### Tool Execution
1. **Registration:** ToolRegistry.tools dict
2. **Invocation:** Agent calls `registry.execute_tool(name, **kwargs)`
3. **Implementation:** Tool method uses Slack SDK directly (NOT MCP imports)
4. **Response:** Always returns dict, never raises
5. Reference: `.claude/skills/debug-agent-tools.md`

---

## Quick Navigation

**New to the project?** Start here:
1. Read `README.md`
2. Follow `QUICK_START.md`
3. Read `src/app.py` to understand structure
4. Check `.claude/README.md` for patterns

**Adding a feature?**
1. Check `.claude/skills/` for how-to guides
2. Review `.claude/rules/slack-bot-development.md`
3. Look at existing implementations in `src/`
4. Write tests in `tests/`

**Debugging an issue?**
1. Check `PROBLEMS.md` for known issues
2. Use `.claude/skills/debug-agent-tools.md`
3. Run `pytest tests/test_integration.py`
4. Check logs in `logs/` directory

**Contributing?**
1. Follow patterns in `.claude/patterns/`
2. Follow rules in `.claude/rules/`
3. Add tests alongside your changes
4. Update `PROBLEMS.md` if you find bugs

---

## Statistics

- **Source files:** 20+ Python modules
- **Tools:** 15+ agent tools
- **Services:** 4 business logic services
- **Tests:** 11 integration tests
- **Documentation:** 10+ markdown files
- **Rules & Patterns:** 8 learning documents

---

## Important Notes

1. **Never commit:**
   - `.env` file (contains API keys)
   - `logs/` directory (runtime logs)
   - `memory_store/` directory (user data)
   - Use `.env.example` as template

2. **Always include:**
   - Tests for new features
   - Error handling in tools
   - Docstrings in services
   - Type hints in function signatures

3. **Reference materials:**
   - `.claude/rules/` - Critical guidelines
   - `.claude/patterns/` - Design patterns
   - `.claude/skills/` - Step-by-step guides

---

**Last Updated:** 2026-02-18
**Version:** 1.0
**Status:** Production Ready ✅
