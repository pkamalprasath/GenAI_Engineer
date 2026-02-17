"""
Issue Detection Service
=======================

WHY THIS FILE IS REQUIRED:
    In team Slack channels, bugs, blockers, and problems are often reported
    informally in conversation rather than through formal ticket systems.
    This service bridges that gap by using Claude (LLM) to read through
    channel messages, extract structured issue data, and optionally push
    those issues into GitHub as tickets — fully automating the triage path
    from "someone mentioned a bug in chat" to "there's a GitHub issue for it."

PROGRAM LOGIC (high-level flow):
    1. Receive a list of raw Slack messages (dicts with user, text, ts keys).
    2. Format them into a human-readable prompt for Claude.
    3. Ask Claude to return a JSON array of detected issues, each with
       title, description, severity, labels, source user, and source text.
    4. Parse and validate Claude's JSON response defensively (LLMs sometimes
       return extra text, code fences, or invalid values).
    5. Optionally, for each issue above a severity threshold, automatically
       create a GitHub issue via the GitHubMCPClient.

WHY THIS APPROACH:
    - LLM-powered analysis is chosen over keyword matching because
      conversations are nuanced — "this is totally broken" means something
      different from "let's break this into smaller tasks."  An LLM can
      understand context, sarcasm, and implicit references that regex cannot.
    - JSON output is used (not free-form text) so the results are
      machine-readable and can feed into downstream automation (GitHub, Jira).
    - The GitHub integration is CONDITIONAL (graceful degradation): if no
      GITHUB_TOKEN is set, the service still works for detection-only mode.
    - Severity filtering uses an ordered tuple so the threshold comparison
      is a simple index comparison (critical=0 < high=1 < medium=2 < low=3).

SECURITY CONSIDERATIONS:
    - Log injection prevention: issue titles from Claude could contain
      newlines or ANSI codes that corrupt log files. We sanitize via
      _sanitize_log_value() before any logger call that includes user data.
    - Severity validation: Claude might return unexpected severity values.
      We normalize them to "medium" rather than crashing with ValueError.
    - Prompt format uses double braces {{}} in the example JSON so Python's
      str.format() doesn't interpret them as template variables.
"""

import json
from typing import List, Dict, Any

from anthropic import AsyncAnthropic

from config.settings import settings
from src.utils.logger import get_logger
from src.utils.exceptions import IssueDetectionError

logger = get_logger(__name__)

# ──────────────────────────────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────────────────────────────

# Ordered from most severe to least.  Used for threshold filtering:
# an index comparison lets us say "create issues for anything at or above
# threshold X" — e.g. threshold "high" means index 1, so "critical" (0)
# and "high" (1) qualify.
VALID_SEVERITIES = ("critical", "high", "medium", "low")

# The prompt sent to Claude.  Key design decisions:
#   - We request pure JSON output to enable machine parsing.
#   - We include an example so Claude returns the exact schema we need.
#   - Double braces {{}} are Python escape sequences for literal { } inside
#     a str.format() template (the {messages} placeholder is the real one).
#   - We cap at 100 messages in _format_messages() so we don't blow up
#     Claude's context window.
ISSUE_DETECTION_PROMPT = """Analyze the following Slack messages and identify any issues, bugs, blockers, or problems being discussed.

For each issue found, provide:
1. title: A concise title (under 80 characters)
2. description: A clear description of the issue
3. severity: One of "critical", "high", "medium", "low"
4. suggested_labels: A list of relevant labels (e.g., "bug", "blocker", "performance", "security")
5. source_user: The user who reported or mentioned the issue
6. source_text: The original message text that mentions the issue

Return your analysis as a JSON array. If no issues are found, return an empty array [].

Example output:
[
  {{
    "title": "Login page crashes on mobile Safari",
    "description": "Users report the login page throws a white screen on mobile Safari browsers. This appears to be related to a CSS flexbox compatibility issue.",
    "severity": "high",
    "suggested_labels": ["bug", "mobile", "css"],
    "source_user": "U12345",
    "source_text": "The login page is broken on my iPhone..."
  }}
]

Messages to analyze:
{messages}

Return ONLY valid JSON. No additional text or explanation."""


