# Known Problems — Slack Bot Assistant

> This file tracks all identified bugs and integration issues.
> Each problem is marked with a status: `[ ]` = open, `[x]` = resolved.

---

## Problem #5 — CRITICAL: Separate MemoryManager Instances (No Conversation Memory)

- **Status:** [x] RESOLVED
- **Files:** `src/agent/orchestrator.py:115`, `src/agent/context_builder.py:73`
- **Description:**
  Both `AgentOrchestrator` and `ContextBuilder` create their **own** `MemoryManager()` instances.
  Each `MemoryManager` creates its own `ShortTermMemory()` (an in-memory dict).
  The orchestrator stores interactions in one ShortTermMemory, but the context builder
  reads from a completely different one. **Conversation history is always empty.**
- **Impact:** The bot has zero short-term memory. Every message is treated as a brand-new conversation.
- **Fix:** Share a single MemoryManager instance between orchestrator and context builder.

---

## Problem #1 — HIGH: /bot-remind Bypasses ReminderService

- **Status:** [x] RESOLVED
- **Files:** `src/slack/listeners/commands.py:328-431`
- **Description:**
  The `/bot-remind` slash command uses Slack's native `chat_scheduleMessage` API directly,
  completely bypassing the `ReminderService`. This means:
  - Reminders are NOT persisted to `reminders.json`
  - `list_reminders` and `cancel_reminder` agent tools will never find these reminders
  - The entire ReminderService CRUD lifecycle is disconnected from the slash command
- **Impact:** Two separate reminder systems that don't talk to each other. Users can't list or cancel slash-command reminders.
- **Fix:** Rewrote `/bot-remind` to use `ReminderService.schedule_reminder()`. Now shows reminder ID for cancellation.

---

## Problem #7 — HIGH: No Scheduler for execute_due_reminders()

- **Status:** [x] RESOLVED
- **Files:** `src/services/reminder.py:379-442`, `src/app.py`
- **Description:**
  `ReminderService.execute_due_reminders()` is designed to be called every 60 seconds by
  APScheduler, but **no scheduler is actually configured anywhere**. The method is never
  invoked. Reminders created via the agent tool are persisted to `reminders.json` but
  **never delivered**.
- **Impact:** Agent-created reminders silently never fire.
- **Fix:** Added `AsyncIOScheduler` from APScheduler in `src/app.py` with a 60-second interval job.

---

## Problem #3/#4 — MEDIUM: create_github_issue Tool Missing Labels Parameter

- **Status:** [x] RESOLVED
- **Files:** `src/agent/tools.py:227-240`, `src/agent/tools.py:415-426`
- **Description:**
  The `create_github_issue` tool schema does not expose a `labels` property, and the
  `_create_github_issue()` wrapper does not pass labels to `GitHubMCPClient.create_issue()`.
  The underlying client supports labels, and `IssueDetectionService` generates `suggested_labels`,
  but the direct tool path drops them.
  - Via `detect_and_create_issues` → passes labels ✅
  - Via `create_github_issue` → **no labels** ❌
- **Impact:** Agent cannot add labels when creating GitHub issues directly.
- **Fix:** Add `labels` to the tool schema and pass it through in `_create_github_issue()`.

---

## Problem #2 — MEDIUM: Duplicate Message Fetching in Detection Tools

- **Status:** [x] RESOLVED
- **Files:** `src/agent/tools.py:473-505`
- **Description:**
  Both `_detect_issues()` and `_detect_and_create_issues()` independently fetch messages
  from Slack via `get_channel_messages()`. If the agent calls `detect_issues` first to
  preview, then calls `detect_and_create_issues`, messages are fetched **twice** and
  detection runs **twice** — wasting API calls and producing potentially different results.
- **Impact:** Redundant Slack API calls and Claude API calls. Possible inconsistent detection results.
- **Fix:** Allow `detect_and_create_issues` to accept pre-fetched messages, or cache fetched messages.

---

## Problem #8 — MEDIUM: Possibly Expired GitHub PAT Token

- **Status:** [x] RESOLVED
- **Files:** `.env:20`
- **Description:**
  The GitHub token uses the `ghp_` prefix (classic Personal Access Token). GitHub has been
  migrating to fine-grained tokens (`github_pat_`). Classic PATs may have expired or been
  revoked, causing all GitHub operations to fail silently with
  `{"success": False, "error": "GitHub API returned 401: ..."}`.
- **Impact:** All GitHub operations (create issue, list issues) fail silently.
- **Fix:** Verify the token is valid. Regenerate if expired. Consider using fine-grained PAT.

---

## Problem #6 — LOW: Direct Import of MCP-Decorated Function

- **Status:** [x] RESOLVED
- **Files:** `src/services/reminder.py:413`, `src/mcp_servers/slack_server.py`
- **Description:**
  `ReminderService.execute_due_reminders()` imports `post_message` directly from
  `slack_server.py`. That function is decorated with `@mcp.tool()`. While FastMCP tools
  are still callable as regular async functions, this bypasses any MCP middleware and
  couples the reminder service directly to the Slack MCP module.
- **Impact:** Tight coupling; may break if FastMCP changes decorator behavior.
- **Fix:** Use the Slack SDK `AsyncWebClient` directly in the reminder delivery path, or create a shared helper.

---

## Problem #9 — CRITICAL: Missing Agent Tools for Core Functionality

