"""
Notion Integration Service
===========================

WHY THIS FILE IS REQUIRED:
    The Notion MCP client (notion_client.py) provides low-level API calls
    (create_page, search), but it doesn't know anything about Slack messages,
    formatting, or how to turn a raw conversation into a useful document.

    This service sits BETWEEN the agent and the Notion client, providing
    high-level operations like:
      - "Take these 50 Slack messages and create a well-formatted Notion page."
      - "Search Notion for pages related to a topic."
      - "Create a Notion page from a specific Slack thread."

    Without this service, the agent would have to manually format messages,
    call Claude for summarization, and then call the Notion API — all in
    the orchestrator.  Extracting that into a dedicated service keeps the
    orchestrator lean and the logic reusable.

PROGRAM LOGIC (high-level flow):
    1. CREATE PAGE FROM MESSAGES:
       a. Accept raw Slack messages + Notion parent ID + title.
       b. Send the messages to Claude with a formatting prompt to produce
          a clean, structured document (summary + sections + action items).
       c. Pass the formatted text to NotionMCPClient.create_page().
       d. Return the created page info (URL, ID, etc.).

    2. CREATE PAGE FROM THREAD:
       a. Fetch messages from a specific Slack thread via the Slack MCP server.
       b. Auto-generate a title from the first message if not provided.
       c. Delegate to create_page_from_messages() for formatting + creation.

    3. SEARCH NOTION:
       a. Thin wrapper around NotionMCPClient.search().
       b. Exists as a service method so the ToolRegistry has a consistent
          interface and the agent can search without knowing API details.

WHY THIS APPROACH (design decisions):
    - AI-POWERED FORMATTING: Raw Slack messages are messy (short replies,
      emojis, incomplete sentences).  Claude restructures them into a
      professional document with a summary, sections, and action items.
      This produces far better Notion pages than simple copy-paste.

    - GRACEFUL AI FALLBACK: If Claude's formatting call fails (rate limit,
      network error), we fall back to a simple "**User X**: text" format
      rather than failing the entire operation.  A basic page is better
      than no page.

    - CONDITIONAL INITIALIZATION: The Notion client is only created if
      NOTION_TOKEN is set.  Every public method calls _require_notion()
      first, which raises NotionIntegrationError if not configured.  This
      extracted guard method eliminates the repeated if-not-client checks
      that would otherwise appear in every method.

    - 50-MESSAGE CAP in formatting: prevents blowing up Claude's context
      window and keeps API costs reasonable for a single page creation.

SECURITY CONSIDERATIONS:
    - Notion tokens are loaded from environment variables, never hardcoded.
    - User content (Slack messages) is passed to Claude for formatting but
      is never logged in full (only message count is logged).
"""

from typing import List, Dict, Any, Optional

from anthropic import AsyncAnthropic

from config.settings import settings
from src.utils.logger import get_logger
from src.utils.exceptions import NotionIntegrationError

logger = get_logger(__name__)

# ──────────────────────────────────────────────────────────────────────
# FORMATTING PROMPT
# ──────────────────────────────────────────────────────────────────────

# This prompt instructs Claude to transform raw Slack messages into a
# structured document suitable for a Notion page.
#
# WHY A PROMPT (vs. regex/templates):
#   Conversations are unstructured — messages overlap, reference each other,
#   and use informal language.  Claude can understand context and produce a
#   coherent document that a template-based approach never could.
#
# WHY "Return ONLY the formatted document":
#   Without this instruction, Claude might add preamble like "Here's the
#   formatted document:" which we'd have to strip.  Being explicit avoids
#   post-processing.
FORMAT_PROMPT = """Format the following Slack conversation into a clean, well-structured document suitable for a Notion page.

Channel: #{channel_name}

Messages:
{messages}

Create a well-organized document with:
1. A brief summary at the top (2-3 sentences)
2. Key discussion points as sections
3. Any action items or decisions highlighted
4. Keep the tone professional but preserve important context

Return ONLY the formatted document text. No JSON or metadata."""


# ──────────────────────────────────────────────────────────────────────
# SERVICE CLASS
# ──────────────────────────────────────────────────────────────────────

