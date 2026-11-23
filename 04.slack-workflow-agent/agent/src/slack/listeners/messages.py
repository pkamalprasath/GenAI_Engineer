"""
Message Event Listeners

=============================================================================
WHY THIS FILE IS REQUIRED:
=============================================================================
This module is the primary message-handling entry point for the Slack bot. When
any user sends a message in a channel where the bot is present (or sends a DM),
Slack dispatches a "message" event. Without this listener, the bot would be
completely deaf to regular conversational messages -- it would only respond to
slash commands or @mentions.

=============================================================================
PROGRAM LOGIC:
=============================================================================
1. REGISTRATION: `register_listeners` is called once during app startup
   (from src/app.py). It binds `handle_message_event` to the Slack "message"
   event type via `app.event("message")`.

2. EVENT RECEPTION: When a message arrives, Slack Bolt dispatches it to
   `handle_message_event` with the raw event dict, a `say` convenience
   function, the full Slack Web API client, and a logger.

3. INPUT VALIDATION: The handler immediately extracts and validates all
   user-supplied fields (text, channel_id, user_id). Text is sanitized
   to strip control characters that could cause injection issues.

4. RESPONSE GATING: The bot only responds to direct messages (DMs). It
   deliberately ignores @mentions here because those are handled separately
   by the `mentions.py` listener to avoid duplicate responses.

5. ACKNOWLEDGMENT: Before performing the (potentially slow) AI call, the
   bot adds an hourglass reaction to the message. This gives the user
   immediate feedback that their request was received.

6. AI PROCESSING: The message is routed to the agent orchestrator, which
   uses an LLM to generate a contextual response.

7. RESPONSE DELIVERY: The bot removes the hourglass, adds a checkmark, and
   posts the AI-generated response in the same thread.

=============================================================================
WHY THIS APPROACH:
=============================================================================
- SEPARATION FROM MENTIONS: Slack dispatches both "message" and "app_mention"
  events. Handling them in separate modules prevents double-responses and
  allows different UX flows (e.g., DMs are private and do not need @prefix
  stripping).
- REACTION-BASED UX: Using emoji reactions (hourglass -> checkmark) is a
  Slack-idiomatic pattern that avoids "typing..." indicators and works
  even when the AI takes several seconds to respond.
- THREAD-FIRST REPLIES: Responding in a thread keeps the main channel tidy
  and groups related conversation together.

=============================================================================
RELATIONSHIP TO OTHER FILES:
=============================================================================
- src/app.py            -- Calls `register_listeners(app)` during boot.
- src/slack/listeners/mentions.py -- Handles @mention events (complementary).
- src/slack/listeners/commands.py -- Handles slash commands (complementary).
- src/agent/orchestrator.py       -- Provides the AI orchestrator that
                                     generates the response text.
- src/utils/validators.py         -- Provides input validation/sanitization.
- src/utils/logger.py             -- Provides the structured logger.
- src/slack/middleware/auth.py     -- Filters out bot messages before they
                                     reach this handler (defense in depth).
"""

from typing import Any, Callable

from slack_bolt.async_app import AsyncApp
from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient

from src.agent.orchestrator import get_orchestrator
from src.utils.logger import get_logger
from src.utils.validators import validate_channel_id, validate_text_length, sanitize_text

# Module-level logger -- using __name__ creates a hierarchical logger
# (e.g., "src.slack.listeners.messages") which can be configured independently
# in logging.yaml for granular log-level control.
logger = get_logger(__name__)


