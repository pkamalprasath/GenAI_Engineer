"""
Notion MCP Client

WHY THIS FILE IS REQUIRED:
    This module enables the Slack bot agent to create and search Notion pages.
    Notion serves as the team's knowledge base / wiki, so integrating it lets
    the agent automatically document decisions, meeting notes, or action items
    that emerge from Slack conversations.  For example, after summarizing a
    Slack thread, the agent can create a Notion page with the summary so it
    is preserved in the team's long-term documentation.

PROGRAM LOGIC:
    1. ``NotionMCPClient`` is initialized with a Notion Internal Integration
       Token from centralized settings.  The token and required headers
       (including the mandatory ``Notion-Version``) are stored once.
    2. ``create_page`` accepts a parent page/database ID, a title, and plain
       text content.  The content is split on double newlines and transformed
       into Notion's block-based JSON schema (one paragraph block per text
       chunk).  The resulting payload is POSTed to the Notion Pages API.
    3. ``search`` sends a query to the Notion Search API and returns a
       simplified list of matching pages (id, type, url).
    4. Like the GitHub client, each method creates a fresh
       ``aiohttp.ClientSession`` per call for lifecycle simplicity.

WHY THIS APPROACH:
    * ``aiohttp`` over the official ``notion-client`` SDK -- The official
      Python SDK is synchronous.  Since the entire bot is async, using
      ``aiohttp`` directly avoids ``asyncio.to_thread`` overhead and gives
      full control over request construction.
    * Plain-text content splitting -- Notion's block model is rich (headings,
      lists, toggles, etc.), but for the bot's primary use case (persisting
      conversation summaries), simple paragraph blocks are sufficient.
      Splitting on ``\n\n`` is a pragmatic heuristic that handles most
      natural-language output from the LLM.
    * Pinned ``Notion-Version`` header -- The Notion API is versioned via a
      required header.  Pinning to ``2022-06-28`` ensures consistent behavior
      even if Notion releases breaking changes in newer API versions.

SECURITY CONSIDERATIONS:
    * The Notion token (``settings.notion_token``) is a secret that grants
      read/write access to any pages shared with the integration.  It is
      loaded from environment configuration and NEVER logged or returned
      in responses.
    * ``parent_id`` should be validated as a Notion UUID before use.  If user
      input flows into this parameter without validation, it could
      theoretically be used to write to unexpected pages.
    * The ``Content-Type: application/json`` header is always set, ensuring
      the API interprets the body correctly even if ``aiohttp`` were to
      default to a different content type.
    * The ``create_page`` method sends content as-is.  If untrusted users
      can control the content, sanitization should be applied upstream to
      prevent Notion-rendered XSS or misleading links.

RELATIONSHIP TO OTHER FILES:
    - ``config/settings.py``           -- Supplies ``notion_token``.
    - ``src/agents/``                  -- The agent orchestration layer uses
                                          this client to create pages and
                                          search Notion as part of tool calls.
    - ``src/utils/exceptions.py``      -- Defines ``MCPServerError``.
    - ``src/utils/logger.py``          -- Structured logging.
    - ``src/mcp_servers/slack_server.py`` -- Sibling MCP integration; the agent
                                          may read Slack messages and then call
                                          Notion to document them.
    - ``src/mcp_servers/github_client.py`` -- Another sibling integration;
                                          together these three clients give the
                                          agent a Slack + GitHub + Notion
                                          workflow.

Real Notion API integration using aiohttp.
Only initialized when NOTION_TOKEN is configured.
"""

import aiohttp
from typing import Dict, Any, List

from config.settings import settings
from src.utils.logger import get_logger
from src.utils.exceptions import MCPServerError

logger = get_logger(__name__)

# Notion REST API base URL.  All endpoint paths are appended to this constant.
NOTION_API_BASE = "https://api.notion.com/v1"

# The Notion API requires a version header on every request.  Pinning to a
# specific version ensures that our payload schemas and response parsing
# remain valid even if Notion releases breaking changes in newer versions.
# "2022-06-28" is a stable, widely-used version at the time of writing.
NOTION_VERSION = "2022-06-28"


