"""
AI-Powered Channel Summarization Service
==========================================

WHY THIS FILE IS REQUIRED:
    Slack channels accumulate hundreds of messages per day.  Catching up on a
    busy channel after a meeting, a holiday, or a weekend is time-consuming and
    error-prone -- important decisions, action items, and blockers get buried
    in noise.  This service solves that problem by distilling an arbitrary list
    of Slack messages into a concise, structured summary using an LLM (Claude).

    Without this service:
      - Users would have to scroll through hundreds of messages manually.
      - The /bot-summarize slash command (src/slack/listeners/commands.py)
        would have no backend to call.
      - There would be no reusable summarization logic for other features
        (e.g., weekly email digests, memory distillation) to build on.

PROGRAM LOGIC:
    1. INITIALIZATION (__init__):
       An AsyncAnthropic client is created with the API key from settings.
       The client is stored as an instance attribute for reuse across calls.

    2. SUMMARIZE_MESSAGES (public entry point):
       a. Receives a raw list of Slack message dicts and a channel name.
       b. Calls _format_messages() to convert the raw dicts into a clean,
          human-readable transcript (one line per message).
       c. Constructs a structured prompt that asks Claude to produce a
          summary covering: main topics, key decisions / action items, and
          important questions or issues raised.
       d. Sends the prompt to the Claude API (claude-sonnet-4-5-20250929 model)
          with a max_tokens cap of 1024.
       e. Extracts the text from the first content block of the response.
       f. Returns the summary string to the caller.
       g. If any exception occurs during the API call, logs the error and
          returns a static fallback string so the caller always gets a
          non-None result.

    3. _FORMAT_MESSAGES (private helper):
       a. Iterates over the message list, extracting user ID and text.
       b. Skips messages with empty text (e.g., file uploads, bot joins).
       c. Formats each message as "**User <id>**: <text>" for readability
          in the prompt.
       d. Joins up to 50 messages with double newlines.
       e. Returns the formatted string for embedding in the prompt.

WHY THIS APPROACH:
    - DEDICATED SERVICE CLASS: Encapsulating summarization in its own class
      (rather than inlining the logic in the slash command handler) enables
      reuse.  The same SummarizationService can be called from commands,
      scheduled jobs, or the memory distillation pipeline without duplicating
      the prompt engineering or API call logic.
    - ANTHROPIC AsyncAnthropic CLIENT: The async client is used because all
      callers in this project are async (Slack Bolt handlers).  A synchronous
      client would block the event loop and freeze the bot for 5-10 seconds
      per summarization request.
    - claude-sonnet-4-5-20250929 MODEL: Sonnet is chosen as the best balance of
      quality, speed, and cost for summarization tasks.  Opus would produce
      marginally better summaries but at 5x the cost and 3x the latency.
      Haiku would be cheaper but its summaries miss nuance in long threads.
    - MAX_TOKENS 1024: Summaries should be concise (a few paragraphs).
      Capping at 1024 tokens prevents the model from producing a summary
      that is as long as the original conversation, which would defeat the
      purpose.
    - 50-MESSAGE LIMIT IN _format_messages: Claude's context window can hold
      far more, but including hundreds of messages would increase cost
      (input tokens are billed) and slow the response.  50 messages is a
      pragmatic cap that covers ~2-4 hours of active conversation.  If the
      caller fetched more messages, only the most recent 50 are used.
    - GRACEFUL FALLBACK ON ERROR: Returning "Failed to generate summary."
      instead of raising ensures the /bot-summarize command always posts
      something to the user rather than leaving them wondering if the bot
      is broken.

RELATIONSHIP TO OTHER FILES:
    - src/slack/listeners/commands.py (CALLER):
        The handle_summarize_command() function creates a SummarizationService
        instance and calls summarize_messages() with messages fetched from the
        Slack API.
    - config/settings.py (DEPENDENCY):
        Provides `settings.anthropic_api_key` for authenticating with the
        Anthropic API.
    - src/utils/logger.py (DEPENDENCY):
        Provides the structured logger for info/error logging.
    - src/slack/services/message_service.py (PEER):
        Provides the get_messages() / get_messages_in_timeframe() methods that
        callers use to fetch the message list before passing it here.
    - src/memory/manager.py (POTENTIAL FUTURE CALLER):
        The memory distillation pipeline could use this service to compress
        old conversation logs into summaries for long-term storage.
"""

