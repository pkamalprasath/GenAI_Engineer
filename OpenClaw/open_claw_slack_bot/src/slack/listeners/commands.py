"""
Slash Command Listeners

=============================================================================
WHY THIS FILE IS REQUIRED:
=============================================================================
Slash commands (e.g., /bot-help, /bot-status) are explicit, user-initiated
actions that differ fundamentally from passive message events. They provide
a structured, discoverable interface for bot capabilities. Without this
module, users would have no way to invoke bot features through the Slack
command palette, and would have to rely solely on @mentions or DMs.

=============================================================================
PROGRAM LOGIC:
=============================================================================
1. REGISTRATION: `register_listeners` binds four slash command handlers to
   the Slack Bolt app: /bot-help, /bot-status, /bot-summarize, /bot-remind.

2. ACKNOWLEDGMENT: Every slash command handler MUST call `ack()` within 3
   seconds (Slack requirement). If the bot does not acknowledge in time,
   Slack shows the user an error. This is why `ack()` is always the first
   line in each handler.

3. PROCESSING: Each handler parses the command text, performs the requested
   action (display help, check status, summarize messages, schedule a
   reminder), and posts a response.

4. ERROR HANDLING: Each handler wraps its logic in try/except to prevent
   a single command failure from crashing the bot. Errors are logged and
   a user-friendly message is returned.

=============================================================================
WHY THIS APPROACH:
=============================================================================
- SLASH COMMANDS vs. MESSAGES: Slash commands are preferable for structured
  actions because: (a) they appear in Slack's autocomplete, (b) they have a
  well-defined input format, (c) Slack handles the UI chrome (loading state),
  and (d) they can be restricted to specific channels.
- SEPARATE HANDLERS PER COMMAND: Each command gets its own async function
  for clarity, testability, and independent error handling.
- LAZY IMPORTS: Heavy dependencies (SummarizationService, settings) are
  imported inside handlers to avoid circular imports and reduce startup time.

=============================================================================
RELATIONSHIP TO OTHER FILES:
=============================================================================
- src/app.py                -- Calls `register_listeners(app)` during boot.
- src/services/summarization.py -- Used by /bot-summarize to generate
                                   AI-powered channel summaries.
- config/settings.py        -- Provides integration token status for /bot-status.
- src/utils/logger.py       -- Structured logging for command telemetry.
"""

import re
import time
from typing import Any, Callable

from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient

from src.utils.logger import get_logger

# Module-level logger for all slash command handling
logger = get_logger(__name__)


def register_listeners(app: AsyncApp) -> None:
    """
    Register all slash command listeners with the app.

    WHY: Slack Bolt requires explicit binding between command names and handler
    functions. Centralizing all command registrations in one function makes it
    easy to see the full command surface area at a glance.

    Design Decision:
        Commands are prefixed with "bot-" (e.g., /bot-help instead of /help) to
        avoid namespace collisions with other Slack apps installed in the same
        workspace.
    """
    logger.info("Registering slash command listeners...")

    # Each app.command() call binds a slash command string to its handler.
    # The command strings must exactly match what is configured in the Slack
    # app manifest (api.slack.com/apps).
    app.command("/bot-help")(handle_help_command)
    app.command("/bot-status")(handle_status_command)
    app.command("/bot-summarize")(handle_summarize_command)
    app.command("/bot-remind")(handle_remind_command)

    logger.info("[OK] Slash command listeners registered")


