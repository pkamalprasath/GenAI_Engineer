# 🤖 Slack Bot Assistant with Agent System

> ✅ **Status:** All features tested and working | Test Suite: 11/11 PASSING
> 🚀 **Ready for:** End-to-end testing with real Slack workspace

An intelligent Slack bot assistant built with agent-based architecture, RAG knowledge base, and MCP integrations. This project serves as both a production-ready bot and an educational tutorial for building sophisticated AI-powered Slack applications.

## 📚 Documentation

**Start Here:**
- 🚀 [QUICK_START.md](QUICK_START.md) — Get running in 5 minutes
- ✅ [docs/guides/E2E_TESTING_GUIDE.md](docs/guides/E2E_TESTING_GUIDE.md) — Complete testing checklist
- 🔧 [docs/development/FIXES_SUMMARY.md](docs/development/FIXES_SUMMARY.md) — All features & recent fixes
- 🐛 [docs/development/PROBLEMS.md](docs/development/PROBLEMS.md) — Known issues (all resolved)
- 📊 [docs/development/TEST_RESULTS.md](docs/development/TEST_RESULTS.md) — Integration test report

## ✨ What's New

### Recent Updates (2026-02-17)

✅ **All Critical Issues Fixed:**
- Fixed all agent Slack tools (Problem #13 - MCP import issue)
- Added missing agent tools: `summarize_channel`, `list_channels`, `get_channel_info`, `list_github_issues`
- Shared MemoryManager instance (conversation history now works)
- Added 4 background jobs: reminder delivery, RAG indexing, cleanup, heartbeat
- Fixed `/bot-remind` to use ReminderService
- Added labels support for GitHub issues

🧪 **Fully Tested:**
- 11/11 integration tests passing
- All functionalities verified with sample data
- Ready for end-to-end testing with real Slack workspace

📖 **See:** [docs/development/FIXES_SUMMARY.md](docs/development/FIXES_SUMMARY.md) for complete changelog

---

## ⚡ Features

### Core Capabilities
- 📝 **Channel Summarization**: AI-powered summaries via agent or slash command
- ⏰ **Smart Reminders**: Schedule, list, cancel reminders (auto-delivered every 60s)
- 📅 **Scheduled Messages**: Post messages at specific times
- 🐛 **Issue Detection**: Auto-detect bugs and create GitHub tickets with labels
- 📚 **Notion Integration**: Create formatted pages from Slack conversations

### Technical Architecture
- 🧠 **Agent System**: LangGraph-based ReAct agent for intelligent task execution
- 🔍 **RAG Knowledge Base**: ChromaDB vector store with 200 messages per channel
- 🛠️ **MCP Servers**: Slack, GitHub, and Notion integrations via Model Context Protocol
- 💾 **Multi-Layered Memory**: Short-term, working, and file-backed long-term memory
- 🔒 **Security-First**: OAuth 2.1, rate limiting, request validation, token management
- ⚡ **High Performance**: Async/await throughout for maximum throughput

## 🏗️ Architecture

### System Overview

```
User Message → Slack Bolt → Middleware (Auth, Rate Limit) → Agent Orchestrator
                                                                     ↓
                                              ┌──────────────────────┴──────────────────────┐
                                              ↓                                              ↓
                                      Context Builder                                Tool Executor
                                      (Memory + RAG)                              (MCP: Slack/GitHub/Notion)
                                              ↓                                              ↓
                                      Response Generator ← ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘
                                              ↓
                                      Memory Writer (Updates MEMORY.md, daily logs)
                                              ↓
                                      Slack Response
```

### Core Components

1. **Slack Integration Layer**
   - Slack Bolt for Python (async)
   - Event listeners (messages, commands, mentions)
   - Middleware (auth, rate limiting, error handling)
   - Services (message, channel, scheduler)

2. **Agent System** ✅ (Fully Implemented)
   - LangGraph orchestrator with ReAct pattern
   - Tool registry and selection
   - Context builder (memory + RAG + conversation history)
   - Decision maker (RAG relevance logic)

3. **Memory System** (Phase 3 - Coming Soon)
   - Short-term: In-memory conversation context
   - Long-term: File-backed storage (MEMORY.md, daily logs)
   - Profile files (USER.md, SOUL.md, TOOLS.md)
   - Semantic retrieval across memory

4. **RAG Knowledge Base** (Phase 4 - Coming Soon)
   - ChromaDB vector store
   - Conversation indexing (200 messages/channel)
   - Semantic retrieval with HNSW indexing
   - Incremental updates every 2 hours

5. **MCP Servers** (Phase 5 - Coming Soon)
   - Custom Slack MCP server (FastMCP)
   - Official GitHub MCP integration
   - Official Notion MCP integration
   - Tool discovery and execution

## 🚀 Getting Started

### Prerequisites

- Python 3.11 or higher
- Poetry (dependency management)
- Slack workspace with admin access
- API keys: Anthropic, OpenAI, GitHub, Notion

### Installation

1. **Clone the repository**
   ```bash
   cd d:\AI\KrishNaik_Academy\Coding\Vizuara\open_claw_proj
   ```

2. **Install dependencies with Poetry**
   ```bash
   poetry install
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and tokens
   ```

4. **Configure Slack App**
   - Go to [api.slack.com/apps](https://api.slack.com/apps)
   - Create a new app
   - Enable Socket Mode (for development)
   - Add required OAuth scopes:
     - `chat:write` - Post messages
     - `channels:read` - Read channel information
     - `channels:history` - Read message history
     - `users:read` - Read user information
     - `reactions:write` - Add reactions
     - `commands` - Slash commands
   - Install app to workspace
   - Copy tokens to .env

5. **Run the bot**
   ```bash
   poetry run python src/main.py
   ```

## 📁 Project Structure

```
open_claw_proj/
├── config/                          # Configuration management
│   ├── settings.py                  # Centralized settings (Pydantic)
│   ├── logging.yaml                 # Structured logging configuration
│   └── prompts/                     # System prompts for agent
│
├── src/                             # Main source code
│   ├── main.py                      # Application entry point
│   ├── app.py                       # Slack Bolt app initialization
│   │
│   ├── agent/                       # Agent system (Phase 6)
│   │   ├── orchestrator.py          # LangGraph agent
│   │   ├── tools.py                 # Tool registry
│   │   ├── context_builder.py       # Context composition
│   │   └── decision_maker.py        # RAG relevance logic
│   │
│   ├── memory/                      # Memory system (Phase 3)
│   │   ├── manager.py               # Memory orchestration
│   │   ├── short_term.py            # In-memory context
│   │   ├── long_term.py             # File-backed storage
│   │   └── retriever.py             # Semantic search
│   │
│   ├── rag/                         # RAG knowledge base (Phase 4)
│   │   ├── indexer.py               # Conversation indexing
│   │   ├── retriever.py             # Semantic retrieval
│   │   ├── embeddings.py            # Embedding generation
│   │   └── store.py                 # Vector store management
│   │
│   ├── mcp_servers/                 # MCP server implementations (Phase 5)
│   │   ├── slack_server.py          # Custom Slack MCP
│   │   ├── github_client.py         # GitHub MCP wrapper
│   │   ├── notion_client.py         # Notion MCP wrapper
│   │   └── registry.py              # MCP server registry
│   │
│   ├── slack/                       # Slack integration layer ✅
│   │   ├── listeners/               # Event handlers
│   │   │   ├── messages.py          # Message events ✅
│   │   │   ├── commands.py          # Slash commands ✅
│   │   │   └── mentions.py          # App mentions ✅
│   │   ├── middleware/              # Request middleware
│   │   │   ├── auth.py              # Authentication ✅
│   │   │   ├── rate_limit.py        # Rate limiting ✅
│   │   │   └── error_handler.py     # Error handling ✅
│   │   ├── services/                # Business logic
│   │   │   ├── message_service.py   # Message operations ✅
│   │   │   ├── channel_service.py   # Channel operations
│   │   │   ├── scheduler_service.py # Message scheduling
│   │   │   └── reminder_service.py  # Reminder management
│   │   └── formatters/
│   │       ├── block_kit.py         # Block Kit UI builders
│   │       └── markdown.py          # Markdown formatters
│   │
│   ├── services/                    # Business logic services (Phase 7)
│   │   ├── summarization.py         # Channel summarization
│   │   ├── issue_detection.py       # Issue pattern detection
│   │   ├── reminder_scheduler.py    # Reminder orchestration
│   │   └── notion_integration.py    # Notion page creation
│   │
│   └── utils/                       # Utilities ✅
│       ├── logger.py                # Logging setup ✅
│       ├── exceptions.py            # Custom exceptions ✅
│       ├── validators.py            # Input validation ✅
│       └── security.py              # Security utilities ✅
│
├── memory_store/                    # File-backed memory (gitignored)
│   ├── MEMORY.md                    # Curated long-term memory
│   ├── USER.md                      # User preferences
│   ├── SOUL.md                      # Bot behavior
│   ├── TOOLS.md                     # Environment notes
│   ├── heartbeat-state.json         # Task state
│   └── memory/
│       └── YYYY-MM-DD.md            # Daily logs
│
├── tests/                           # Test suite (Phase 9)
│   ├── unit/                        # Unit tests
│   ├── integration/                 # Integration tests
│   └── fixtures/                    # Test fixtures
│
├── scripts/                         # Utility scripts
│   ├── setup_vector_store.py       # Initialize ChromaDB
│   ├── index_channels.py           # Bulk channel indexing
│   └── rotate_tokens.py            # Token rotation
│
├── .env.example                     # Environment variables template
├── .gitignore                       # Git ignore patterns
├── pyproject.toml                   # Poetry dependencies ✅
└── README.md                        # This file ✅
```

## 🔧 Configuration

### Environment Variables

See [.env.example](.env.example) for all available configuration options.

Key variables:
- `SLACK_BOT_TOKEN`: Bot User OAuth Token (xoxb-...)
- `SLACK_APP_TOKEN`: App-Level Token for Socket Mode (xapp-...)
- `ANTHROPIC_API_KEY`: Claude API key for agent
- `OPENAI_API_KEY`: OpenAI key for embeddings
- `GITHUB_TOKEN`: GitHub PAT for MCP server
- `NOTION_TOKEN`: Notion integration token

### Logging

Logging is configured in [config/logging.yaml](config/logging.yaml):
- Console output for development
- File rotation (10MB, 5 backups)
- Structured logging for production
- Per-module log levels

## 🛡️ Security Features

### Implemented (Phase 1-2) ✅
- ✅ Request signature verification (automatic via Slack Bolt)
- ✅ Timestamp validation (prevent replay attacks)
- ✅ Rate limiting (10 req/min per user, 30 req/min per channel)
- ✅ Bot loop prevention
- ✅ Input validation and sanitization
- ✅ Injection attack detection
- ✅ Token masking in logs

### Coming Soon (Phase 8)
- 🔜 OAuth 2.1 token management
- 🔜 Automated token rotation
- 🔜 Audit logging
- 🔜 Security monitoring and alerts

## 📚 Available Commands

### Slash Commands
- `/bot-help` - Show available commands and usage
- `/bot-status` - Check bot health and capabilities
- `/bot-summarize #channel [time]` - Summarize channel messages
- `/bot-remind [message] in [time]` - Schedule a reminder

### Usage Examples
```
/bot-summarize #general 24h
/bot-remind Send email in 5 minutes
```

### Direct Interaction
- **DM the bot**: Send a direct message for private conversation
- **@ mention**: @YourBot in any channel to get the bot's attention

## 🔨 Development

### Project Status

| Phase | Component | Status |
|-------|-----------|--------|
| Phase 1 | Project Foundation | ✅ Complete |
| Phase 2 | Slack Integration | 🟡 In Progress |
| Phase 3 | Memory System | ⏳ Pending |
| Phase 4 | RAG Knowledge Base | ⏳ Pending |
| Phase 5 | MCP Servers | ⏳ Pending |
| Phase 6 | Agent System | ⏳ Pending |
| Phase 7 | Business Logic | ⏳ Pending |
| Phase 8 | Security Features | ⏳ Pending |
| Phase 9 | Testing | ⏳ Pending |
| Phase 10 | Documentation | ⏳ Pending |

### Running Tests

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=src

# Run specific test file
poetry run pytest tests/unit/test_agent/test_orchestrator.py
```

### Code Quality

```bash
# Format code with Black
poetry run black src/

# Lint with Ruff
poetry run ruff check src/

# Type check with MyPy
poetry run mypy src/
```

## 🏫 Educational Notes

This project is designed to be educational. Key learning points:

### Architecture Patterns
- **Factory Pattern**: App initialization (testable, configurable)
- **Service Layer**: Separation of concerns (business logic vs API)
- **Middleware Pattern**: Cross-cutting concerns (auth, logging, rate limiting)
- **Dependency Injection**: Testable, modular components

### Best Practices
- **Type Hints**: Full type annotations for clarity and safety
- **Async/Await**: High-performance async operations
- **Error Handling**: Custom exceptions with clear error messages
- **Logging**: Structured logging with proper levels
- **Security**: Input validation, sanitization, rate limiting
- **Testing**: Comprehensive unit and integration tests

### Slack Bolt Concepts
- **Event Listeners**: @app.event() decorator pattern
- **Middleware**: Global and listener-specific middleware
- **Async Handlers**: High-throughput event processing
- **Error Handling**: Global and middleware error handlers

## 📖 Documentation

### Getting Started
- **README.md** (this file): Project overview and getting started
- **QUICK_START.md**: Setup in 5 minutes
- **FOLDER_STRUCTURE.md**: Directory organization and file guide

### Technical Documentation
- **ARCHITECTURE.md** (Phase 10): Detailed technical architecture
- **SECURITY.md** (Phase 10): Security implementation and best practices
- **PROJECT_STRUCTURE.md**: Detailed project structure with phases
- **Inline Comments**: Extensive educational comments in source code

### Learning Materials (`.claude/` folder)
Educational resources for building similar AI-powered Slack bots:

**Rules & Guidelines:**
- `rules/slack-bot-development.md` - 10 critical Slack bot rules
- `rules/fastmcp-integration.md` - FastMCP patterns and gotchas

**Design Patterns:**
- `patterns/shared-state-management.md` - Dependency injection for shared state
- `patterns/error-handling-strategy.md` - Layered error handling architecture
- `patterns/testing-async-services.md` - Testing async Python services

**How-To Guides:**
- `skills/add-agent-tool.md` - Step-by-step: Add a new agent tool
- `skills/add-scheduler-job.md` - Step-by-step: Add periodic background jobs
- `skills/debug-agent-tools.md` - 7-step debugging process for tools

**Developer Workflows:**
- `agents/bug-hunter.md` - Systematic bug discovery methodology
- `agents/integration-tester.md` - Creating integration test suites

**Start here:** Read `.claude/README.md` for a guide to all learning materials.

### Issue Tracking
- **PROBLEMS.md**: Known issues tracker (all resolved ✅)
- **FIXES_SUMMARY.md**: Complete changelog of all fixes
- **TEST_RESULTS.md**: Integration test report (11/11 passing)

## 🤝 Contributing

This is an educational project. Contributions are welcome! Follow these steps:

### Development Setup
1. Clone the repository
2. Install dependencies: `poetry install`
3. Copy `.env.example` to `.env` and configure
4. Read [docs/architecture/FOLDER_STRUCTURE.md](docs/architecture/FOLDER_STRUCTURE.md) to understand project layout

### Development Workflow
1. Create a feature branch: `git checkout -b feature/your-feature`
2. Make your changes following the patterns in `.claude/`
3. Write tests alongside your code
4. Run tests: `pytest tests/`
5. Commit with clear messages
6. Submit a pull request with a description of changes

### Code Standards
- **Type Hints**: Use full type annotations
- **Docstrings**: Add docstrings to all functions
- **Testing**: Write tests for new features
- **Error Handling**: Follow layered error handling pattern
- **Logging**: Use appropriate log levels
- **References**: Check `.claude/rules/` before implementing

### Adding Features
Detailed how-to guides available:
- Adding a tool: See `.claude/skills/add-agent-tool.md`
- Adding a job: See `.claude/skills/add-scheduler-job.md`
- Debugging tools: See `.claude/skills/debug-agent-tools.md`

### Reporting Issues
1. Check [docs/development/PROBLEMS.md](docs/development/PROBLEMS.md) for known issues
2. Create an issue with:
   - Clear title and description
   - Steps to reproduce
   - Expected vs actual behavior
   - Your environment (Python version, OS, etc.)
3. If it's a bug fix, reference this issue in your PR

## 📝 License

MIT License - See LICENSE file for details

## 🔐 Security

For security vulnerabilities, please email security@example.com instead of using the issue tracker.

See [docs/security/SECURITY.md](docs/security/SECURITY.md) for detailed security implementation details.

## 🙏 Acknowledgments

- **Slack Bolt for Python**: Official Slack framework
- **LangGraph**: Agent orchestration
- **Anthropic Claude**: AI agent capabilities
- **FastMCP**: Model Context Protocol implementation
- **ChromaDB**: Vector store for RAG

## 📞 Support

For issues, questions, or contributions, please open an issue on GitHub.

---

**Built with ❤️ as an educational tutorial for building production-grade Slack bots**