class NotionIntegrationService:
    """
    High-level Notion operations: create pages from Slack, search, sync.

    Architecture:
        - Wraps NotionMCPClient (low-level API) with business logic.
        - Uses AsyncAnthropic to format conversations via Claude.
        - Both dependencies are conditionally initialized.
        - All public methods call _require_notion() as a precondition guard.

    Dependency chain:
        Agent Orchestrator → ToolRegistry → NotionIntegrationService
                                               ├── NotionMCPClient (API calls)
                                               └── AsyncAnthropic (formatting)
    """

    def __init__(self):
        # The Notion API client — set to None if no token is configured.
        # We use a lazy import to avoid import errors when the notion_client
        # module isn't needed.
        self._notion_client = None

        # Claude client for AI-powered message formatting.
        # Always initialized because we need it for formatting even if
        # Notion might not be available (the service degrades gracefully).
        self._ai_client = AsyncAnthropic(api_key=settings.anthropic_api_key)

        # Conditional initialization: only create the Notion client if
        # a token is configured.  This pattern is consistent with how
        # MCPRegistry initializes GitHub and Notion clients.
        if settings.notion_token:
            from src.mcp_servers.notion_client import NotionMCPClient
            self._notion_client = NotionMCPClient()
            logger.info("Notion integration service initialized")
        else:
            logger.info("Notion integration service initialized (no Notion token - limited mode)")

    @property
    def is_available(self) -> bool:
        """
        Check if Notion integration is available.

        WHY A PROPERTY:
            Allows callers to check availability without try/except.
            Example: if notion_service.is_available: ...
        """
        return self._notion_client is not None

    def _require_notion(self) -> None:
        """
        Precondition guard: raise if Notion is not configured.

        WHY AN EXTRACTED METHOD:
            Without this, every public method would have:
                if not self._notion_client:
                    raise NotionIntegrationError("Notion not configured...")
            Extracting it into a single method eliminates the duplication and
            ensures consistent error messages.  This is the "Guard Clause"
            pattern — fail fast at the top of the method, before doing any work.
        """
        if not self._notion_client:
            raise NotionIntegrationError(
                "Notion integration not configured. Set NOTION_TOKEN to enable."
            )

    # ──────────────────────────────────────────────────────────────────
    # PUBLIC: Create a Notion page from Slack messages
    # ──────────────────────────────────────────────────────────────────

    async def create_page_from_messages(
        self,
        messages: List[Dict[str, Any]],
        parent_id: str,
        title: str,
        channel_name: str = "channel",
    ) -> Dict[str, Any]:
        """
        Create a Notion page from Slack messages.

        HOW IT WORKS:
            1. Guard: ensure Notion is configured and messages are non-empty.
            2. Call _format_messages_for_notion() which sends messages to Claude
               to produce a clean, structured document.
            3. Call NotionMCPClient.create_page() with the formatted content.
            4. Return the result (includes page URL and ID).

        WHY FORMAT BEFORE CREATING:
            Raw Slack messages are short, informal, and lack structure.
            A Notion page should be a polished document.  Claude transforms
            the raw chat into sections, summaries, and action items.

        Args:
            messages:     List of Slack message dicts (need "text" and "user" keys).
            parent_id:    Notion parent page or database ID (where to create).
            title:        Title for the new Notion page.
            channel_name: Source channel name (used in the formatting prompt).

        Returns:
            Dict from Notion API with page creation details.

        Raises:
            NotionIntegrationError: If Notion is not configured, no messages
                provided, or the API call fails.
        """
        self._require_notion()

        if not messages:
            raise NotionIntegrationError("No messages provided to create page from")

        logger.info("Creating Notion page '%s' from %d messages", title, len(messages))

        try:
            # Step 1: Use Claude to format raw messages into a structured document.
            formatted_content = await self._format_messages_for_notion(
                messages, channel_name
            )

            # Step 2: Create the Notion page via the MCP client.
            result = await self._notion_client.create_page(
                parent_id=parent_id,
                title=title,
                content=formatted_content,
            )

            if result.get("success"):
                logger.info("Notion page created: %s", result.get("url", "unknown"))
            else:
                logger.warning("Notion page creation returned: %s", result)

            return result

        except NotionIntegrationError:
            # Domain errors propagate unchanged.
            raise
        except Exception as e:
            # Wrap unexpected errors into NotionIntegrationError for
            # consistent error handling by the caller (ToolRegistry).
            logger.error("Failed to create Notion page: %s", e)
            raise NotionIntegrationError(f"Failed to create Notion page: {e}")

    # ──────────────────────────────────────────────────────────────────
    # PUBLIC: Create a Notion page from a Slack thread
    # ──────────────────────────────────────────────────────────────────

    async def create_page_from_thread(
        self,
        channel_id: str,
        thread_ts: str,
        parent_id: str,
        title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a Notion page from a Slack thread.

        HOW IT WORKS:
            1. Fetch messages from the channel via the Slack MCP server.
               (We fetch 7 days of history to capture the full thread.)
            2. Auto-generate a title from the first message if not provided,
               truncated to 60 characters to keep it reasonable.
            3. Delegate to create_page_from_messages() for the actual work.

        WHY DELEGATION:
            This method handles the "fetch from Slack" step; the formatting
            and Notion creation are reused from create_page_from_messages().
            This avoids duplicating the Claude formatting and API call logic.

        Args:
            channel_id: Slack channel ID containing the thread.
            thread_ts:  Thread timestamp (the parent message's ts value).
            parent_id:  Notion parent page or database ID.
            title:      Optional title (auto-generated from first message if omitted).

        Returns:
            Dict from Notion API with page creation details.

        Raises:
            NotionIntegrationError: If no messages found or creation fails.
        """
        self._require_notion()

        logger.info("Creating Notion page from thread %s in %s", thread_ts, channel_id)

        try:
            # Lazy import to avoid circular dependencies at module load time.
            # The Slack MCP server imports settings, which might transitively
            # import this module during startup.
            from src.mcp_servers.slack_server import get_channel_messages

            # Fetch 7 days of messages to capture thread context.
            # 168 hours = 7 days * 24 hours.
            messages_result = await get_channel_messages(channel_id, hours=168)
            messages = messages_result.get("messages", [])

            if not messages:
                raise NotionIntegrationError("No messages found in the specified thread")

            # Auto-title: use the first 60 chars of the first message.
            # This gives users a recognizable title without manual input.
            if not title:
                first_text = messages[0].get("text", "Slack Thread")[:60]
                title = f"Thread: {first_text}"

            # Delegate to the main method for formatting + creation.
            return await self.create_page_from_messages(
                messages=messages,
                parent_id=parent_id,
                title=title,
                channel_name=channel_id,
            )

        except NotionIntegrationError:
            raise
        except Exception as e:
            logger.error("Failed to create page from thread: %s", e)
            raise NotionIntegrationError(f"Failed to create page from thread: {e}")

    # ──────────────────────────────────────────────────────────────────
    # PUBLIC: Search Notion
    # ──────────────────────────────────────────────────────────────────

    async def search_notion(self, query: str) -> List[Dict[str, Any]]:
        """
        Search Notion for pages matching a query.

        WHY A WRAPPER:
            The raw NotionMCPClient.search() method returns API-level data.
            This wrapper adds logging and consistent error handling.  It also
            provides the ToolRegistry with a uniform service interface.

        Args:
            query: Free-text search query.

        Returns:
            List of matching Notion page dicts.

        Raises:
            NotionIntegrationError: If Notion is not configured or search fails.
        """
        self._require_notion()

        try:
            results = await self._notion_client.search(query)
            logger.info("Notion search for '%s' returned %d results", query, len(results))
            return results

        except NotionIntegrationError:
            raise
        except Exception as e:
            logger.error("Notion search failed: %s", e)
            raise NotionIntegrationError(f"Notion search failed: {e}")

    # ──────────────────────────────────────────────────────────────────
    # PRIVATE: AI-powered message formatting
    # ──────────────────────────────────────────────────────────────────

    async def _format_messages_for_notion(
        self, messages: List[Dict[str, Any]], channel_name: str
    ) -> str:
        """
        Use Claude to format Slack messages into structured Notion content.

        HOW IT WORKS:
            1. Convert each Slack message into a "**User X**: text" line.
            2. Cap at 50 messages to stay within Claude's context window
               and keep API costs reasonable.
            3. Build the FORMAT_PROMPT with the channel name and messages.
            4. Call Claude Sonnet to produce the formatted document.
            5. Return the formatted text.

        FALLBACK STRATEGY:
            If Claude fails (rate limit, network error, etc.), we fall back
            to the raw "**User X**: text" format.  This ensures the page
            is still created — just without AI polish.  A basic page is
            better than a failed operation.

        WHY 50-MESSAGE CAP:
            - Claude Sonnet has a large context window, but we're also
              paying per token.  50 messages typically cover the important
              parts of a conversation.
            - Longer conversations often have noise (reactions, short "ok"
              replies) that dilute the summary.  50 is a practical balance.

        Args:
            messages:     Raw Slack message dicts.
            channel_name: Channel name for the prompt context.

        Returns:
            Formatted text string suitable for a Notion page body.
        """
        # Build the raw message text (used both for the prompt and as fallback).
        formatted_msgs = []
        for msg in messages[:50]:  # Cap at 50 messages
            user = msg.get("user", "Unknown")
            text = msg.get("text", "")
            if text:
                formatted_msgs.append(f"**User {user}**: {text}")

        messages_text = "\n\n".join(formatted_msgs)

        # Build the full prompt with channel context.
        prompt = FORMAT_PROMPT.format(
            channel_name=channel_name, messages=messages_text
        )

        try:
            response = await self._ai_client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )

            content = response.content[0].text.strip()
            logger.debug("Messages formatted for Notion successfully")
            return content

        except Exception as e:
            # Graceful degradation: use raw format instead of failing.
            logger.warning("AI formatting failed, using raw format: %s", e)
            return messages_text