# ──────────────────────────────────────────────────────────────────────
# HELPER: Log sanitization
# ──────────────────────────────────────────────────────────────────────

def _sanitize_log_value(value: str) -> str:
    """
    Strip newlines and carriage returns from a string before it is
    interpolated into a log message.

    WHY:  Issue titles come from Claude's output, which in turn is
    derived from user-written Slack messages.  A malicious or accidental
    newline in a title (e.g. "Bug\\n[ERROR] fake log entry") could inject
    misleading lines into log files.  This helper makes the value safe
    for single-line log output.
    """
    return value.replace("\n", "\\n").replace("\r", "\\r")


# ──────────────────────────────────────────────────────────────────────
# SERVICE CLASS
# ──────────────────────────────────────────────────────────────────────

class IssueDetectionService:
    """
    Analyzes Slack messages for bugs/blockers and optionally creates GitHub issues.

    Architecture:
        - Uses the Anthropic SDK (AsyncAnthropic) to call Claude for analysis.
        - Optionally wraps the GitHubMCPClient to create issues.
        - Both dependencies are conditionally initialized based on settings
          (Anthropic key is always required; GitHub token is optional).

    Typical usage from the agent's tool registry:
        service = IssueDetectionService()
        issues = await service.detect_issues(messages, channel_name="general")
    """

    def __init__(self):
        # AsyncAnthropic is the official async client for the Anthropic API.
        # We always need it because detection itself requires Claude.
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)

        # GitHub integration is optional — only initialized if a token exists.
        # This follows the "conditional initialization" pattern used across
        # the project (see also MCPRegistry, NotionIntegrationService).
        # We use a lazy import to avoid import-time side effects when the
        # GitHub module reads its own settings or opens connections.
        self._github_client = None

        if settings.github_token:
            from src.mcp_servers.github_client import GitHubMCPClient
            self._github_client = GitHubMCPClient()
            logger.info("Issue detection service initialized with GitHub integration")
        else:
            logger.info("Issue detection service initialized (no GitHub integration)")

    # ──────────────────────────────────────────────────────────────────
    # PUBLIC: Detect issues (analysis only, no side effects)
    # ──────────────────────────────────────────────────────────────────

    async def detect_issues(
        self, messages: List[Dict[str, Any]], channel_name: str = "channel"
    ) -> List[Dict[str, Any]]:
        """
        Analyze messages and detect potential issues.

        HOW IT WORKS:
            1. Short-circuit if the message list is empty (no API call needed).
            2. Format messages into a single string for the prompt.
            3. Send the prompt to Claude and get a JSON response.
            4. Parse the JSON defensively (strip code fences, validate fields).
            5. Return a list of normalized issue dicts.

        Args:
            messages: List of Slack message dicts (must have "text" key).
            channel_name: Human-readable channel name (for logging only).

        Returns:
            List of issue dicts, each with keys: title, description,
            severity, suggested_labels, source_user, source_text.

        Raises:
            IssueDetectionError: If the Claude API call fails.
        """
        if not messages:
            logger.info("No messages to analyze for issues")
            return []

        # %s-style logging is preferred over f-strings in this project because
        # the logging module can skip string interpolation entirely if the
        # message's log level is below the configured threshold — a small
        # but useful performance optimization.
        logger.info("Analyzing %d messages from #%s for issues", len(messages), channel_name)

        formatted = self._format_messages(messages)
        prompt = ISSUE_DETECTION_PROMPT.format(messages=formatted)

        try:
            # We use Claude Sonnet for a good balance of speed and quality.
            # The response is expected to be pure JSON (no tool_use needed
            # because we handle parsing ourselves for maximum flexibility).
            response = await self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )

            raw_text = response.content[0].text.strip()
            issues = self._parse_issues(raw_text)

            logger.info("Detected %d issues in #%s", len(issues), channel_name)
            return issues

        except IssueDetectionError:
            # Already a domain error — let it propagate unchanged.
            raise
        except Exception as e:
            # Wrap unexpected errors (network, auth, parsing) into our
            # domain exception so callers have a single error type to handle.
            logger.error("Issue detection failed: %s", e)
            raise IssueDetectionError(f"Failed to detect issues: {e}")

    # ──────────────────────────────────────────────────────────────────
    # PUBLIC: Detect issues AND create GitHub tickets
    # ──────────────────────────────────────────────────────────────────

    async def detect_and_create_issues(
        self,
        messages: List[Dict[str, Any]],
        repo: str,
        channel_name: str = "channel",
        auto_create_threshold: str = "high",
    ) -> Dict[str, Any]:
        """
        End-to-end pipeline: detect → filter → create GitHub issues.

        HOW IT WORKS:
            1. Validate that GitHub is configured and the threshold is valid.
            2. Call detect_issues() to get the raw issue list.
            3. Filter issues by severity: only those at or above the threshold
               qualify for automatic GitHub issue creation.
            4. For each qualifying issue, build a Markdown body and call the
               GitHub MCP client to create the issue.
            5. Return a summary dict containing all detected issues, the subset
               that were pushed to GitHub, and success/failure counts.

        WHY THRESHOLD FILTERING:
            Not every detected issue warrants a GitHub ticket.  "Low" issues
            may be minor annoyances that don't need tracking.  The threshold
            parameter lets the user (or the agent) control what gets created.
            The severity tuple is ordered critical < high < medium < low by
            index, so we create issues where index <= threshold_index.

        Args:
            messages: List of Slack message dicts.
            repo: GitHub repository in "owner/repo" format (e.g. "acme/api").
            channel_name: Source channel name for the issue body.
            auto_create_threshold: Minimum severity to auto-create.

        Returns:
            Dict with keys: detected_issues, created_issues,
            total_detected, total_created.

        Raises:
            IssueDetectionError: If GitHub is not configured, threshold is
                invalid, or the detection step fails.
        """
        # Guard: GitHub must be configured for this method.
        if not self._github_client:
            raise IssueDetectionError(
                "GitHub integration not configured. Set GITHUB_TOKEN to enable."
            )

        # Guard: validate the threshold string before we call .index() on it.
        # Without this check, an invalid value like "urgent" would raise
        # ValueError from tuple.index(), which is a confusing error message.
        if auto_create_threshold not in VALID_SEVERITIES:
            raise IssueDetectionError(
                f"Invalid threshold '{auto_create_threshold}'. "
                f"Must be one of {VALID_SEVERITIES}"
            )

        # Step 1: Detect all issues via Claude.
        issues = await self.detect_issues(messages, channel_name)

        if not issues:
            return {"detected_issues": [], "created_issues": []}

        # Step 2: Filter by severity threshold.
        # VALID_SEVERITIES is ordered critical(0), high(1), medium(2), low(3).
        # If threshold is "high" (index 1), we keep issues with index 0 or 1.
        threshold_index = VALID_SEVERITIES.index(auto_create_threshold)
        qualifying_issues = [
            issue for issue in issues
            if VALID_SEVERITIES.index(issue.get("severity", "low")) <= threshold_index
        ]

        # Step 3: Create GitHub issues for qualifying items.
        # We wrap each creation in its own try/except so one failure doesn't
        # prevent the rest from being created — partial success is better
        # than total failure.
        created = []
        for issue in qualifying_issues:
            # Build a Markdown body for the GitHub issue.  We include the
            # channel name, severity, and reporting user for traceability.
            body = (
                f"**Detected from Slack #{channel_name}**\n\n"
                f"{issue['description']}\n\n"
                f"**Severity:** {issue['severity']}\n"
                f"**Reported by:** {issue.get('source_user', 'Unknown')}\n\n"
                f"---\n"
                f"*Auto-created by Slack Bot Issue Detection*"
            )

            try:
                result = await self._github_client.create_issue(
                    repo=repo,
                    title=issue["title"],
                    body=body,
                    labels=issue.get("suggested_labels"),
                )
                created.append({**issue, "github_result": result})
                # Sanitize the title before logging to prevent log injection.
                logger.info("Created GitHub issue: %s", _sanitize_log_value(issue["title"]))
            except Exception as e:
                safe_title = _sanitize_log_value(issue["title"])
                logger.error("Failed to create GitHub issue '%s': %s", safe_title, e)
                created.append({**issue, "github_result": {"success": False, "error": str(e)}})

        return {
            "detected_issues": issues,
            "created_issues": created,
            "total_detected": len(issues),
            "total_created": len([c for c in created if c.get("github_result", {}).get("success")]),
        }

    # ──────────────────────────────────────────────────────────────────
    # PRIVATE: Format messages for the prompt
    # ──────────────────────────────────────────────────────────────────

    def _format_messages(self, messages: List[Dict[str, Any]]) -> str:
        """
        Convert a list of Slack message dicts into a single string for
        the Claude prompt.

        WHY THIS FORMAT:
            Each message is rendered as "[User U123 at 1234567890.123]: text"
            so Claude can see who said what and when.  We cap at 100 messages
            to avoid exceeding Claude's context window (~200k tokens for
            Sonnet, but the prompt + response must fit together).

        Messages with empty text are skipped (e.g. join/leave system messages).
        """
        formatted = []
        for msg in messages[:100]:  # Cap at 100 to protect context window
            user = msg.get("user", "Unknown")
            text = msg.get("text", "")
            ts = msg.get("ts", "")
            if text:
                formatted.append(f"[User {user} at {ts}]: {text}")

        return "\n".join(formatted)

    # ──────────────────────────────────────────────────────────────────
    # PRIVATE: Parse Claude's JSON response
    # ──────────────────────────────────────────────────────────────────

    def _parse_issues(self, raw_text: str) -> List[Dict[str, Any]]:
        """
        Parse Claude's response text into a validated list of issue dicts.

        WHY DEFENSIVE PARSING:
            LLMs don't always follow instructions perfectly.  Common issues:
            - Claude wraps JSON in ```json ... ``` code fences.
            - Claude returns a single object instead of an array.
            - Claude uses invalid severity values like "CRITICAL" or "urgent".
            - Claude omits optional fields like suggested_labels.

            This method handles all of these gracefully, normalizing the
            output so downstream code can trust the schema.

        Returns:
            List of validated issue dicts.  Returns empty list on parse failure
            (we prefer degraded functionality over crashing the agent loop).
        """
        try:
            text = raw_text
            # Strip markdown code fences that Claude sometimes adds.
            # Example: ```json\n[...]\n``` → [...]
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            issues = json.loads(text)

            # Claude occasionally returns a single object instead of an array.
            if not isinstance(issues, list):
                logger.warning("Issue detection response is not a list, wrapping")
                issues = [issues]

            # Validate and normalize each issue dict.
            valid_issues = []
            for issue in issues:
                # Skip anything that isn't a dict with at least a "title" key.
                if not isinstance(issue, dict) or "title" not in issue:
                    continue
                # Ensure all expected keys exist with sensible defaults.
                issue.setdefault("description", "")
                issue.setdefault("suggested_labels", [])
                # Normalize severity: if Claude returned "CRITICAL", "urgent",
                # or any non-standard value, default to "medium" so the
                # threshold comparison in detect_and_create_issues() won't
                # crash with ValueError from tuple.index().
                if issue.get("severity") not in VALID_SEVERITIES:
                    issue["severity"] = "medium"
                valid_issues.append(issue)

            return valid_issues

        except json.JSONDecodeError:
            # Log a safe excerpt of the unparseable response for debugging.
            safe_excerpt = _sanitize_log_value(raw_text[:100])
            logger.warning("Failed to parse issue detection JSON: %s...", safe_excerpt)
            return []
