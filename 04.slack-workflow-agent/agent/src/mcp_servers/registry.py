"""
MCP Server Registry
====================

WHY THIS FILE IS REQUIRED:
    The bot integrates with multiple external services (Slack, GitHub, Notion)
    via the Model Context Protocol (MCP).  Each service has its own client
    class (GitHubMCPClient, NotionMCPClient) that requires an API token.

    Rather than scattering "if token configured → create client" checks
    throughout the codebase, this registry centralizes that logic.  It:
      1. Checks which tokens are present in settings.
      2. Conditionally initializes the corresponding MCP clients.
      3. Exposes .github and .notion attributes (None if not configured).
      4. Provides get_available_tools() for introspection.

PROGRAM LOGIC:
    - On initialization, check settings.github_token and settings.notion_token.
    - If a token exists, import and instantiate the corresponding client.
    - If no token, set the attribute to None and log a "disabled" message.
    - get_available_tools() returns a dynamic list of tool descriptors based
      on which services are currently enabled.

WHY THIS APPROACH:
    - CONDITIONAL INITIALIZATION avoids import errors and unnecessary
      network connections for services the user hasn't configured.
    - LAZY IMPORTS (inside __init__, not at module top) prevent circular
      imports and keep startup fast when a service isn't needed.
    - SINGLE REGISTRY means the ToolRegistry only needs to check one place
      to know what's available — rather than each tool checking independently.
    - DYNAMIC TOOL LIST: get_available_tools() only includes tools for
      configured services, so the agent never sees phantom capabilities.

RELATIONSHIP TO OTHER FILES:
    - Used by: src/agent/tools.py (ToolRegistry checks .github / .notion)
    - Uses: src/mcp_servers/github_client.py, src/mcp_servers/notion_client.py
    - Reads: config/settings.py (for token presence checks)
"""

from typing import Dict, List, Any, Optional

from config.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MCPRegistry:
    """
    Central registry for external MCP service clients.

    Attributes:
        github: GitHubMCPClient instance (or None if no token).
        notion: NotionMCPClient instance (or None if no token).

    The Slack MCP server (slack_server.py) is always available because
    Slack tokens are required fields — they're validated at startup by
    Pydantic.  GitHub and Notion are optional integrations.
    """

    def __init__(self):
        # These are typed as Optional so callers can do `if self.github:`
        # checks safely.  The forward-reference strings ("GitHubMCPClient")
        # are used because the actual classes haven't been imported yet.
        self.github: Optional["GitHubMCPClient"] = None
        self.notion: Optional["NotionMCPClient"] = None

        # ── GitHub: conditional initialization ──
        # Only import and create the client if a Personal Access Token (PAT)
        # is configured.  This prevents import-time errors if the github
        # module has unmet dependencies AND avoids making API connections
        # we'll never use.
        if settings.github_token:
            from src.mcp_servers.github_client import GitHubMCPClient
            self.github = GitHubMCPClient()
            logger.info("GitHub MCP client enabled")
        else:
            logger.info("GitHub MCP client disabled (no token)")

        # ── Notion: conditional initialization ──
        # Same pattern as GitHub — only create if NOTION_TOKEN is set.
        if settings.notion_token:
            from src.mcp_servers.notion_client import NotionMCPClient
            self.notion = NotionMCPClient()
            logger.info("Notion MCP client enabled")
        else:
            logger.info("Notion MCP client disabled (no token)")

        logger.info("MCP registry initialized")

    def get_available_tools(self) -> List[Dict[str, Any]]:
        """
        Return a list of all available tool descriptors.

        This is used for introspection and logging — it tells you what
        capabilities the bot currently has based on which tokens are set.

        Each descriptor is a dict with:
            - name:        Namespaced tool name (e.g. "slack:post_message")
            - description: Human-readable description
            - server:      Which MCP server provides this tool

        The list is DYNAMIC: GitHub and Notion tools only appear if their
        respective clients are initialized.

        NOTE: This is separate from ToolRegistry.get_tool_definitions(),
        which returns Claude's JSON schema format.  This method returns a
        simpler list for logging and admin purposes.
        """
        # ── Always-available tools ──
        # Slack tools are always present because Slack tokens are required.
        # Agent tools (issue detection, reminders) use Claude or local storage
        # and don't require external tokens.
        tools = [
            {
                "name": "slack:get_channel_messages",
                "description": "Retrieve messages from Slack channel",
                "server": "slack",
            },
            {
                "name": "slack:post_message",
                "description": "Post message to Slack channel",
                "server": "slack",
            },
            {
                "name": "slack:schedule_message",
                "description": "Schedule a message to Slack channel",
                "server": "slack",
            },
            {
                "name": "agent:detect_issues",
                "description": "Detect issues in Slack channel messages",
                "server": "agent",
            },
            {
                "name": "agent:schedule_reminder",
                "description": "Schedule a reminder for a user",
                "server": "agent",
            },
            {
                "name": "agent:list_reminders",
                "description": "List pending reminders",
                "server": "agent",
            },
            {
                "name": "agent:cancel_reminder",
                "description": "Cancel a pending reminder",
                "server": "agent",
            },
        ]

        # ── Conditionally-available: GitHub ──
        if self.github is not None:
            tools.append({
                "name": "github:create_issue",
                "description": "Create GitHub issue",
                "server": "github",
            })
            tools.append({
                "name": "agent:detect_and_create_issues",
                "description": "Detect issues and auto-create GitHub issues",
                "server": "agent",
            })

        # ── Conditionally-available: Notion ──
        if self.notion is not None:
            tools.append({
                "name": "notion:create_page",
                "description": "Create Notion page",
                "server": "notion",
            })
            tools.append({
                "name": "notion:create_page_from_messages",
                "description": "Create Notion page from Slack messages",
                "server": "notion",
            })
            tools.append({
                "name": "notion:search",
                "description": "Search Notion workspace",
                "server": "notion",
            })

        return tools