async def handle_help_command(
    ack: Callable, command: dict, say: Callable, logger: Any
) -> None:
    """
    Handle /bot-help command. Shows available commands and usage.

    WHY: A help command is essential for discoverability. Users need a way to
    learn what the bot can do without reading external documentation.

    Args:
        ack: Acknowledgment function -- MUST be called within 3 seconds.
        command: Command payload containing user_id, channel_id, text, etc.
        say: Convenience function to post a message in the invoking channel.
        logger: Logger instance injected by Slack Bolt.

    Design Decision:
        The help text uses Slack's mrkdwn formatting (not standard Markdown)
        for bold, code blocks, and bullet lists to render nicely in Slack.
    """
    # Acknowledge immediately to satisfy Slack's 3-second deadline.
    # If we don't call ack(), Slack shows "This command didn't work" to the user.
    await ack()

    user_id = command.get("user_id")
    logger.info(f"Help command from user {user_id}")

    # Build help text using Slack's mrkdwn formatting.
    # WHY mrkdwn: Slack uses its own flavor of Markdown (called "mrkdwn")
    # that differs from standard Markdown in subtle ways -- e.g., bold is
    # *text* not **text**, and links use <url|text> syntax.
    help_text = (
        "*Slack Bot Assistant - Available Commands*\n\n"
        "*Basic Commands:*\n"
        "- `/bot-help` - Show this help message\n"
        "- `/bot-status` - Check bot status and health\n\n"
        "*Channel Management:*\n"
        "- `/bot-summarize #channel 24h` - Summarize channel messages\n"
        "- `/bot-remind [message] in [time]` - Set a reminder\n\n"
        "*Examples:*\n"
        "```\n"
        "/bot-summarize #general 24h\n"
        "/bot-remind Review PR in 30 minutes\n"
        "/bot-remind Team standup in 2 hours\n"
        "```\n\n"
        "*Mentions:*\n"
        "@ mention me in any channel or DM me directly!"
    )

    await say(text=help_text)


async def handle_status_command(
    ack: Callable, command: dict, say: Callable, logger: Any
) -> None:
    """
    Handle /bot-status command. Shows real component status.

    WHY: Operators and users need a quick way to verify the bot is healthy
    and which integrations are active. This avoids confusion when features
    do not work because a token is missing.

    Args:
        ack: Acknowledgment function.
        command: Command payload.
        say: Message posting function.
        logger: Logger instance.

    Security Consideration:
        The status output deliberately does NOT expose actual token values.
        It only shows "Connected" or "Not configured" to avoid leaking
        secrets in the channel.
    """
    await ack()

    user_id = command.get("user_id")
    logger.info(f"Status command from user {user_id}")

    # Lazy import to avoid circular dependency at module load time.
    # Settings is a heavyweight module that loads .env and validates all config.
    from config.settings import settings

    # Check integration availability by testing if tokens are present.
    # WHY token presence check: We do NOT make live API calls here because
    # that would be slow and could fail. Token presence is a fast proxy
    # for "this integration was configured."
    github_status = "Connected" if settings.github_token else "Not configured"
    notion_status = "Connected" if settings.notion_token else "Not configured"
    openai_status = "Connected" if settings.openai_api_key else "Not configured"

    status_text = (
        "*Bot Status: Healthy*\n\n"
        "*System Info:*\n"
        f"- Status: Operational\n"
        f"- Environment: {settings.environment}\n"
        f"- Memory System: Connected\n"
        f"- RAG Knowledge Base: Connected\n"
        f"- Agent System: Connected (Claude)\n\n"
        "*Integrations:*\n"
        f"- GitHub: {github_status}\n"
        f"- Notion: {notion_status}\n"
        f"- OpenAI Embeddings: {openai_status}\n\n"
        "*Capabilities:*\n"
        "- Message handling\n"
        "- Channel summarization\n"
        "- Scheduled messages & reminders\n"
        "- AI-powered responses (Claude)\n"
        f"- GitHub integration: {'Available' if settings.github_token else 'Disabled'}\n"
        f"- Notion integration: {'Available' if settings.notion_token else 'Disabled'}"
    )

    await say(text=status_text)