class NotionMCPClient:
    """Client for Notion API operations.

    Exposes a minimal interface for page creation and search -- the two
    operations the Slack bot agent needs to document conversations and look
    up existing documentation.

    Design decision -- why not support databases, blocks, or comments?
        Keeping the client focused on two operations reduces surface area
        for bugs and security issues.  Additional endpoints can be added
        incrementally as the agent's capabilities grow.
    """

    def __init__(self):
        """Initialize the Notion client with authentication headers.

        Three headers are required on every Notion API request:
          - ``Authorization: Bearer <token>``  -- authenticates the request.
          - ``Content-Type: application/json``  -- required for POST bodies.
          - ``Notion-Version``                  -- pins the API version.

        These are pre-built once and reused for all requests.

        Security note:
            The token is stored in ``self.token`` for potential reuse but is
            never serialized, logged, or exposed in tool responses.
        """
        self.token = settings.notion_token
        self._headers = {
            # Bearer token authentication for Notion Internal Integrations.
            "Authorization": f"Bearer {self.token}",
            # Explicit JSON content type.  While aiohttp sets this
            # automatically when using ``json=``, being explicit prevents
            # surprises if the calling code changes.
            "Content-Type": "application/json",
            # Mandatory API version header (see module-level constant).
            "Notion-Version": NOTION_VERSION,
        }
        logger.info("Notion MCP client initialized")

    async def create_page(self, parent_id: str, title: str, content: str) -> Dict[str, Any]:
        """
        Create a Notion page.

        Transforms plain text into Notion's block-based page structure and
        creates it under the specified parent page.  This is how the agent
        persists conversation summaries, meeting notes, and other artifacts
        from Slack into the team's Notion workspace.

        Content transformation logic:
            The ``content`` string is split on double newlines (``\\n\\n``),
            which is the standard paragraph separator in plain text.  Each
            non-empty chunk becomes a Notion "paragraph" block.  This
            produces clean, readable pages from the LLM's text output.

        Why use ``page_id`` as parent type?
            Notion supports two parent types: ``page_id`` (nested page) and
            ``database_id`` (row in a database).  ``page_id`` is used here
            because the bot's typical workflow is to create documentation
            pages under a designated parent page.  Supporting database
            parents would require additional schema (property values), which
            can be added later if needed.

        Args:
            parent_id: Parent page or database ID
            title: Page title
            content: Page content (plain text, split into paragraphs)

        Returns:
            Created page information with ``success``, ``id``, ``url``, and
            ``title`` keys on success, or ``success`` and ``error`` keys on
            failure.
        """
        url = f"{NOTION_API_BASE}/pages"

        # ------------------------------------------------------------------
        # Build Notion "children" blocks from plain text.
        # Each paragraph (separated by double newlines) becomes a Notion
        # paragraph block.  Empty chunks are skipped to avoid blank blocks.
        # ------------------------------------------------------------------
        children = []
        for paragraph in content.split("\n\n"):
            paragraph = paragraph.strip()
            if paragraph:
                # Each block follows Notion's required schema:
                #   object  -> "block"
                #   type    -> "paragraph"
                #   paragraph.rich_text -> array of text objects
                children.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": paragraph}}]
                    },
                })

        # ------------------------------------------------------------------
        # Assemble the full page creation payload.
        # ------------------------------------------------------------------
        payload = {
            # ``parent`` specifies where the new page lives in the Notion
            # hierarchy.  Using ``page_id`` nests it under another page.
            "parent": {"page_id": parent_id},
            # ``properties.title`` is the only required property for a page
            # (as opposed to a database row, which may have many properties).
            "properties": {
                "title": {
                    "title": [{"type": "text", "text": {"content": title}}]
                }
            },
            # ``children`` holds the page body as an ordered list of blocks.
            "children": children,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=self._headers) as resp:
                    if resp.status == 200:
                        # Notion returns 200 (not 201) for page creation.
                        data = await resp.json()
                        logger.info(f"Created Notion page: {title}")
                        return {
                            "success": True,
                            "id": data.get("id"),
                            # The URL lets the agent share a direct link
                            # back in Slack so users can click through.
                            "url": data.get("url"),
                            "title": title,
                        }
                    else:
                        # Return the error as a structured dict so the LLM
                        # agent can read and report the failure message.
                        error_body = await resp.text()
                        logger.error(f"Notion API error {resp.status}: {error_body}")
                        return {
                            "success": False,
                            "error": f"Notion API returned {resp.status}: {error_body}",
                        }

        except Exception as e:
            # Network-level failures are raised as MCPServerError for
            # centralized handling in the agent layer.
            raise MCPServerError(f"Failed to create page: {e}", server_name="notion")

    async def search(self, query: str) -> List[Dict[str, Any]]:
        """Search Notion pages.

        Sends a text query to the Notion Search API and returns matching
        pages.  The agent uses this to check whether documentation already
        exists before creating a new page, avoiding duplicates.

        Why ``page_size=10``?
            Returning 10 results balances completeness with token cost.
            The agent rarely needs more than a handful of results to
            determine whether a topic is already documented.

        Design note on error handling:
            Like ``GitHubMCPClient.list_issues``, this method returns a
            list, so HTTP errors are raised as ``MCPServerError`` rather
            than embedded in the return value.

        Args:
            query: Text to search for across the Notion workspace.

        Returns:
            List of dicts, each with ``id``, ``type`` (page or database),
            and ``url`` keys.

        Raises:
            MCPServerError: On HTTP errors or network failures.
        """
        url = f"{NOTION_API_BASE}/search"
        # The Notion Search API uses POST (not GET) with a JSON body.
        # ``page_size`` limits results to avoid fetching the entire workspace.
        payload = {"query": query, "page_size": 10}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=self._headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results = data.get("results", [])
                        logger.info(f"Notion search returned {len(results)} results")
                        # Map to a minimal representation to keep the payload
                        # lean for the LLM agent.
                        return [
                            {
                                "id": item.get("id"),
                                "type": item.get("object"),
                                "url": item.get("url"),
                            }
                            for item in results
                        ]
                    else:
                        error_body = await resp.text()
                        raise MCPServerError(
                            f"Notion API returned {resp.status}: {error_body}",
                            server_name="notion",
                        )

        except MCPServerError:
            # Re-raise MCPServerError as-is to prevent the generic
            # ``except Exception`` below from double-wrapping it with
            # a less specific message.
            raise
        except Exception as e:
            # Catch-all for network errors, DNS failures, timeouts, etc.
            raise MCPServerError(f"Failed to search: {e}", server_name="notion")
