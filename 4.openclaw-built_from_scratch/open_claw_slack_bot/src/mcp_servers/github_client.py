"""
GitHub MCP Client

WHY THIS FILE IS REQUIRED:
    This module provides the Slack bot with the ability to interact with GitHub
    -- specifically, to create and list issues.  Many engineering teams use
    Slack as their primary communication hub and GitHub as their project
    tracker.  By connecting the two, the AI agent can automatically create
    GitHub issues from Slack conversations (e.g., a bug report in Slack
    becomes a tracked issue in GitHub) and pull issue lists into Slack threads
    for stand-ups or triage.

PROGRAM LOGIC:
    1. ``GitHubMCPClient`` is constructed with a Personal Access Token (PAT)
       from centralized settings.  The token and standard headers are stored
       once and reused for every request.
    2. ``create_issue`` builds a JSON payload and POSTs it to the GitHub REST
       API v3.  On success (HTTP 201) it returns the new issue's number and URL;
       on failure it returns a structured error dict.
    3. ``list_issues`` GETs issues from a repository, with optional state
       filtering and pagination.  Results are mapped to a minimal dict to keep
       payloads small for the LLM agent.
    4. Each method creates a fresh ``aiohttp.ClientSession`` per call.  See
       design notes below for rationale.

WHY THIS APPROACH:
    * ``aiohttp`` over ``requests`` -- The entire application is async (Slack
      events, MCP tool calls, RAG retrieval).  Using ``aiohttp`` avoids
      blocking the event loop.  The ``requests`` library is synchronous and
      would require wrapping every call in ``asyncio.to_thread``.
    * A new ``ClientSession`` per method call -- While reusing a session is
      more efficient, it requires careful lifecycle management (create on
      init, close on shutdown).  Since GitHub API calls are infrequent
      (a few per conversation), the overhead of a new session is negligible,
      and it avoids the risk of using a closed session after a timeout.
    * Returning dicts instead of raising on HTTP errors -- The tools are
      consumed by an LLM agent that cannot catch exceptions.  A dict with
      ``{"success": False, "error": "..."}`` gives the agent actionable
      information to recover or inform the user.
    * ``MCPServerError`` is raised only for truly unexpected failures (network
      down, DNS failure) -- things the agent cannot reasonably handle.

SECURITY CONSIDERATIONS:
    * The GitHub PAT (``settings.github_token``) grants repository access.
      It is loaded from environment configuration and NEVER logged or
      returned in API responses.
    * The ``Authorization`` header uses the ``token`` scheme for PATs.
      For GitHub Apps, this would need to be ``Bearer`` with a JWT.
    * ``repo`` parameters are expected in ``owner/repo`` format.  If user
      input flows into this parameter, it should be validated to prevent
      path-traversal-style attacks (e.g., ``../../other-org/other-repo``).
    * The ``User-Agent`` header is required by GitHub's API; we set it to a
      descriptive identifier rather than leaking internal details.

RELATIONSHIP TO OTHER FILES:
    - ``config/settings.py``       -- Supplies ``github_token``.
    - ``src/agents/``              -- The agent orchestration layer uses this
                                      client to create/list issues as part of
                                      tool execution.
    - ``src/utils/exceptions.py``  -- Defines ``MCPServerError``.
    - ``src/utils/logger.py``      -- Structured logging.
    - ``src/mcp_servers/slack_server.py`` -- Sibling MCP integration; the
                                      agent may read a Slack message and then
                                      call GitHub to create an issue from it.

Real GitHub API integration using aiohttp.
Only initialized when GITHUB_TOKEN is configured.
"""

import aiohttp
from typing import Dict, Any, List, Optional

from config.settings import settings
from src.utils.logger import get_logger
from src.utils.exceptions import MCPServerError

logger = get_logger(__name__)

# GitHub REST API v3 base URL.  All endpoint paths are appended to this.
# Using a constant avoids magic strings scattered across methods.
GITHUB_API_BASE = "https://api.github.com"