from typing import List, Dict, Any
from anthropic import AsyncAnthropic

from config.settings import settings
from src.utils.logger import get_logger

# WHY module-level logger (not class-level): Keeps the logger creation out of
# __init__, so it is available even if the class fails to instantiate (e.g.,
# due to a missing API key).  This ensures the error can still be logged.
logger = get_logger(__name__)


class SummarizationService:
    """Service for summarizing channel conversations using Claude."""

    def __init__(self):
        # WHY create the client in __init__ (not at module level): Module-level
        # clients are created at import time, which means a missing API key
        # would crash the entire import chain.  Creating in __init__ lets the
        # module be imported safely and defers the failure to actual usage.
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        logger.info("Summarization service initialized")

    async def summarize_messages(
        self, messages: List[Dict[str, Any]], channel_name: str = "channel"
    ) -> str:
        """
        Summarize a list of messages.

        Args:
            messages: List of message dictionaries
            channel_name: Channel name for context

        Returns:
            Summary text
        """
        logger.info(f"Summarizing {len(messages)} messages from {channel_name}")

        # WHY format before building the prompt: Separating formatting from
        # prompt construction keeps each concern testable independently.
        # _format_messages can be unit-tested without mocking the LLM.
        formatted_messages = self._format_messages(messages)

        # WHY include channel name in the prompt: Providing the channel name
        # gives the LLM context about the domain (e.g., #engineering vs.
        # #marketing), which helps it produce more relevant summaries.
        prompt = f"""Summarize these messages from #{channel_name}:

{formatted_messages}

Provide a concise summary covering:
1. Main topics discussed
2. Key decisions or action items
3. Important questions or issues raised"""

        try:
            # WHY messages=[{"role": "user", ...}] with no system prompt:
            # For a straightforward summarization task, the instructions are
            # self-contained in the user message.  A system prompt would add
            # cost (extra input tokens) without improving quality here.
            response = await self.client.messages.create(
                model="claude-sonnet-4-5-20250929",  # WHY Sonnet: Best quality/cost/speed balance for summarization (see module docstring)
                max_tokens=1024,  # WHY 1024: Keeps summaries concise; longer caps risk verbose output that defeats the purpose
                messages=[{"role": "user", "content": prompt}],
            )

            # WHY response.content[0].text: The Anthropic API returns a list of
            # content blocks (text, tool_use, etc.).  For a pure text completion,
            # the first block is always a TextBlock whose .text attribute holds
            # the model's response string.
            summary = response.content[0].text
            logger.info("Summary generated successfully")
            return summary

        except Exception as e:
            # WHY broad except (not specific Anthropic exceptions): The Anthropic
            # SDK can raise several exception types (AuthenticationError,
            # RateLimitError, APIConnectionError, etc.) and new ones may be added
            # in future SDK versions.  Catching Exception ensures no failure mode
            # propagates as an unhandled crash to the user.
            logger.error(f"Summarization failed: {e}")
            # WHY return a static string instead of raising: The /bot-summarize
            # command posts whatever string we return.  Raising would require the
            # caller to handle the exception and compose its own fallback message,
            # which is error-prone if multiple callers exist.
            return "Failed to generate summary."

    def _format_messages(self, messages: List[Dict[str, Any]]) -> str:
        """Format messages for prompt."""
        formatted = []
        for msg in messages:
            user = msg.get("user", "Unknown")
            text = msg.get("text", "")
            # WHY skip empty text: Some Slack "messages" are system events (user
            # joined, file uploaded, channel topic changed) with no text content.
            # Including them would add noise to the prompt without information.
            if text:
                # WHY "**User <id>**" format: The bold markdown prefix clearly
                # delineates speaker changes for the LLM, improving summary
                # quality.  We use the raw user ID (not display name) because
                # resolving display names would require additional API calls.
                formatted.append(f"**User {user}**: {text}")

        # WHY limit to 50 messages: Controls input token cost and keeps the
        # prompt within a predictable size.  The slice takes the FIRST 50
        # messages (oldest), which are the ones returned by Slack's API in
        # reverse-chronological order after the caller reverses or filters them.
        # If the caller passes more, the excess is silently dropped.
        return "\n\n".join(formatted[:50])