- **Status:** [x] RESOLVED
- **Files:** `src/agent/tools.py`
- **Description:**
  The agent tool registry was missing several critical tools that are needed for
  the agent to actually perform its advertised capabilities:
  - **No `summarize_channel` tool** — Agent cannot summarize channels (only `/bot-summarize` slash command works)
  - **No `list_channels` tool** — Agent cannot discover what channels exist
  - **No `get_channel_info` tool** — Agent cannot inspect channel metadata
  - **No `list_github_issues` tool** — Agent can create issues but never list them
- **Impact:** The agent is severely limited and cannot perform basic operations users expect:
  - "Summarize #general" → fails (no tool to call)
  - "What channels am I in?" → fails (no tool to call)
  - "What issues are open?" → fails (no tool to call)
- **Fix:** Added all missing tools to `ToolRegistry`:
  - `summarize_channel(channel_id, hours)` — chains `get_channel_messages` + `SummarizationService`
  - `list_channels()` — delegates to Slack MCP `list_channels`
  - `get_channel_info(channel_id)` — delegates to Slack MCP `get_channel_info`
  - `list_github_issues(repo, state, limit)` — delegates to `GitHubMCPClient.list_issues`

---

## Problem #10 — HIGH: No RAG Indexing Cron Job

- **Status:** [x] RESOLVED
- **Files:** `src/app.py`, `src/rag/indexer.py`
- **Description:**
  The RAG (Retrieval-Augmented Generation) system has a complete indexer and vector
  store implementation, but **no periodic job to populate it**. The `ChannelIndexer`
  is never invoked, so the ChromaDB vector store remains empty. This means:
  - `SemanticRetriever.retrieve()` always returns empty results
  - The agent's RAG context is always blank
  - Memory context enhancement from past conversations never works
- **Impact:** The agent has no access to historical channel messages for semantic search.
  It cannot answer "what did we discuss about X last week?" or provide context from
  past conversations.
- **Fix:** Added periodic RAG indexing job to APScheduler in `src/app.py`:
  - Runs every `settings.rag_indexing_frequency` seconds (default: 2 hours)
  - Fetches list of all channels via `list_channels()`
  - Calls `ChannelIndexer.index_channel()` for each channel
  - Logs indexing progress and errors

---

## Problem #11 — MEDIUM: No Reminder Cleanup Cron Job

- **Status:** [x] RESOLVED
- **Files:** `src/app.py`, `src/services/reminder.py`
- **Description:**
  The `ReminderService` has a complete `cleanup_old_reminders()` method to remove
  delivered/cancelled reminders older than N days, but **it is never called**. Without
  periodic cleanup, the `reminders.json` file grows indefinitely with stale data.
- **Impact:** Over time, `reminders.json` becomes bloated with thousands of old delivered
  reminders, slowing down file I/O and wasting disk space.
- **Fix:** Added weekly cleanup job to APScheduler in `src/app.py`:
  - Runs every Sunday at midnight (cron: `0 0 * * 0`)
  - Calls `ReminderService.cleanup_old_reminders(days=30)`
  - Removes delivered/cancelled reminders older than 30 days
  - Preserves all pending reminders regardless of age

---

## Problem #12 — LOW: No Heartbeat/Health Check

- **Status:** [x] RESOLVED
- **Files:** `src/app.py`
- **Description:**
  The bot has no periodic health check or heartbeat mechanism. This makes it difficult
  to detect degraded states (e.g., Slack API down, scheduler stalled, memory leaks) in
  production.
- **Impact:** Silent failures can go undetected for hours. No uptime metrics or service
  availability monitoring.
- **Fix:** Added heartbeat job to APScheduler in `src/app.py`:
  - Runs every 5 minutes
  - Logs bot uptime and key service status
  - Provides a regular pulse in logs for monitoring/alerting
  - Can be extended to ping external health check endpoints (Datadog, PagerDuty, etc.)

---

## Problem #13 — CRITICAL: Agent Tools Importing MCP-Decorated Functions

- **Status:** [x] RESOLVED
- **Files:** `src/agent/tools.py`
- **Description:**
  All agent tools that needed to call Slack operations were importing FastMCP-decorated
  functions from `src/mcp_servers/slack_server.py`. When FastMCP decorates a function
  with `@mcp.tool()`, it wraps the function in a `FunctionTool` object. Direct imports
  of these wrapped functions fail with `'FunctionTool' object is not callable`.

  Affected tools:
  - `_get_channel_messages` — imported `get_channel_messages`
  - `_post_message` — imported `post_message`
  - `_schedule_message` — imported `schedule_message`
  - `_list_channels` — imported `list_channels`
  - `_get_channel_info` — imported `get_channel_info`
  - `_summarize_channel` — imported `get_channel_messages`, `get_channel_info`
  - `_fetch_channel_messages` — imported `get_channel_messages`
  - `_create_notion_page_from_messages` — imported `get_channel_messages`
- **Impact:** **ALL agent Slack tools were completely broken**. The agent could not:
  - Fetch messages from channels
  - Post messages
  - Schedule messages
  - List channels
  - Get channel info
  - Summarize channels
  - Any compound operation using these primitives
- **Fix:** Rewrote all affected tools to use `slack_sdk.web.async_client.AsyncWebClient`
  directly instead of importing MCP-decorated functions. Each tool now creates its own
  Slack client and calls the SDK methods directly. This makes the tools independent of
  the MCP server implementation and fully functional.