def register_listeners(app: AsyncApp) -> None:
    """
    Register all message event listeners with the app.

    WHY: Slack Bolt requires explicit binding between event types and handler
    functions. This registration function is the single place where that
    binding happens for "message" events, keeping the wiring discoverable.

    Args:
        app: AsyncApp instance -- the Slack Bolt application that will
             receive and dispatch events.

    Design Decision:
        We use a dedicated registration function (rather than decorators at
        import time) because it gives src/app.py explicit control over
        registration order and makes testing easier -- you can call
        `register_listeners(mock_app)` in tests.
    """
    logger.info("Registering message listeners...")

    # Bind the "message" event type to our async handler.
    # Slack Bolt calls `handle_message_event` for every message event that
    # passes through the middleware chain (auth, rate-limit, error-handler).
    app.event("message")(handle_message_event)

    logger.info("[OK] Message listeners registered")


async def handle_message_event(
    event: dict, say: Callable, client: AsyncWebClient, logger: Any
) -> None:
    """
    Handle incoming message events from Slack.

    This is the main entry point for user messages. It:
    1. Validates and sanitizes the message
    2. Checks if the message mentions the bot or is a DM
    3. Invokes the agent system to generate a response
    4. Posts the response back to Slack

    Args:
        event: Message event data from Slack. Key fields:
               - text (str): The raw message text.
               - user (str): Slack user ID of the sender.
               - channel (str): Channel ID where the message was posted.
               - ts (str): Message timestamp (unique ID for the message).
               - thread_ts (str|None): Parent thread timestamp, if threaded.
        say: Function to post message to the same channel. Automatically
             scoped to the correct channel by Slack Bolt.
        client: Slack Web API client for advanced operations like adding
                reactions, fetching user info, etc.
        logger: Logger instance injected by Slack Bolt (overrides module-level
                logger within this function scope).

    Security Considerations:
        - All user-supplied text is sanitized via `sanitize_text()` before
          being forwarded to the AI agent, preventing injection of control
          characters.
        - Channel ID is validated against a strict regex pattern to prevent
          crafted IDs from reaching the Slack API.
        - Bot messages are explicitly filtered to prevent infinite loops
          (a bot responding to its own messages).
    """
    # =========================================================================
    # Extract message details from the event payload
    # =========================================================================
    # WHY: Slack sends a flat dictionary. We extract fields into named
    # variables for readability and to apply default values safely.
    text = event.get("text", "")
    user_id = event.get("user")
    channel_id = event.get("channel")
    message_ts = event.get("ts")
    thread_ts = event.get("thread_ts")  # None if message is not in a thread

    logger.info(
        f"Message received from user {user_id} in channel {channel_id}",
        extra={
            "user_id": user_id,
            "channel_id": channel_id,
            "message_length": len(text),
            "is_thread": bool(thread_ts),
        },
    )

    # =========================================================================
    # Input Validation and Sanitization
    # =========================================================================
    # WHY: User input is NEVER trustworthy. Validating early prevents malformed
    # data from propagating deeper into the system where it could cause
    # unexpected behavior or security vulnerabilities.

    try:
        # Validate that channel_id matches Slack's ID format (e.g., C1234567890).
        # This catches corrupted or forged event payloads.
        validate_channel_id(channel_id)

        # Enforce a maximum message length to prevent abuse (e.g., someone
        # pasting a 100MB text). The 4000 char limit aligns with Slack's
        # own message length cap.
        validate_text_length(text, max_length=4000, field_name="message")

        # Remove control characters and strip whitespace. This does NOT
        # HTML-escape because Slack uses <@U123> syntax for mentions that
        # must be preserved.
        sanitized_text = sanitize_text(text)

    except Exception as e:
        logger.error(f"Input validation failed: {e}")
        # Inform the user that something was wrong with their message.
        # Reply in-thread to keep the channel clean.
        await say(
            text="Sorry, I couldn't process your message. Please try again.",
            thread_ts=thread_ts or message_ts,
        )
        return

    # =========================================================================
    # Check if Bot Should Respond
    # =========================================================================
    # WHY: The bot receives ALL messages in channels it belongs to. Without
    # this gate, it would respond to every single message, which is noisy and
    # expensive (each response requires an AI API call).

    # DEFENSE IN DEPTH: The auth middleware (auth.py) already filters bot
    # messages, but we check again here in case middleware ordering changes
    # or a new middleware is added that inadvertently lets bot messages through.
    bot_id = event.get("bot_id")
    if bot_id:
        # Ignore messages from bots (prevents infinite response loops)
        logger.debug(f"Ignoring bot message: {bot_id}")
        return

    # Check if this is a DM -- Slack DM channel IDs always start with "D"
    is_dm = channel_id.startswith("D")

    # Check if bot is mentioned (simple heuristic: look for <@ in text).
    # NOTE: @mention events are handled by mentions.py via the separate
    # "app_mention" event type. We deliberately skip mentions here to
    # avoid sending duplicate responses.
    is_mention = "<@" in text  # Simple mention check

    # Only respond to DMs -- @mentions are handled by app_mention listener
    should_respond = is_dm

    if not should_respond:
        logger.debug("Message doesn't require bot response")
        return

    # =========================================================================
    # Acknowledge Receipt (Post Processing Indicator)
    # =========================================================================
    # WHY: AI processing can take several seconds. Adding a visible reaction
    # gives the user immediate feedback that their message was received and
    # is being processed, preventing them from re-sending.

    try:
        await client.reactions_add(
            channel=channel_id, name="hourglass_flowing_sand", timestamp=message_ts
        )
    except Exception as e:
        # Non-critical: if the reaction fails, we still process the message.
        # This can happen if the bot lacks the reactions:write scope.
        logger.warning(f"Failed to add reaction: {e}")

    # =========================================================================
    # Invoke Agent System (Phase 6)
    # =========================================================================
    # WHY: The orchestrator encapsulates the entire AI pipeline -- context
    # loading, RAG retrieval, LLM call, and tool execution. Delegating to
    # the orchestrator keeps this listener thin and focused on Slack I/O.

    try:
        # Get the singleton orchestrator instance (lazy initialization)
        orchestrator = get_orchestrator()

        # Process the message through the AI agent pipeline.
        # The orchestrator may use memory, RAG, and MCP tools internally.
        response_text = await orchestrator.process_message(
            user_message=sanitized_text,
            user_id=user_id,
            channel_id=channel_id,
        )

        # Remove the "processing" hourglass reaction now that we have a response
        try:
            await client.reactions_remove(
                channel=channel_id, name="hourglass_flowing_sand", timestamp=message_ts
            )
        except SlackApiError as e:
            # "no_reaction" means someone (or a race condition) already removed it
            if e.response["error"] != "no_reaction":
                logger.warning(f"Failed to remove hourglass reaction: {e}")

        # Add a checkmark reaction to indicate successful processing
        try:
            await client.reactions_add(
                channel=channel_id, name="white_check_mark", timestamp=message_ts
            )
        except SlackApiError as e:
            # "already_reacted" is harmless -- bot already added this reaction
            if e.response["error"] != "already_reacted":
                logger.warning(f"Failed to add checkmark reaction: {e}")

        # Post the AI response in the same thread as the original message.
        # If the original was already in a thread, use its thread_ts;
        # otherwise, start a new thread from the original message's ts.
        await say(text=response_text, thread_ts=thread_ts or message_ts)

        logger.info(f"Response sent to user {user_id}")

    except Exception as e:
        # Catch-all for any failure during AI processing. This ensures the
        # user always gets feedback, even if the orchestrator crashes.
        logger.exception(f"Error processing message: {e}")

        # Clean up: remove the hourglass so it doesn't linger indefinitely
        try:
            await client.reactions_remove(
                channel=channel_id, name="hourglass_flowing_sand", timestamp=message_ts
            )
        except Exception:
            pass  # Best-effort cleanup; don't mask the original error

        # Post a user-friendly error message (no internal details exposed)
        await say(
            text="Sorry, I encountered an error processing your message. Please try again.",
            thread_ts=thread_ts or message_ts,
        )
