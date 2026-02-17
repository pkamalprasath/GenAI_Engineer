"""
App Mention Listeners

=============================================================================
WHY THIS FILE IS REQUIRED:
=============================================================================
When a user types "@BotName do something" in a channel, Slack fires an
"app_mention" event (distinct from the generic "message" event). This module
handles those @mention events. Without it, users would have no way to invoke
the bot by name inside a channel -- they would have to use DMs or slash
commands exclusively.

=============================================================================
PROGRAM LOGIC:
=============================================================================
1. REGISTRATION: `register_listeners` binds `handle_app_mention` to the
   Slack "app_mention" event type.

2. TEXT CLEANUP: The raw event text contains the bot mention token
   (e.g., "<@U12345>"). The handler strips this out with a regex so the
   AI agent receives only the user's actual question.

3. EMPTY MENTION HANDLING: If the user only typed "@BotName" with no
   additional text, the bot replies with a helpful prompt listing its
   capabilities instead of sending an empty string to the AI.

4. ACKNOWLEDGMENT: An "eyes" emoji reaction is added immediately to
   signal that the bot saw the mention and is working on a response.

5. AI PROCESSING: Non-empty messages are forwarded to the agent
   orchestrator for LLM-based response generation.

6. RESPONSE DELIVERY: The AI response is posted in a thread to keep the
   main channel clean. Reactions are swapped from "eyes" to "checkmark."

=============================================================================
WHY THIS APPROACH:
=============================================================================
- SEPARATE FROM messages.py: Slack's event model distinguishes "message"
  (all messages) from "app_mention" (@bot specifically). Handling them
  separately avoids duplicate responses (a message that @mentions the bot
  would trigger BOTH event types if not carefully gated).
- THREAD-FIRST REPLIES: Always replying in a thread prevents the bot from
  flooding the channel, especially in busy channels where the bot is
  frequently mentioned.
- DIFFERENT EMOJI: Using "eyes" (instead of hourglass) for mentions gives
  a distinct visual cue that differentiates "@mention" processing from DM
  processing.

=============================================================================
RELATIONSHIP TO OTHER FILES:
=============================================================================
- src/app.py                -- Calls `register_listeners(app)` during boot.
- src/slack/listeners/messages.py -- Handles DM messages (complementary).
                                     messages.py explicitly skips @mentions
                                     to avoid double-responding.
- src/agent/orchestrator.py       -- Provides the AI orchestrator.
- src/utils/validators.py         -- Provides text sanitization.
- src/utils/logger.py             -- Structured logging.
"""

import re
from typing import Any, Callable

from slack_bolt.async_app import AsyncApp
from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient

from src.agent.orchestrator import get_orchestrator
from src.utils.logger import get_logger
from src.utils.validators import sanitize_text

# Module-level logger scoped to this file's namespace
logger = get_logger(__name__)


def register_listeners(app: AsyncApp) -> None:
    """
    Register all app mention listeners with the app.

    WHY: Binding the "app_mention" event to our handler is what makes the bot
    respond when users type @BotName in a channel. Without this registration,
    the app_mention events would be silently dropped by Slack Bolt.

    Args:
        app: AsyncApp instance -- the Slack Bolt application.

    Design Decision:
        We register a single handler for all app_mention events rather than
        trying to route different mentions to different handlers. The handler
        itself decides what to do based on the message content. This keeps
        the registration simple and the routing logic centralized.
    """
    logger.info("Registering app mention listeners...")

    # Bind the "app_mention" event type to our handler function.
    # Slack distinguishes this from "message" events -- app_mention fires
    # ONLY when the bot user is explicitly @mentioned.
    app.event("app_mention")(handle_app_mention)

    logger.info("[OK] App mention listeners registered")