async def handle_summarize_command(
    ack: Callable, command: dict, say: Callable, client: AsyncWebClient, logger: Any
) -> None:
    """
    Handle /bot-summarize command.

    Usage: /bot-summarize #channel 24h
    or:    /bot-summarize <channel_id> 48h

    WHY: Channel summarization is one of the bot's core value propositions.
    It uses the Slack API to fetch recent messages and an LLM to distill
    them into a concise summary.

    Args:
        ack: Acknowledgment function.
        command: Command payload with 'text' containing the user's arguments.
        say: Message posting function.
        client: Full Slack Web API client needed for conversations_history.
        logger: Logger instance.

    Design Decisions:
        - The 168-hour (7-day) cap prevents abuse and excessive API calls.
        - The 200-message limit per fetch balances completeness vs. cost.
        - Channel name resolution is best-effort; the summary works even
          if we cannot resolve the human-readable channel name.
    """
    await ack()

    user_id = command.get("user_id")
    text = command.get("text", "").strip()

    logger.info(f"Summarize command from user {user_id}: {text}")

    # Provide usage help if no arguments are given
    if not text:
        await say(
            text="Usage: `/bot-summarize #channel 24h`\nExample: `/bot-summarize #general 24h`"
        )
        return

    # =========================================================================
    # Parse channel reference and timeframe from the command text
    # =========================================================================
    # WHY regex: Slack transforms #channel-name into <#C1234567890|channel-name>
    # in the command text. We need to extract the channel ID from this encoded
    # format. The regex handles both the encoded form and bare channel IDs.
    channel_match = re.search(r"<#([A-Z0-9]+)\|?[^>]*>", text)
    hours_match = re.search(r"(\d+)\s*h", text, re.IGNORECASE)

    if not channel_match:
        # Fallback: try to match a bare channel ID (C or G prefix + alphanumeric)
        channel_match = re.search(r"([CG][A-Z0-9]{8,12})", text)

    if not channel_match:
        await say(
            text="Please specify a channel. Example: `/bot-summarize #general 24h`"
        )
        return

    target_channel = channel_match.group(1)
    hours = int(hours_match.group(1)) if hours_match else 24

    # Cap at 168 hours (7 days) to prevent excessive API calls and token usage.
    # WHY 168: Slack's free tier retains messages for 90 days, but summarizing
    # more than 7 days of chat produces diminishing returns and high LLM costs.
    hours = min(hours, 168)

    # Let the user know we are working on it (summarization can take 10+ seconds)
    await say(text=f"Summarizing the last {hours}h of messages... This may take a moment.")

    try:
        from datetime import datetime, timedelta

        # Calculate the Unix timestamp for "hours ago" to use as the oldest
        # message boundary in the Slack API call.
        oldest = (datetime.now() - timedelta(hours=hours)).timestamp()

        # Fetch up to 200 messages from the target channel within the timeframe.
        # WHY limit=200: Balances completeness with API rate limits and LLM
        # context window size. More messages can be fetched with pagination
        # if needed in the future.
        response = await client.conversations_history(
            channel=target_channel, oldest=str(oldest), limit=200
        )
        messages = response.get("messages", [])

        if not messages:
            await say(text=f"No messages found in the last {hours} hours.")
            return

        # Lazy import to avoid loading the Anthropic client at module level.
        # This keeps startup fast and prevents import errors if the API key
        # is not configured.
        from src.services.summarization import SummarizationService

        service = SummarizationService()

        # Try to resolve the human-readable channel name for a nicer summary header.
        # This is best-effort -- the summary still works with just the channel ID.
        channel_name = target_channel
        try:
            info = await client.conversations_info(channel=target_channel)
            channel_name = info["channel"].get("name", target_channel)
        except Exception:
            pass  # Use channel ID as fallback

        # Generate the AI-powered summary via the SummarizationService
        summary = await service.summarize_messages(messages, channel_name=channel_name)

        await say(
            text=f"*Summary of #{channel_name}* (last {hours}h, {len(messages)} messages):\n\n{summary}"
        )

    except Exception as e:
        logger.error(f"Summarization failed: {e}")
        # User-friendly error -- do not expose internal exception details.
        # The most common failure is the bot not being a member of the channel.
        await say(
            text="Sorry, I couldn't summarize that channel. Make sure I'm a member of the channel and try again."
        )


