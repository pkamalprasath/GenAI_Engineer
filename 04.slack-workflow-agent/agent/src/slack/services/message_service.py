"""
Message Service -- High-Level Slack Message Operations
=======================================================

WHY THIS FILE IS REQUIRED:
    The raw Slack Web API (slack_sdk.web.async_client.AsyncWebClient) exposes
    dozens of low-level methods with inconsistent parameter names, error codes,
    and return shapes.  Calling the API directly from listeners and services
    would scatter Slack-specific knowledge across the entire codebase, making
    it hard to:
      - swap the Slack SDK version without updating every call site,
      - add cross-cutting concerns (logging, metrics, input validation)
        consistently,
      - write unit tests (each test would need to mock the raw SDK).

    This service layer wraps every Slack message operation behind a clean,
    validated, well-logged interface.  Listeners call `MessageService` methods
    instead of touching the SDK directly, and tests can mock a single service
    class instead of dozens of SDK calls.

PROGRAM LOGIC:
    1. CONSTRUCTION: The caller passes an authenticated AsyncWebClient.
       The service stores it and creates a child logger scoped to the class.
    2. MESSAGE POSTING:
       a. post_message()      -- Posts a visible message to a channel or thread.
       b. post_ephemeral_message() -- Posts a message visible only to one user.
    3. MESSAGE RETRIEVAL:
       a. get_messages()       -- Fetches channel history with optional time range.
       b. get_messages_in_timeframe() -- Convenience wrapper that computes
          "oldest" from a relative hours-ago offset.
    4. MESSAGE MUTATION:
       a. update_message()     -- Edits an existing message in place.
       b. delete_message()     -- Permanently removes a message.
    5. SCHEDULED MESSAGES:
       a. schedule_message()   -- Queues a message for future delivery via Slack.
    6. REACTIONS:
       a. add_reaction()       -- Adds an emoji reaction to a message.
       b. remove_reaction()    -- Removes an emoji reaction.
    Every method validates inputs, calls the SDK, logs the outcome, and
    translates SlackApiError into the project's custom exception hierarchy.

WHY THIS APPROACH:
    - SERVICE LAYER PATTERN: Placing all message logic in one class follows
      the "Service Layer" pattern from Domain-Driven Design.  This keeps
      listeners thin (they handle Slack event plumbing) and services thick
      (they contain reusable business logic).
    - DEPENDENCY INJECTION (constructor receives client): The service does not
      create its own AsyncWebClient.  This means tests can inject a mock client,
      and the same service class can be used with different Slack workspaces
      (each with its own token) if multi-tenancy is added later.
    - ASYNC THROUGHOUT: All methods are async because Slack API calls are I/O-
      bound.  Using async/await allows the event loop to handle other requests
      while waiting for Slack's response, which is critical for a bot that may
      serve hundreds of concurrent users.
    - FAIL-SAFE REACTIONS: add_reaction() and remove_reaction() swallow errors
      instead of raising.  This is intentional -- reactions are cosmetic
      feedback, and a failed reaction should never abort a message-processing
      pipeline.

RELATIONSHIP TO OTHER FILES:
    - src/slack/listeners/messages.py (CALLER):
        Uses post_message() and add_reaction() to respond to DMs.
    - src/slack/listeners/mentions.py (CALLER):
        Uses add_reaction() / remove_reaction() for the eyes-to-checkmark flow.
    - src/slack/listeners/commands.py (CALLER):
        Uses get_messages_in_timeframe() for the /bot-summarize command and
        schedule_message() for the /bot-remind command.
    - src/services/summarization.py (PEER):
        Receives pre-fetched message lists from callers who used this service
        to retrieve them.
    - src/utils/validators.py (DEPENDENCY):
        Provides validate_channel_id() and validate_message_ts() used by
        every method here to reject malformed input before hitting the API.
    - src/utils/exceptions.py (DEPENDENCY):
        Provides SlackAPIError, ChannelNotFoundError, MessageNotFoundError --
        the custom exceptions this service raises when the SDK reports errors.
    - src/utils/logger.py (DEPENDENCY):
        Provides get_logger() for structured, per-module logging.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError

from src.utils.logger import get_logger
from src.utils.exceptions import SlackAPIError, ChannelNotFoundError, MessageNotFoundError
from src.utils.validators import validate_channel_id, validate_message_ts

# WHY module-level logger: Used for class-independent log messages (if any).
# The class itself creates a child logger with a more specific name.
logger = get_logger(__name__)


class MessageService:
    """
    Service for Slack message operations.

    Provides methods for:
    - Posting messages
    - Retrieving message history
    - Updating/deleting messages
    - Scheduling messages
    - Thread operations
    """

    def __init__(self, client: AsyncWebClient):
        """
        Initialize the message service.

        Args:
            client: Authenticated Slack WebClient
        """
        # WHY store client as instance attribute: Allows each method to reuse
        # the same authenticated session, and lets tests replace the client
        # with a mock via constructor injection.
        self.client = client
        # WHY child logger with class name: Log lines include
        # "src.slack.services.message_service.MessageService" so you can filter
        # logs from this class vs. other code in the same module.
        self.logger = get_logger(f"{__name__}.MessageService")

    # =========================================================================
    # Message Posting
    # =========================================================================

    async def post_message(
        self,
        channel_id: str,
        text: str,
        blocks: Optional[List[Dict]] = None,
        thread_ts: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Post a message to a Slack channel.

        Args:
            channel_id: Channel to post to
            text: Message text (plain text or markdown)
            blocks: Optional Block Kit blocks for rich formatting
            thread_ts: Optional thread timestamp to post in thread

        Returns:
            Message response with ts, channel, etc.

        Raises:
            SlackAPIError: If posting fails

        Example:
            ```python
            service = MessageService(client)
            response = await service.post_message(
                channel_id="C123ABC456",
                text="Hello world!",
                thread_ts="1234567890.123456"  # Optional: post in thread
            )
            message_ts = response["ts"]
            ```
        """
        # WHY validate before calling the API: Catching malformed channel IDs
        # locally produces a clear ValidationError instead of a cryptic Slack
        # API error that requires reading Slack's docs to decode.
        validate_channel_id(channel_id)

        try:
            self.logger.debug(f"Posting message to channel {channel_id}")

            response = await self.client.chat_postMessage(
                channel=channel_id,
                text=text,
                blocks=blocks,
                thread_ts=thread_ts,
                unfurl_links=False,  # WHY False: Prevents Slack from auto-expanding URLs, which could expose preview content from private links or trigger phishing previews
                unfurl_media=False,  # WHY False: Same security rationale -- auto-expanded media can be distracting and potentially malicious
            )

            self.logger.info(
                f"Message posted successfully to {channel_id}",
                extra={"channel_id": channel_id, "message_ts": response["ts"]},
            )

            return response

        except SlackApiError as e:
            error_code = e.response["error"]
            self.logger.error(f"Failed to post message: {error_code}")

            # WHY special-case "channel_not_found": This is a common, actionable
            # error (bot is not in the channel).  Raising a specific exception
            # lets callers provide a targeted user message.
            if error_code == "channel_not_found":
                raise ChannelNotFoundError(f"Channel not found: {channel_id}")
            else:
                raise SlackAPIError(f"Failed to post message: {error_code}", error_code=error_code)

    async def post_ephemeral_message(
        self, channel_id: str, user_id: str, text: str, blocks: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Post an ephemeral message (visible only to specific user).

        Ephemeral messages are useful for:
        - Error messages
        - Private notifications
        - User-specific help text

        Args:
            channel_id: Channel to post to
            user_id: User who will see the message
            text: Message text
            blocks: Optional Block Kit blocks

        Returns:
            Message response
        """
        validate_channel_id(channel_id)

        try:
            # WHY ephemeral instead of DM: Ephemeral messages appear in the
            # channel context where the user is already looking, so the feedback
            # feels immediate.  DMs would require the user to switch channels.
            response = await self.client.chat_postEphemeral(
                channel=channel_id, user=user_id, text=text, blocks=blocks
            )

            self.logger.debug(f"Ephemeral message posted to user {user_id}")
            return response

        except SlackApiError as e:
            error_code = e.response["error"]
            raise SlackAPIError(
                f"Failed to post ephemeral message: {error_code}", error_code=error_code
            )

    # =========================================================================
    # Message Retrieval
    # =========================================================================

    async def get_messages(
        self,
        channel_id: str,
        limit: int = 100,
        oldest: Optional[str] = None,
        latest: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve messages from a channel.

        Args:
            channel_id: Channel to retrieve from
            limit: Maximum number of messages (default: 100, max: 1000)
            oldest: Only messages after this timestamp
            latest: Only messages before this timestamp

        Returns:
            List of message dictionaries
        """
        validate_channel_id(channel_id)

        try:
            self.logger.debug(f"Retrieving messages from channel {channel_id}")

            response = await self.client.conversations_history(
                channel=channel_id,
                limit=min(limit, 1000),  # WHY cap at 1000: Slack's API hard-limits conversations_history to 1000 messages per call; requesting more would be silently ignored but signals a misunderstanding of the API contract
                oldest=oldest,
                latest=latest,
            )

            messages = response["messages"]

            self.logger.info(
                f"Retrieved {len(messages)} messages from {channel_id}",
                extra={"channel_id": channel_id, "count": len(messages)},
            )

            return messages

        except SlackApiError as e:
            error_code = e.response["error"]
            self.logger.error(f"Failed to retrieve messages: {error_code}")

            if error_code == "channel_not_found":
                raise ChannelNotFoundError(f"Channel not found: {channel_id}")
            else:
                raise SlackAPIError(
                    f"Failed to retrieve messages: {error_code}", error_code=error_code
                )

    async def get_messages_in_timeframe(
        self, channel_id: str, hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Retrieve messages from the past N hours.

        Convenience method that calculates timestamps for you.

        Args:
            channel_id: Channel to retrieve from
            hours: Number of hours to look back

        Returns:
            List of messages from the past N hours

        Example:
            ```python
            # Get messages from past 24 hours
            messages = await service.get_messages_in_timeframe("C123ABC", hours=24)
            ```
        """
        # WHY compute oldest here instead of letting callers do it: Converting
        # "hours ago" to a Unix timestamp string is boilerplate that every caller
        # would have to repeat.  Centralizing it here follows the DRY principle
        # and ensures the timestamp format is always correct.
        oldest_time = datetime.now() - timedelta(hours=hours)
        oldest_ts = str(oldest_time.timestamp())

        self.logger.debug(
            f"Retrieving messages from past {hours} hours",
            extra={"channel_id": channel_id, "hours": hours},
        )

        return await self.get_messages(
            channel_id=channel_id, oldest=oldest_ts, limit=1000  # WHY limit=1000: When fetching an entire timeframe we want ALL messages (up to Slack's max), unlike get_messages() default of 100 which is conservative for general use
        )

    # =========================================================================
    # Message Updates
    # =========================================================================

    async def update_message(
        self, channel_id: str, message_ts: str, text: str, blocks: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Update an existing message.

        Args:
            channel_id: Channel containing the message
            message_ts: Timestamp of message to update
            text: New message text
            blocks: New Block Kit blocks

        Returns:
            Updated message response
        """
        validate_channel_id(channel_id)
        # WHY validate message_ts: Slack uses the message timestamp as a unique
        # ID (e.g., "1234567890.123456").  A malformed ts would produce an
        # unhelpful "message_not_found" error from Slack; validating early gives
        # a clearer error message.
        validate_message_ts(message_ts)

        try:
            response = await self.client.chat_update(
                channel=channel_id, ts=message_ts, text=text, blocks=blocks
            )

            self.logger.info(f"Message updated: {message_ts}")
            return response

        except SlackApiError as e:
            error_code = e.response["error"]
            self.logger.error(f"Failed to update message: {error_code}")

            if error_code == "message_not_found":
                raise MessageNotFoundError(f"Message not found: {message_ts}")
            else:
                raise SlackAPIError(
                    f"Failed to update message: {error_code}", error_code=error_code
                )

    async def delete_message(self, channel_id: str, message_ts: str) -> Dict[str, Any]:
        """
        Delete a message.

        Args:
            channel_id: Channel containing the message
            message_ts: Timestamp of message to delete

        Returns:
            Deletion response
        """
        validate_channel_id(channel_id)
        validate_message_ts(message_ts)

        try:
            response = await self.client.chat_delete(channel=channel_id, ts=message_ts)

            # WHY log at INFO (not DEBUG): Deletion is a destructive, irreversible
            # operation.  INFO-level logging ensures there is always an audit trail
            # of what was deleted and when.
            self.logger.info(f"Message deleted: {message_ts}")
            return response

        except SlackApiError as e:
            error_code = e.response["error"]
            raise SlackAPIError(f"Failed to delete message: {error_code}", error_code=error_code)

    # =========================================================================
    # Scheduled Messages
    # =========================================================================

    async def schedule_message(
        self, channel_id: str, text: str, post_at: int, blocks: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Schedule a message to be posted at a future time.

        Args:
            channel_id: Channel to post to
            text: Message text
            post_at: Unix timestamp when message should be posted
            blocks: Optional Block Kit blocks

        Returns:
            Scheduled message response with scheduled_message_id

        Example:
            ```python
            import time

            # Schedule message for 1 hour from now
            post_at = int(time.time()) + 3600
            response = await service.schedule_message(
                channel_id="C123ABC",
                text="Scheduled message!",
                post_at=post_at
            )
            scheduled_id = response["scheduled_message_id"]
            ```
        """
        validate_channel_id(channel_id)

        try:
            # WHY use Slack's native scheduling instead of asyncio.sleep or APScheduler:
            # Slack-side scheduling survives bot restarts and process crashes.  An
            # in-memory timer would lose all pending reminders if the bot is redeployed.
            response = await self.client.chat_scheduleMessage(
                channel=channel_id, text=text, post_at=post_at, blocks=blocks
            )

            self.logger.info(
                f"Message scheduled for {post_at}",
                extra={"channel_id": channel_id, "post_at": post_at},
            )

            return response

        except SlackApiError as e:
            error_code = e.response["error"]
            raise SlackAPIError(f"Failed to schedule message: {error_code}", error_code=error_code)

    # =========================================================================
    # Reactions
    # =========================================================================

    async def add_reaction(self, channel_id: str, message_ts: str, emoji_name: str) -> None:
        """
        Add an emoji reaction to a message.

        Args:
            channel_id: Channel containing the message
            message_ts: Message timestamp
            emoji_name: Emoji name without colons (e.g., "thumbsup", not ":thumbsup:")
        """
        validate_channel_id(channel_id)
        validate_message_ts(message_ts)

        try:
            await self.client.reactions_add(
                channel=channel_id, timestamp=message_ts, name=emoji_name
            )

            self.logger.debug(f"Added reaction :{emoji_name}: to message {message_ts}")

        except SlackApiError as e:
            # WHY swallow the error (log + return) instead of raising: Reactions
            # are non-critical UI feedback.  If adding a "thumbsup" fails, the
            # user's request was still processed successfully.  Raising here
            # would abort the entire listener for a cosmetic failure.
            self.logger.warning(f"Failed to add reaction: {e.response['error']}")

    async def remove_reaction(self, channel_id: str, message_ts: str, emoji_name: str) -> None:
        """Remove an emoji reaction from a message."""
        validate_channel_id(channel_id)
        validate_message_ts(message_ts)

        try:
            await self.client.reactions_remove(
                channel=channel_id, timestamp=message_ts, name=emoji_name
            )

            self.logger.debug(f"Removed reaction :{emoji_name}: from message {message_ts}")

        except SlackApiError as e:
            # WHY swallow error here too: Same rationale as add_reaction --
            # removing a reaction is cosmetic cleanup, and the common "no_reaction"
            # error (reaction was already removed by someone else) is harmless.
            self.logger.warning(f"Failed to remove reaction: {e.response['error']}")
