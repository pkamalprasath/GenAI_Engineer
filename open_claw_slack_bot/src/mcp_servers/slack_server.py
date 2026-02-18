"""
Custom Slack MCP Server

WHY THIS FILE IS REQUIRED:
    This module exposes Slack API operations as MCP (Model Context Protocol)
    tools.  MCP is a standardized protocol that lets an LLM agent discover and
    invoke external capabilities ("tools") at runtime.  By wrapping Slack
    operations in MCP tool definitions, the AI agent can autonomously decide
    when to read channels, post messages, or schedule messages -- without
    hard-coded if/else logic for each action.

PROGRAM LOGIC:
    1. A ``FastMCP`` server instance is created -- it handles MCP protocol
       details (tool registration, JSON schema generation, request routing).
    2. An ``AsyncWebClient`` is initialized with the bot's Slack OAuth token
       so all tools share a single authenticated HTTP session.
    3. Each tool function is decorated with ``@mcp.tool()``, which
       automatically registers it with the MCP server and generates the
       JSON schema that agents use to understand the tool's parameters.
    4. Every tool follows a consistent pattern:
       - Accept typed parameters.
       - Call the Slack Web API via ``slack_client``.
       - Return a structured dict (success payload or error payload).
       - Log the outcome for observability.

WHY THIS APPROACH:
    * FastMCP -- The ``fastmcp`` library abstracts away the low-level MCP
      transport (stdio / SSE).  This means we only write normal Python
      async functions and the library handles serialization, schema
      publication, and protocol compliance.
    * Slack SDK's AsyncWebClient -- Using the official SDK (rather than raw
      HTTP) gives us automatic rate-limit handling, token refresh, and
      typed responses.  The async variant is essential because MCP tool
      invocations are awaited from an async agent loop.
    * Returning dicts (not raising) on API errors -- Tools are consumed by
      an LLM agent, which cannot catch Python exceptions.  By returning
      ``{"error": ...}`` dicts, the agent can read the error message and
      decide how to recover (e.g., retry, ask the user for clarification).

SECURITY CONSIDERATIONS:
    * The Slack bot token (``settings.slack_bot_token``) is loaded from
      environment configuration and never logged or included in tool
      responses.
    * ``channel_id`` parameters are expected to be Slack-format IDs (e.g.,
      "C01ABCDEF").  The Slack API itself validates them, but callers should
      still sanitize IDs if they originate from untrusted user input.
    * ``post_message`` and ``schedule_message`` send user-provided text
      directly to Slack.  If the bot is deployed in a context where
      untrusted users can invoke these tools, input validation / content
      moderation should be added upstream.

RELATIONSHIP TO OTHER FILES:
    - ``config/settings.py``       -- Provides ``slack_bot_token``.
    - ``src/rag/indexer.py``       -- May consume the messages returned by
                                      ``get_channel_messages`` for indexing.
    - ``src/agents/``              -- The agent orchestration layer discovers
                                      and invokes these tools via MCP.
    - ``src/utils/logger.py``      -- Structured logging.

FastMCP-based server providing Slack operations as MCP tools.
"""

from fastmcp import FastMCP
from typing import Optional, Dict, Any
from slack_sdk.web.async_client import AsyncWebClient

from config.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# MCP Server Initialization
# ---------------------------------------------------------------------------
# ``FastMCP`` is the entry point for a Model Context Protocol server.
# The ``name`` parameter identifies this server when an agent connects to
# multiple MCP servers simultaneously (e.g., slack + github + notion).
mcp = FastMCP(name="slack-mcp-server")

# ---------------------------------------------------------------------------
# Slack Client Initialization
# ---------------------------------------------------------------------------
# A single AsyncWebClient instance is shared across all tool functions.
# The Slack SDK manages connection pooling internally, so creating one
# client is both efficient and thread-safe.
#
# Security: The token is read from ``settings`` (backed by env vars / a
# .env file) -- it is never hard-coded.  ``AsyncWebClient`` transmits
# it via the ``Authorization`` header over HTTPS.
slack_client = AsyncWebClient(token=settings.slack_bot_token)


# ===========================================================================
# MCP Tool Definitions
# ===========================================================================
# Each ``@mcp.tool()``-decorated function becomes a callable tool that an
# LLM agent can invoke.  The decorator introspects the function signature
# and docstring to auto-generate the JSON schema the agent uses to
# understand the tool's purpose and parameters.


@mcp.tool()
async def get_channel_messages(channel_id: str, hours: int = 24) -> Dict[str, Any]:
    """
    Retrieve messages from a Slack channel.

    This is the primary tool the agent uses to gather conversation context.
    The ``hours`` parameter controls how far back to look, defaulting to
    24 hours -- enough for a daily summary without fetching excessive history.

    Why a ``limit=200`` on the API call?
        The Slack ``conversations.history`` endpoint paginates at 200
        messages by default.  For the RAG use case, 200 recent messages
        is a practical upper bound; fetching more would increase latency
        and token cost with diminishing relevance.

    Args:
        channel_id: Channel ID (e.g., C123ABC456)
        hours: Number of hours to look back (default: 24)

    Returns:
        Dictionary with messages and metadata
    """
    # Import inside the function to avoid a module-level dependency on
    # ``datetime`` in every import of this file.  This is a minor
    # optimization for cold-start time in serverless-style deployments.
    from datetime import datetime, timedelta

    # Calculate the earliest timestamp to fetch.  Slack's API accepts
    # ``oldest`` as a Unix timestamp string.
    oldest = (datetime.now() - timedelta(hours=hours)).timestamp()

    try:
        response = await slack_client.conversations_history(
            channel=channel_id, oldest=str(oldest), limit=200
        )

        messages = response["messages"]
        logger.info(f"Retrieved {len(messages)} messages from {channel_id}")

        # Return a structured payload the agent can reason about.
        # Including ``message_count`` lets the agent decide whether there
        # is enough data to summarize without iterating through the list.
        return {"channel_id": channel_id, "message_count": len(messages), "messages": messages}

    except Exception as e:
        # Return the error as data (not an exception) so the LLM agent
        # can read the failure reason and decide how to proceed.
        logger.error(f"Failed to retrieve messages: {e}")
        return {"error": str(e)}


