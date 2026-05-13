"""
Agent Tool Registry
====================

WHY THIS FILE IS REQUIRED:
    The AI agent (orchestrator.py) uses Claude's tool-calling feature to
    perform actions in the real world — post Slack messages, create GitHub
    issues, schedule reminders, etc.  Claude needs to know:
      1. WHAT tools are available (name, description, input schema).
      2. HOW to call them (an async function that does the work).

    This registry is the bridge: it maps tool names → callable methods,
    and provides JSON schema definitions that Claude uses to decide which
    tool to invoke and with what arguments.

PROGRAM LOGIC (high-level flow):
    1. On initialization, ToolRegistry creates an MCPRegistry (which checks
       which external services are configured via environment tokens).
    2. _register_tools() loops through all available tools and:
       a. Adds the tool's implementation (async method) to self.tools dict.
       b. Adds the tool's JSON schema definition to self._definitions list.
       c. Conditionally registers tools based on config (e.g. GitHub tools
          are only registered if GITHUB_TOKEN is set).
    3. When the orchestrator receives a tool_use block from Claude, it calls
       execute_tool(name, **kwargs) which looks up the method and runs it.

WHY THIS APPROACH (design decisions):
    - LAZY SERVICE CACHING: Services like IssueDetectionService and
      ReminderService are expensive to create (they initialize API clients,
      load files, etc.).  Rather than creating a new instance on every tool
      call, we cache them with _get_*_service() accessors.  The first call
      creates the instance; subsequent calls reuse it.

    - LAZY IMPORTS: Service imports (e.g. `from src.services.reminder import
      ReminderService`) are done inside methods, not at the top of the file.
      This prevents circular imports and avoids loading heavy modules until
      they're actually needed.  Since each import is cached by Python after
      the first load, the overhead is negligible.

    - CONDITIONAL REGISTRATION: GitHub and Notion tools are only registered
      if their respective tokens are configured.  This means Claude never
      sees tools it can't actually use — reducing confusion and preventing
      errors from attempting to call unconfigured services.

    - NULL SAFETY GUARDS: Even though tools are conditionally registered,
      _create_github_issue() and _create_notion_page() include null checks
      on the MCP client.  This is defense-in-depth: if the registry state
      somehow becomes inconsistent (e.g. hot config reload), the methods
      return an error dict instead of crashing with AttributeError.

    - TOOL SCHEMA FORMAT: Each tool definition follows the Claude tool_use
      format: name, description, input_schema (JSON Schema).  This is sent
      directly to the Anthropic API in the `tools` parameter.

SECURITY CONSIDERATIONS:
    - Tool names and descriptions are static strings (not user-supplied),
      so there's no injection risk in the schema definitions.
    - All user-supplied arguments (channel_id, text, etc.) are validated
      by the downstream services, not by this registry.
    - %s-style logging is used throughout to avoid unnecessary string
      interpolation when log levels are disabled.
"""

from typing import Dict, Any, Callable, List, Optional

from src.utils.logger import get_logger
from src.mcp_servers.registry import MCPRegistry

logger = get_logger(__name__)