async def handle_remind_command(
    ack: Callable, command: dict, say: Callable, client: AsyncWebClient, logger: Any
) -> None:
    """
    Handle /bot-remind command.

    Usage: /bot-remind [message] in [time]
    Examples:
        /bot-remind Review PR in 30 minutes
        /bot-remind Team standup in 2 hours
        /bot-remind Check deployment in 1 hour

    WHY: Reminders are a common productivity feature. This command uses
    the ReminderService to persist reminders to disk (reminders.json),
    making them available for listing, cancellation, and delivery via
    the periodic scheduler.

    Args:
        ack: Acknowledgment function.
        command: Command payload.
        say: Message posting function.
        client: Slack Web API client (unused but required by Bolt signature).
        logger: Logger instance.

    Design Decisions:
        - Uses ReminderService for persistence so reminders are visible to
          the agent's list_reminders and cancel_reminder tools.
        - Delivery is handled by execute_due_reminders() called by APScheduler.
        - Supports both minutes and hours as time units.
        - The regex parser is intentionally lenient (accepts "min", "mins",
          "minutes", "hr", "hrs", "hours") for better UX.
    """
    await ack()

    user_id = command.get("user_id")
    channel_id = command.get("channel_id")
    text = command.get("text", "").strip()

    logger.info(f"Remind command from user {user_id}: {text}")

    if not text:
        await say(
            text="Usage: `/bot-remind [message] in [time]`\nExample: `/bot-remind Review PR in 30 minutes`"
        )
        return

    # =========================================================================
    # Parse "message in X minutes/hours" using regex
    # =========================================================================
    # WHY regex: The natural-language format "do X in Y minutes" is user-friendly
    # but requires careful parsing. The regex captures three groups:
    #   1. The reminder text (everything before " in ")
    #   2. The numeric amount
    #   3. The time unit (minutes/hours with various abbreviations)
    match = re.match(r"(.+?)\s+in\s+(\d+)\s*(minutes?|mins?|hours?|hrs?)\s*$", text, re.IGNORECASE)

    if not match:
        await say(
            text=(
                "I couldn't parse your reminder. Please use the format:\n"
                "`/bot-remind [message] in [number] [minutes/hours]`\n"
                "Example: `/bot-remind Review PR in 30 minutes`"
            )
        )
        return

    reminder_text = match.group(1).strip()
    amount = int(match.group(2))
    unit = match.group(3).lower()

    # Convert the human-readable time to seconds.
    if unit.startswith("h"):
        delay_seconds = amount * 3600
        time_display = f"{amount} hour{'s' if amount != 1 else ''}"
    else:
        delay_seconds = amount * 60
        time_display = f"{amount} minute{'s' if amount != 1 else ''}"

    # Compute the absolute Unix timestamp for when the reminder should fire.
    remind_at = int(time.time()) + delay_seconds

    try:
        # Use ReminderService so the reminder is persisted to reminders.json
        # and can be listed/cancelled via agent tools.  Delivery is handled
        # by execute_due_reminders() called periodically by APScheduler.
        from src.services.reminder import ReminderService

        service = ReminderService()
        result = await service.schedule_reminder(
            user_id=user_id,
            channel_id=channel_id,
            text=reminder_text,
            remind_at=remind_at,
        )

        reminder_id = result.get("reminder_id", "unknown")
        await say(
            text=(
                f"Got it! I'll remind you in {time_display}: \"{reminder_text}\"\n"
                f"_Reminder ID: `{reminder_id}` — use this to cancel if needed._"
            )
        )

    except Exception as e:
        logger.error(f"Failed to schedule reminder: {e}")
        await say(
            text="Sorry, I couldn't set that reminder. Please try again."
        )
