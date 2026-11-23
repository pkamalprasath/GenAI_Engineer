# Slack Workflow Agent: code

This folder holds the code. The overview, architecture diagram, tool list, design decisions and limitations are in the [project README](../README.md).

## Setup

Full Slack app setup (scopes, Socket Mode, events, slash commands): [QUICK_START.md](QUICK_START.md).

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e .                 # or: poetry install
cp .env.example .env
python src/main.py
```

| Variable | Required | Purpose |
|---|---|---|
| `SLACK_BOT_TOKEN` | yes | Bot token (`xoxb-...`) |
| `SLACK_APP_TOKEN` | yes | App-level token for Socket Mode (`xapp-...`) |
| `SLACK_SIGNING_SECRET` | yes | Passed to Slack Bolt |
| `ANTHROPIC_API_KEY` | yes | Claude calls (agent loop, summaries, issue detection) |
| `GITHUB_TOKEN` | no | Registers the three GitHub tools |
| `NOTION_TOKEN` | no | Registers the three Notion tools |
| `RATE_LIMIT_PER_USER`, `RATE_LIMIT_PER_CHANNEL` | no | Requests per minute (defaults 10 and 30) |
| `RAG_INDEXING_FREQUENCY`, `RAG_MESSAGE_LIMIT` | no | Indexing interval in seconds (7200) and messages per channel (200) |

All settings, with descriptions, are in [`config/settings.py`](config/settings.py) and [`.env.example`](.env.example). Logging is configured in `config/logging.yaml` (console, plus `logs/app.log` and `logs/error.log`).

## Layout

```
agent/
  src/
    main.py              entry point: logging, then Socket Mode handler
    app.py               Bolt AsyncApp, middleware chain, listeners, APScheduler jobs
    agent/               orchestrator (tool-use loop), tools (16), context builder
    memory/              short-term (in process), long-term (MEMORY.md + memory/YYYY-MM-DD.md)
    rag/                 ChromaDB store, channel indexer, retriever
    mcp_servers/         FastMCP Slack server; GitHub and Notion REST clients; registry
    services/            summarisation, issue detection, reminders, Notion export
    slack/               listeners, middleware (auth, rate limit, errors), message service
    utils/               validators, security helpers, exceptions, logger
  config/                settings, logging config, system prompt
  scripts/               test-channel seeding, manual indexing, vector store setup
  tests/unit/            267 unit tests (pytest tests -q)
  test_integration.py    9 end-to-end checks against the real Claude API (not in CI)
  docs/                  guides and security notes
  .claude/               Claude Code agents, skills, rules and patterns written while building this
```

## Tests

```bash
pip install -e . pytest pytest-asyncio
pytest tests -q
```

## Slash commands

- `/bot-help`: available commands
- `/bot-status`: which integrations are configured
- `/bot-summarize #channel 24h`: Claude summary of recent messages
- `/bot-remind <text> in <time>`: schedule a reminder

DM the bot or @mention it in a channel to use the agent and its tools.