class ToolRegistry:
    """
    Registry of tools available to the AI agent.

    Architecture:
        ToolRegistry is the central hub that connects:
          - Claude (via tool definitions / JSON schemas)
          - MCP servers (Slack, GitHub, Notion via MCPRegistry)
          - Business services (IssueDetection, Reminder, NotionIntegration)

    The orchestrator uses this class in two ways:
        1. get_tool_definitions() → passed to Claude in the API call.
        2. execute_tool(name, **kwargs) → called when Claude returns tool_use.
    """

    def __init__(self):
        # MCPRegistry checks which external services have tokens configured
        # and initializes their clients.  We store it to access .github and
        # .notion clients directly for low-level operations.
        self.mcp_registry = MCPRegistry()

        # Map of tool_name → async callable.
        # Example: {"post_message": self._post_message, ...}
        self.tools: Dict[str, Callable] = {}

        # List of tool definitions in Claude's expected JSON schema format.
        # Sent to the Anthropic API in the `tools` parameter.
        self._definitions: List[Dict[str, Any]] = []

        # ── Lazy-cached service instances ──
        # Why Optional[Any] instead of Optional[IssueDetectionService]:
        #   Using the actual type would require importing the service class
        #   at the top of the file, which we avoid to prevent circular imports.
        #   The lazy accessors (_get_*_service) handle the import internally.
        self._issue_service: Optional[Any] = None
        self._reminder_service: Optional[Any] = None
        self._notion_service: Optional[Any] = None

        # Register all available tools based on current configuration.
        self._register_tools()
        logger.info("Tool registry initialized with %d tools", len(self.tools))

    # ──────────────────────────────────────────────────────────────────
    # LAZY SERVICE ACCESSORS
    #
    # WHY LAZY:
    #   Each service is only created on first use.  This avoids:
    #   - Loading heavy modules (Anthropic SDK, file I/O) at startup.
    #   - Creating services that may never be called in a given session.
    #   - Import errors if an optional dependency is missing.
    #
    # WHY CACHED:
    #   Services hold state (API clients, file handles, in-memory data).
    #   Re-creating them on every call would waste resources and lose state
    #   (e.g. ReminderService would re-read the JSON file unnecessarily).
    # ──────────────────────────────────────────────────────────────────

    def _get_issue_service(self):
        """Get or create the cached IssueDetectionService instance."""
        if self._issue_service is None:
            from src.services.issue_detection import IssueDetectionService
            self._issue_service = IssueDetectionService()
        return self._issue_service

    def _get_reminder_service(self):
        """Get or create the cached ReminderService instance."""
        if self._reminder_service is None:
            from src.services.reminder import ReminderService
            self._reminder_service = ReminderService()
        return self._reminder_service

    def _get_notion_service(self):
        """Get or create the cached NotionIntegrationService instance."""
        if self._notion_service is None:
            from src.services.notion_integration import NotionIntegrationService
            self._notion_service = NotionIntegrationService()
        return self._notion_service

    # ──────────────────────────────────────────────────────────────────
    # TOOL REGISTRATION
    #
    # Each tool registration has two parts:
    #   1. self.tools[name] = method   (the implementation)
    #   2. self._definitions.append()  (the JSON schema for Claude)
    #
    # The JSON schema follows Claude's tool_use format:
    #   {
    #     "name": "tool_name",
    #     "description": "What this tool does (Claude reads this)",
    #     "input_schema": {
    #       "type": "object",
    #       "properties": { ... },
    #       "required": [ ... ]
    #     }
    #   }
    #
    # Claude uses the description to decide WHEN to call a tool, and the
    # input_schema to decide WHAT arguments to pass.  Good descriptions
    # are critical for reliable tool selection.
    # ──────────────────────────────────────────────────────────────────

    def _register_tools(self) -> None:
        """Register all available tools based on current configuration."""

        # ── SLACK TOOLS (always available) ──
        # These are core operations that every Slack bot needs.
        # They delegate to the Slack MCP server (slack_server.py).

        self.tools["get_channel_messages"] = self._get_channel_messages
        self._definitions.append({
            "name": "get_channel_messages",
            "description": "Retrieve messages from a Slack channel for a given time period",
            "input_schema": {
                "type": "object",
                "properties": {
                    "channel_id": {"type": "string", "description": "Slack channel ID (e.g. C1234567890)"},
                    "hours": {"type": "integer", "description": "Hours to look back (default: 24)"},
                },
                "required": ["channel_id"],
            },
        })

        self.tools["post_message"] = self._post_message
        self._definitions.append({
            "name": "post_message",
            "description": "Post a message to a Slack channel",
            "input_schema": {
                "type": "object",
                "properties": {
                    "channel_id": {"type": "string", "description": "Slack channel ID to post to"},
                    "text": {"type": "string", "description": "Message text to post"},
                },
                "required": ["channel_id", "text"],
            },
        })

        self.tools["schedule_message"] = self._schedule_message
        self._definitions.append({
            "name": "schedule_message",
            "description": "Schedule a message to be posted to a Slack channel at a specific time",
            "input_schema": {
                "type": "object",
                "properties": {
                    "channel_id": {"type": "string", "description": "Slack channel ID"},
                    "text": {"type": "string", "description": "Message text to post"},
                    "post_at": {"type": "integer", "description": "Unix timestamp for when to post"},
                },
                "required": ["channel_id", "text", "post_at"],
            },
        })

        self.tools["list_channels"] = self._list_channels
        self._definitions.append({
            "name": "list_channels",
            "description": "List all Slack channels the bot is a member of",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        })

        self.tools["get_channel_info"] = self._get_channel_info
        self._definitions.append({
            "name": "get_channel_info",
            "description": "Get information about a Slack channel (name, privacy, member count)",
            "input_schema": {
                "type": "object",
                "properties": {
                    "channel_id": {"type": "string", "description": "Slack channel ID"},
                },
                "required": ["channel_id"],
            },
        })

        self.tools["summarize_channel"] = self._summarize_channel
        self._definitions.append({
            "name": "summarize_channel",
            "description": (
                "Summarize recent messages from a Slack channel. "
                "Fetches messages and uses AI to produce a concise summary covering "
                "main topics, key decisions, and important issues."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "channel_id": {"type": "string", "description": "Slack channel ID to summarize"},
                    "hours": {"type": "integer", "description": "Hours of messages to summarize (default: 24)"},
                },
                "required": ["channel_id"],
            },
        })

        # ── GITHUB TOOLS (only if GITHUB_TOKEN is configured) ──
        # Conditional registration: Claude never sees these tools if
        # GitHub isn't set up, so it won't try to call them.
        if self.mcp_registry.github is not None:
            self.tools["create_github_issue"] = self._create_github_issue
            self._definitions.append({
                "name": "create_github_issue",
                "description": "Create a GitHub issue in a repository",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "repo": {"type": "string", "description": "Repository in owner/repo format"},
                        "title": {"type": "string", "description": "Issue title"},
                        "body": {"type": "string", "description": "Issue description body"},
                        "labels": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of labels to apply (e.g. ['bug', 'high-priority'])",
                        },
                    },
                    "required": ["repo", "title", "body"],
                },
            })

            self.tools["list_github_issues"] = self._list_github_issues
            self._definitions.append({
                "name": "list_github_issues",
                "description": "List issues from a GitHub repository, optionally filtered by state",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "repo": {"type": "string", "description": "Repository in owner/repo format"},
                        "state": {
                            "type": "string",
                            "description": "Issue state filter (default: open)",
                            "enum": ["open", "closed", "all"],
                        },
                        "limit": {"type": "integer", "description": "Max issues to return (default: 10, max: 100)"},
                    },
                    "required": ["repo"],
                },
            })

        # ── NOTION TOOLS (only if NOTION_TOKEN is configured) ──
        if self.mcp_registry.notion is not None:
            self.tools["create_notion_page"] = self._create_notion_page
            self._definitions.append({
                "name": "create_notion_page",
                "description": "Create a Notion page",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "parent_id": {"type": "string", "description": "Parent page or database ID"},
                        "title": {"type": "string", "description": "Page title"},
                        "content": {"type": "string", "description": "Page content in markdown"},
                    },
                    "required": ["parent_id", "title", "content"],
                },
            })

            # This higher-level tool fetches Slack messages, formats them
            # with AI, and creates a Notion page — all in one call.
            self.tools["create_notion_page_from_messages"] = self._create_notion_page_from_messages
            self._definitions.append({
                "name": "create_notion_page_from_messages",
                "description": (
                    "Create a Notion page from Slack channel messages. "
                    "Fetches messages, formats them with AI, and creates a structured Notion page."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "channel_id": {"type": "string", "description": "Slack channel ID to pull messages from"},
                        "parent_id": {"type": "string", "description": "Notion parent page or database ID"},
                        "title": {"type": "string", "description": "Title for the Notion page"},
                        "hours": {"type": "integer", "description": "Hours of messages to include (default: 24)"},
                    },
                    "required": ["channel_id", "parent_id", "title"],
                },
            })

            self.tools["search_notion"] = self._search_notion
            self._definitions.append({
                "name": "search_notion",
                "description": "Search Notion workspace for pages matching a query",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query string"},
                    },
                    "required": ["query"],
                },
            })

        # ── ISSUE DETECTION TOOLS (always available) ──
        # detect_issues uses Claude for analysis, so it works without
        # any external service tokens.
        self.tools["detect_issues"] = self._detect_issues
        self._definitions.append({
            "name": "detect_issues",
            "description": (
                "Analyze Slack channel messages to detect bugs, blockers, and issues. "
                "Returns a list of detected issues with severity and suggested labels."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "channel_id": {"type": "string", "description": "Slack channel ID to analyze"},
                    "hours": {"type": "integer", "description": "Hours of messages to analyze (default: 24)"},
                },
                "required": ["channel_id"],
            },
        })

        # detect_and_create_issues requires GitHub (to create tickets),
        # so it's only registered when GitHub is configured.
        if self.mcp_registry.github is not None:
            self.tools["detect_and_create_issues"] = self._detect_and_create_issues
            self._definitions.append({
                "name": "detect_and_create_issues",
                "description": (
                    "Analyze Slack messages for issues and automatically create GitHub issues "
                    "for ones meeting the severity threshold."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "channel_id": {"type": "string", "description": "Slack channel ID to analyze"},
                        "repo": {"type": "string", "description": "GitHub repository in owner/repo format"},
                        "hours": {"type": "integer", "description": "Hours of messages to analyze (default: 24)"},
                        "threshold": {
                            "type": "string",
                            "description": "Minimum severity to auto-create issues (critical, high, medium, low). Default: high",
                            "enum": ["critical", "high", "medium", "low"],
                        },
                    },
                    "required": ["channel_id", "repo"],
                },
            })

        # ── REMINDER TOOLS (always available) ──
        # Reminders use file-backed storage — no external API needed.
        self.tools["schedule_reminder"] = self._schedule_reminder
        self._definitions.append({
            "name": "schedule_reminder",
            "description": (
                "Schedule a reminder for a user. The reminder will be posted to the "
                "specified channel at the given time."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "Slack user ID to remind"},
                    "channel_id": {"type": "string", "description": "Channel to post reminder in"},
                    "text": {"type": "string", "description": "Reminder message text"},
                    "remind_at": {"type": "integer", "description": "Unix timestamp for when to deliver the reminder"},
                },
                "required": ["user_id", "channel_id", "text", "remind_at"],
            },
        })

        self.tools["list_reminders"] = self._list_reminders
        self._definitions.append({
            "name": "list_reminders",
            "description": "List pending reminders for a user",
            "input_schema": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "Slack user ID (optional, lists all if omitted)"},
                },
                "required": [],
            },
        })

        self.tools["cancel_reminder"] = self._cancel_reminder
        self._definitions.append({
            "name": "cancel_reminder",
            "description": "Cancel a pending reminder by its ID",
            "input_schema": {
                "type": "object",
                "properties": {
                    "reminder_id": {"type": "string", "description": "ID of the reminder to cancel"},
                    "user_id": {"type": "string", "description": "User ID (must match the reminder creator)"},
                },
                "required": ["reminder_id", "user_id"],
            },
        })

    # ──────────────────────────────────────────────────────────────────
    # SLACK TOOL IMPLEMENTATIONS
    #
    # These are thin wrappers around the Slack MCP server functions.
    # The lazy import pattern (import inside the method) avoids circular
    # imports since slack_server.py may import settings which may
    # transitively touch other modules.
    # ──────────────────────────────────────────────────────────────────

    async def _get_channel_messages(self, channel_id: str, hours: int = 24) -> Dict[str, Any]:
        """Get messages from a Slack channel via Slack SDK."""
        from slack_sdk.web.async_client import AsyncWebClient
        from config.settings import settings
        from datetime import datetime, timedelta

        try:
            slack_client = AsyncWebClient(token=settings.slack_bot_token)
            oldest = (datetime.now() - timedelta(hours=hours)).timestamp()
            response = await slack_client.conversations_history(
                channel=channel_id, oldest=str(oldest), limit=200
            )
            messages = response["messages"]
            return {"channel_id": channel_id, "message_count": len(messages), "messages": messages}
        except Exception as e:
            return {"error": str(e)}

    async def _post_message(self, channel_id: str, text: str) -> Dict[str, Any]:
        """Post a message to a Slack channel via Slack SDK."""
        from slack_sdk.web.async_client import AsyncWebClient
        from config.settings import settings

        try:
            slack_client = AsyncWebClient(token=settings.slack_bot_token)
            response = await slack_client.chat_postMessage(channel=channel_id, text=text)
            return {"success": True, "ts": response["ts"], "channel": response["channel"]}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _schedule_message(self, channel_id: str, text: str, post_at: int) -> Dict[str, Any]:
        """Schedule a message via Slack SDK."""
        from slack_sdk.web.async_client import AsyncWebClient
        from config.settings import settings

        try:
            slack_client = AsyncWebClient(token=settings.slack_bot_token)
            response = await slack_client.chat_scheduleMessage(
                channel=channel_id, text=text, post_at=post_at
            )
            return {
                "success": True,
                "scheduled_message_id": response["scheduled_message_id"],
                "post_at": post_at,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _list_channels(self) -> Dict[str, Any]:
        """List all channels the bot is a member of via Slack SDK."""
        from slack_sdk.web.async_client import AsyncWebClient
        from config.settings import settings

        try:
            slack_client = AsyncWebClient(token=settings.slack_bot_token)
            response = await slack_client.conversations_list(types="public_channel,private_channel")
            channels = response["channels"]
            return {
                "count": len(channels),
                "channels": [{"id": ch["id"], "name": ch.get("name")} for ch in channels],
            }
        except Exception as e:
            return {"error": str(e)}

    async def _get_channel_info(self, channel_id: str) -> Dict[str, Any]:
        """Get information about a Slack channel via Slack SDK."""
        from slack_sdk.web.async_client import AsyncWebClient
        from config.settings import settings

        try:
            slack_client = AsyncWebClient(token=settings.slack_bot_token)
            response = await slack_client.conversations_info(channel=channel_id)
            channel = response["channel"]
            return {
                "id": channel["id"],
                "name": channel.get("name"),
                "is_private": channel.get("is_private", False),
                "member_count": channel.get("num_members", 0),
            }
        except Exception as e:
            return {"error": str(e)}

    async def _summarize_channel(self, channel_id: str, hours: int = 24) -> Dict[str, Any]:
        """
        Fetch messages from a Slack channel and produce an AI summary.

        Chains two operations:
          1. Fetch messages via Slack SDK directly
          2. SummarizationService to generate a Claude-powered summary
        """
        from slack_sdk.web.async_client import AsyncWebClient
        from config.settings import settings
        from src.services.summarization import SummarizationService
        from datetime import datetime, timedelta

        try:
            slack_client = AsyncWebClient(token=settings.slack_bot_token)

            # Calculate oldest timestamp
            oldest = (datetime.now() - timedelta(hours=hours)).timestamp()

            # Fetch messages
            response = await slack_client.conversations_history(
                channel=channel_id,
                oldest=str(oldest),
                limit=200
            )

            messages = response.get("messages", [])

            if not messages:
                return {
                    "summary": f"No messages found in the last {hours} hours.",
                    "message_count": 0,
                    "channel": channel_id,
                }

            # Try to resolve channel name
            channel_name = channel_id
            try:
                info_response = await slack_client.conversations_info(channel=channel_id)
                channel_name = info_response["channel"].get("name", channel_id)
            except Exception:
                pass

            # Generate summary
            service = SummarizationService()
            summary = await service.summarize_messages(messages, channel_name=channel_name)

            return {
                "summary": summary,
                "channel": channel_name,
                "message_count": len(messages),
                "hours": hours,
            }

        except Exception as e:
            return {"error": f"Failed to summarize channel: {str(e)}"}


    # ──────────────────────────────────────────────────────────────────
    # GITHUB TOOL IMPLEMENTATIONS
    # ──────────────────────────────────────────────────────────────────

    async def _create_github_issue(
        self, repo: str, title: str, body: str, labels: List[str] = None
    ) -> Dict[str, Any]:
        """
        Create a GitHub issue via the GitHub MCP client.

        NULL SAFETY:  Even though this tool is only registered when GitHub
        is configured, we include a null check as defense-in-depth.  If
        the registry state somehow becomes inconsistent (e.g. hot config
        reload), this returns an error dict instead of crashing.
        """
        if self.mcp_registry.github is None:
            return {"error": "GitHub integration not configured"}
        return await self.mcp_registry.github.create_issue(repo, title, body, labels=labels)

    async def _list_github_issues(
        self, repo: str, state: str = "open", limit: int = 10
    ) -> Any:
        """
        List issues from a GitHub repository via the GitHub MCP client.
        """
        if self.mcp_registry.github is None:
            return {"error": "GitHub integration not configured"}
        return await self.mcp_registry.github.list_issues(repo, state=state, limit=limit)

    # ──────────────────────────────────────────────────────────────────
    # NOTION TOOL IMPLEMENTATIONS
    # ──────────────────────────────────────────────────────────────────

    async def _create_notion_page(self, parent_id: str, title: str, content: str) -> Dict[str, Any]:
        """
        Create a Notion page directly via the Notion MCP client.

        This is the low-level tool — it takes pre-formatted content.
        For AI-formatted pages from Slack messages, use
        create_notion_page_from_messages instead.
        """
        if self.mcp_registry.notion is None:
            return {"error": "Notion integration not configured"}
        return await self.mcp_registry.notion.create_page(parent_id, title, content)

    async def _create_notion_page_from_messages(
        self, channel_id: str, parent_id: str, title: str, hours: int = 24
    ) -> Dict[str, Any]:
        """
        High-level tool: fetch Slack messages → format with AI → create Notion page.

        This is a compound operation that chains:
          1. Fetch Slack messages → 2. Claude (format) → 3. Notion API (create page)
        The NotionIntegrationService handles steps 2 and 3.
        """
        # Use _get_channel_messages to fetch messages (uses Slack SDK)
        messages_result = await self._get_channel_messages(channel_id, hours)
        messages = messages_result.get("messages", [])

        service = self._get_notion_service()
        return await service.create_page_from_messages(
            messages=messages, parent_id=parent_id, title=title, channel_name=channel_id
        )

    async def _search_notion(self, query: str) -> Any:
        """Search Notion workspace via the NotionIntegrationService."""
        service = self._get_notion_service()
        return await service.search_notion(query)

    # ──────────────────────────────────────────────────────────────────
    # ISSUE DETECTION TOOL IMPLEMENTATIONS
    # ──────────────────────────────────────────────────────────────────

    async def _fetch_channel_messages(self, channel_id: str, hours: int = 24) -> list:
        """
        Shared helper to fetch channel messages from Slack.

        Centralises the Slack API call so that detect_issues and
        detect_and_create_issues never duplicate the fetch.
        """
        # Use _get_channel_messages which uses Slack SDK
        messages_result = await self._get_channel_messages(channel_id, hours)
        return messages_result.get("messages", [])

    async def _detect_issues(self, channel_id: str, hours: int = 24) -> Any:
        """
        Detect issues in channel messages (analysis only, no side effects).

        Flow: fetch messages from Slack → pass to IssueDetectionService
        → Claude analyzes → return structured issue list.
        """
        messages = await self._fetch_channel_messages(channel_id, hours)
        service = self._get_issue_service()
        return await service.detect_issues(messages, channel_name=channel_id)

    async def _detect_and_create_issues(
        self, channel_id: str, repo: str, hours: int = 24, threshold: str = "high"
    ) -> Any:
        """
        Detect issues AND create GitHub tickets for severe ones.

        Flow: fetch messages → Claude detects → filter by severity threshold
        → create GitHub issues for qualifying items.
        """
        messages = await self._fetch_channel_messages(channel_id, hours)
        service = self._get_issue_service()
        return await service.detect_and_create_issues(
            messages=messages, repo=repo, channel_name=channel_id, auto_create_threshold=threshold
        )

    # ──────────────────────────────────────────────────────────────────
    # REMINDER TOOL IMPLEMENTATIONS
    #
    # All three methods delegate to the cached ReminderService instance.
    # The service handles validation, persistence, and delivery.
    # ──────────────────────────────────────────────────────────────────

    async def _schedule_reminder(
        self, user_id: str, channel_id: str, text: str, remind_at: int
    ) -> Dict[str, Any]:
        """Schedule a reminder — delegates to ReminderService."""
        service = self._get_reminder_service()
        return await service.schedule_reminder(user_id, channel_id, text, remind_at)

    async def _list_reminders(self, user_id: str = None) -> Any:
        """List reminders for a user — delegates to ReminderService."""
        service = self._get_reminder_service()
        return await service.list_reminders(user_id=user_id)

    async def _cancel_reminder(self, reminder_id: str, user_id: str) -> Dict[str, Any]:
        """Cancel a pending reminder — delegates to ReminderService."""
        service = self._get_reminder_service()
        return await service.cancel_reminder(reminder_id, user_id)

    # ──────────────────────────────────────────────────────────────────
    # EXECUTION ENGINE
    #
    # This is the method the orchestrator calls when Claude returns a
    # tool_use block.  It looks up the tool by name, calls it with the
    # provided kwargs, and returns the result.
    #
    # WHY CATCH-ALL EXCEPTION HANDLING:
    #   If a tool crashes, we don't want the entire agent loop to abort.
    #   Instead, we return an error dict that Claude can interpret and
    #   either retry or inform the user.
    # ──────────────────────────────────────────────────────────────────

    async def execute_tool(self, tool_name: str, **kwargs) -> Any:
        """
        Execute a registered tool by name.

        Called by the orchestrator when Claude returns a tool_use block.
        The orchestrator passes tool_name and the input arguments as kwargs.

        Args:
            tool_name: Name of the tool (must match a registered tool).
            **kwargs:  Tool arguments (must match the input_schema).

        Returns:
            Tool result (dict, list, or other serializable value).

        Raises:
            ValueError: If the tool name is not registered.
        """
        if tool_name not in self.tools:
            raise ValueError(f"Tool not found: {tool_name}")

        tool = self.tools[tool_name]
        logger.info("Executing tool: %s", tool_name)

        try:
            result = await tool(**kwargs)
            logger.debug("Tool %s completed successfully", tool_name)
            return result
        except Exception as e:
            # Return error as a dict so Claude can read it and respond
            # appropriately (e.g. "I tried but the tool failed because...").
            logger.error("Tool %s failed: %s", tool_name, e)
            return {"error": str(e)}

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """
        Get all tool definitions in Claude's expected format.

        These are passed to the Anthropic API in the `tools` parameter
        of messages.create().  Claude uses them to decide which tool to
        call and what arguments to pass.

        Returns:
            List of tool definition dicts (name, description, input_schema).
        """
        return self._definitions