async def handle_app_mention(
    event: dict, say: Callable, client: AsyncWebClient, logger: Any
) -> None:
    """
    Handle app_mention events.

    When the bot is @mentioned, this handler processes the message
    and generates a response.

    Args:
        event: Mention event data from Slack. Key fields:
               - text (str): Full message text INCLUDING the <@BOT_ID> token.
               - user (str): Slack user ID of the person who mentioned the bot.
               - channel (str): Channel ID where the mention occurred.
               - ts (str): Message timestamp (unique message identifier).
               - thread_ts (str|None): Parent thread timestamp, if in a thread.
        say: Function to post message to the same channel.
        client: Slack Web API client for reactions and other API calls.
        logger: Logger instance injected by Slack Bolt.

    Security Considerations:
        - User text is sanitized via `sanitize_text()` before being sent to
          the AI agent to prevent control character injection.
        - Error messages never expose internal exception details to the user.
    """
    # Extract message metadata from the event dictionary
    text = event.get("text", "")
    user_id = event.get("user")
    channel_id = event.get("channel")
    message_ts = event.get("ts")
    thread_ts = event.get("thread_ts")

    logger.info(
        f"Bot mentioned by user {user_id} in channel {channel_id}",
        extra={"user_id": user_id, "channel_id": channel_id, "message_length": len(text)},
    )

    # =========================================================================
    # Remove Bot Mention from Text
    # =========================================================================
    # WHY: The raw text contains the bot's mention token in Slack's encoded
    # format: "<@U123ABC456>". This is meaningless to the AI agent and would
    # confuse the LLM. We strip ALL mention tokens (not just the bot's) to
    # get a clean user message.
    #
    # Example transformation:
    #   "<@U0LAN0Z89> summarize #general" -> "summarize #general"

    # Regex matches Slack's mention format: <@ followed by uppercase
    # alphanumeric ID followed by >
    clean_text = re.sub(r"<@[A-Z0-9]+>", "", text).strip()

    # Sanitize to remove control characters (defense in depth)
    clean_text = sanitize_text(clean_text)

    logger.debug(f"Cleaned mention text: {clean_text}")

    # =========================================================================
    # Acknowledge Receipt
    # =========================================================================
    # WHY: Adding an "eyes" emoji reaction gives the user immediate visual
    # feedback that the bot noticed their mention. This is especially
    # important in busy channels where the response may take several seconds.

    try:
        await client.reactions_add(
            channel=channel_id, name="eyes", timestamp=message_ts  # eyes emoji
        )
    except Exception as e:
        # Non-critical failure -- processing continues even without the reaction.
        # Common cause: bot lacks the reactions:write OAuth scope.
        logger.warning(f"Failed to add reaction: {e}")

    # =========================================================================
    # Process Mention (Invoke Agent)
    # =========================================================================
    # WHY: The core purpose of handling @mentions is to generate a helpful AI
    # response. We delegate to the orchestrator for the actual LLM call,
    # keeping this handler focused on Slack I/O concerns.

    try:
        if not clean_text:
            # User just mentioned the bot without a message (e.g., just "@Bot").
            # Instead of sending an empty string to the AI (which would produce
            # a confusing response), we return a helpful prompt.
            response_text = (
                f"Hi <@{user_id}>!\n\n"
                "You mentioned me, but didn't include a message. How can I help you?\n\n"
                "Try:\n"
                "- Ask me to summarize a channel\n"
                "- Set a reminder\n"
                "- Create a GitHub issue\n"
                "- Or just chat with me!\n\n"
                "Type `/bot-help` to see all my capabilities."
            )
        else:
            # Non-empty message: route to the AI agent for a real response.
            # The orchestrator handles context loading, RAG retrieval, tool
            # execution, and LLM interaction internally.
            orchestrator = get_orchestrator()
            response_text = await orchestrator.process_message(
                user_message=clean_text,
                user_id=user_id,
                channel_id=channel_id,
            )

        # Swap the "eyes" reaction for a "checkmark" to indicate completion.
        # This two-step reaction swap (eyes -> checkmark) gives users a clear
        # visual timeline: "received" -> "done."
        try:
            await client.reactions_remove(channel=channel_id, name="eyes", timestamp=message_ts)
        except SlackApiError as e:
            # "no_reaction" means the reaction was already removed (race condition)
            if e.response["error"] != "no_reaction":
                logger.warning(f"Failed to remove eyes reaction: {e}")

        try:
            await client.reactions_add(
                channel=channel_id, name="white_check_mark", timestamp=message_ts
            )
        except SlackApiError as e:
            # "already_reacted" is harmless
            if e.response["error"] != "already_reacted":
                logger.warning(f"Failed to add checkmark reaction: {e}")

        # Post the response in a thread to keep the main channel tidy.
        # If the mention was already inside a thread, use its thread_ts;
        # otherwise, start a new thread from the mention's own ts.
        await say(text=response_text, thread_ts=thread_ts or message_ts)

        logger.info(f"Responded to mention from user {user_id}")

    except Exception as e:
        # Catch-all error handler ensures the user always gets feedback,
        # even if the AI agent or Slack API fails unexpectedly.
        logger.exception(f"Error handling mention: {e}")

        # Best-effort cleanup of the "eyes" reaction
        try:
            await client.reactions_remove(channel=channel_id, name="eyes", timestamp=message_ts)
        except Exception:
            pass  # Don't mask the original error

        # Post a user-friendly error (no internal details exposed)
        await say(
            text=f"Sorry <@{user_id}>, I encountered an error. Please try again.",
            thread_ts=thread_ts or message_ts,
        )