@mcp.tool()
async def post_message(
    channel_id: str, text: str, thread_ts: Optional[str] = None
) -> Dict[str, Any]:
    """
    Post a message to Slack channel.

    This tool lets the agent communicate results, summaries, or alerts back
    to a Slack channel.  The optional ``thread_ts`` parameter enables the
    agent to reply in-thread, keeping conversations organized.

    Security consideration:
        ``text`` is sent to Slack as-is.  If untrusted users can trigger
        this tool with arbitrary text, a content filter should be applied
        upstream to prevent abuse (e.g., @here/@channel spam, phishing
        links).

    Args:
        channel_id: Channel ID
        text: Message text
        thread_ts: Optional thread timestamp

    Returns:
        Message posting result
    """
    try:
        response = await slack_client.chat_postMessage(
            channel=channel_id, text=text, thread_ts=thread_ts
        )

        logger.info(f"Posted message to {channel_id}")
        # Return the timestamp (``ts``) so the caller can reference this
        # message later (e.g., to reply in-thread or add a reaction).
        return {"success": True, "ts": response["ts"], "channel": response["channel"]}

    except Exception as e:
        logger.error(f"Failed to post message: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def schedule_message(channel_id: str, text: str, post_at: int) -> Dict[str, Any]:
    """
    Schedule a message to be posted later.

    Useful for reminders, follow-ups, or time-zone-aware notifications.
    The agent can calculate the correct ``post_at`` timestamp and schedule
    the message without the user needing to stay online.

    Design note:
        ``post_at`` is a Unix timestamp (seconds since epoch).  This is
        the format the Slack API expects.  The agent or upstream code is
        responsible for converting human-readable times into Unix
        timestamps.

    Security consideration:
        Slack enforces that ``post_at`` must be in the future and within
        120 days.  However, a malicious caller could schedule many messages;
        rate-limiting at the application level is advisable.

    Args:
        channel_id: Channel ID
        text: Message text
        post_at: Unix timestamp when to post

    Returns:
        Scheduling result
    """
    try:
        response = await slack_client.chat_scheduleMessage(
            channel=channel_id, text=text, post_at=post_at
        )

        logger.info(f"Scheduled message for {post_at}")
        # Return the scheduled_message_id so it can be cancelled later if
        # needed via ``chat.deleteScheduledMessage``.
        return {
            "success": True,
            "scheduled_message_id": response["scheduled_message_id"],
            "post_at": post_at,
        }

    except Exception as e:
        logger.error(f"Failed to schedule message: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def get_channel_info(channel_id: str) -> Dict[str, Any]:
    """
    Get information about a channel.

    Provides metadata the agent may need to make decisions -- for example,
    whether the channel is private (which affects who can see bot messages)
    or how many members it has (which affects the tone of a summary).

    Args:
        channel_id: Channel ID

    Returns:
        Channel information
    """
    try:
        response = await slack_client.conversations_info(channel=channel_id)

        channel = response["channel"]
        logger.info(f"Retrieved info for channel {channel_id}")

        # Return only the fields the agent is likely to need, rather than
        # the entire raw API response.  This reduces token usage when the
        # agent processes the result and avoids leaking sensitive internal
        # metadata.
        return {
            "id": channel["id"],
            "name": channel.get("name"),
            "is_private": channel.get("is_private", False),
            "member_count": channel.get("num_members", 0),
        }

    except Exception as e:
        logger.error(f"Failed to get channel info: {e}")
        return {"error": str(e)}


@mcp.tool()
async def list_channels() -> Dict[str, Any]:
    """
    List all channels the bot is a member of.

    The agent uses this to discover available channels without the user
    having to provide a channel ID manually.

    Why include both ``public_channel`` and ``private_channel`` types?
        The bot may be invited to private channels.  Listing only public
        channels would make those invisible to the agent.  The Slack API
        only returns channels the bot token has access to, so there is no
        risk of exposing channels the bot should not see.

    Returns:
        List of channels
    """
    try:
        # Request both public and private channels the bot has access to.
        response = await slack_client.conversations_list(types="public_channel,private_channel")

        channels = response["channels"]
        logger.info(f"Retrieved {len(channels)} channels")

        # Return a minimal representation (id + name) to keep the response
        # compact.  The agent can call ``get_channel_info`` for details on
        # any specific channel.
        return {
            "count": len(channels),
            "channels": [{"id": ch["id"], "name": ch.get("name")} for ch in channels],
        }

    except Exception as e:
        logger.error(f"Failed to list channels: {e}")
        return {"error": str(e)}