class GitHubMCPClient:
    """Client for GitHub API operations.

    This client wraps the GitHub REST API v3 and exposes the subset of
    operations that the Slack bot agent needs.  It is intentionally thin --
    each method maps to a single API endpoint with minimal transformation.

    Design decision -- why not use PyGithub or ghapi?
        Third-party GitHub libraries add dependencies and often lag behind
        API changes.  Since we only need two endpoints (create issue, list
        issues), raw ``aiohttp`` calls are simpler, lighter, and easier to
        audit for security.
    """

    def __init__(self):
        """Initialize the GitHub client with authentication headers.

        The Personal Access Token (PAT) is read from centralized settings.
        Headers are pre-built once because they are identical for every
        request:
          - ``Authorization`` authenticates the request.
          - ``Accept`` pins the API version to v3 JSON format.
          - ``User-Agent`` is required by GitHub (requests without one are
            rejected).

        Security note:
            The token is stored in ``self.token`` for potential reuse but is
            never serialized, logged, or exposed in tool responses.
        """
        self.token = settings.github_token
        self._headers = {
            # PAT authentication scheme for GitHub REST API.
            "Authorization": f"token {self.token}",
            # Pin to GitHub REST API v3 JSON response format.
            "Accept": "application/vnd.github.v3+json",
            # GitHub requires a User-Agent header; without it, requests
            # receive a 403 Forbidden response.
            "User-Agent": "slack-bot-assistant",
        }
        logger.info("GitHub MCP client initialized")

    async def create_issue(
        self, repo: str, title: str, body: str, labels: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create a GitHub issue.

        This is the primary integration point between Slack and GitHub.
        The agent can extract action items or bug reports from a Slack
        conversation and create tracked GitHub issues automatically.

        Why return the HTML URL?
            The ``html_url`` is the human-readable issue link (e.g.,
            https://github.com/org/repo/issues/42).  The agent can post
            this back to Slack so team members can click through directly.

        Args:
            repo: Repository in owner/repo format
            title: Issue title
            body: Issue description
            labels: Optional list of labels

        Returns:
            Created issue information with ``success``, ``number``, ``url``,
            and ``title`` keys on success, or ``success`` and ``error`` keys
            on failure.
        """
        url = f"{GITHUB_API_BASE}/repos/{repo}/issues"

        # Build the request payload.  Labels are optional, so we only
        # include them if provided to keep the payload minimal.
        payload: Dict[str, Any] = {"title": title, "body": body}
        if labels:
            payload["labels"] = labels

        try:
            # Create a fresh ClientSession for this request.  See module
            # docstring for rationale on per-call sessions.
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=self._headers) as resp:
                    if resp.status == 201:
                        # HTTP 201 Created -- the issue was successfully created.
                        data = await resp.json()
                        logger.info(f"Created GitHub issue #{data['number']} in {repo}")
                        return {
                            "success": True,
                            "number": data["number"],
                            "url": data["html_url"],
                            "title": data["title"],
                        }
                    else:
                        # Non-201 status indicates an API-level error (e.g.,
                        # 404 repo not found, 422 validation error).  We
                        # return it as data so the agent can report it.
                        error_body = await resp.text()
                        logger.error(f"GitHub API error {resp.status}: {error_body}")
                        return {
                            "success": False,
                            "error": f"GitHub API returned {resp.status}: {error_body}",
                        }

        except Exception as e:
            # Network-level or unexpected failures are raised as
            # MCPServerError for centralized error handling.
            raise MCPServerError(f"Failed to create issue: {e}", server_name="github")

    async def list_issues(
        self, repo: str, state: str = "open", limit: int = 10
    ) -> List[Dict[str, Any]]:
        """List issues from a repository.

        Returns a compact representation of each issue (number, title, state,
        URL) that the agent can present in a Slack message or use for triage
        decisions.

        Why cap ``per_page`` at 100?
            GitHub's API enforces a maximum of 100 results per page.
            ``min(limit, 100)`` ensures we never request more than the API
            allows, avoiding a 422 validation error.

        Design note on error handling:
            Unlike ``create_issue``, this method raises ``MCPServerError``
            for HTTP errors rather than returning a dict.  This is because
            ``list_issues`` returns a list (not a dict), so there is no
            natural place to embed an error field.  The calling agent layer
            catches ``MCPServerError`` and converts it to an error message.

        Args:
            repo:  Repository in owner/repo format.
            state: Issue state filter -- "open", "closed", or "all".
            limit: Maximum number of issues to return (capped at 100 by
                   the GitHub API).

        Returns:
            List of issue dicts, each with ``number``, ``title``, ``state``,
            and ``url`` keys.

        Raises:
            MCPServerError: On HTTP errors or network failures.
        """
        url = f"{GITHUB_API_BASE}/repos/{repo}/issues"
        # Clamp limit to the GitHub API maximum of 100 results per page.
        params = {"state": state, "per_page": min(limit, 100)}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=self._headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        logger.info(f"Listed {len(data)} issues from {repo}")
                        # Map each issue to a minimal dict to reduce token
                        # usage when the agent processes the results.
                        return [
                            {
                                "number": issue["number"],
                                "title": issue["title"],
                                "state": issue["state"],
                                "url": issue["html_url"],
                            }
                            for issue in data
                        ]
                    else:
                        error_body = await resp.text()
                        raise MCPServerError(
                            f"GitHub API returned {resp.status}: {error_body}",
                            server_name="github",
                        )

        except MCPServerError:
            # Re-raise MCPServerError as-is to avoid double-wrapping.
            # Without this, the generic ``except Exception`` below would
            # catch and re-wrap it with a less specific message.
            raise
        except Exception as e:
            # Catch-all for network errors, DNS failures, timeouts, etc.
            raise MCPServerError(f"Failed to list issues: {e}", server_name="github")
