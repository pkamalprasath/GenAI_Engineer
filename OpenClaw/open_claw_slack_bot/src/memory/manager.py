"""
Memory Manager -- Central Orchestrator for the Multi-Layered Memory System
===========================================================================

WHY THIS FILE IS REQUIRED:
    The memory subsystem is split into three specialised components:
        - ShortTermMemory  (fast, in-memory, per-conversation)
        - LongTermMemory   (persistent, file-backed, append-only logs)
        - MemoryRetriever  (search across both layers)

    Without an orchestrator, every call-site (Slack event handlers, tool
    callbacks, etc.) would need to know about all three objects and coordinate
    them manually.  That leads to duplicated logic, inconsistent storage, and
    tight coupling between the transport layer and the memory layer.

    `MemoryManager` is the single entry-point: callers say *"store this
    interaction"* or *"recall relevant memories"* and the manager routes the
    request to the right sub-components.  This is the **Facade** design
    pattern.

PROGRAM LOGIC:
    1. `__init__` creates one instance each of ShortTermMemory, LongTermMemory,
       and MemoryRetriever and wires them together.
    2. `store_interaction` writes a user+assistant message pair into BOTH
       short-term (for immediate conversation context) AND long-term (for
       future recall across sessions).
    3. `get_conversation_history` returns the most recent N messages from
       short-term memory for a specific user-channel pair.
    4. `recall_memory` delegates to the MemoryRetriever, which searches
       across all layers, and then formats the top results into a single
       context string suitable for injection into the LLM prompt.

WHY THIS APPROACH (Facade pattern):
    - **Loose coupling**: Slack handlers depend only on MemoryManager, not on
      the internal memory classes.  If we swap ShortTermMemory for Redis
      tomorrow, the handlers do not change.
    - **Single responsibility**: Each memory class does one thing; the manager
      composes them.
    - **Testability**: In unit tests you can inject mock sub-components into
      the manager without touching the real file system or network.

RELATIONSHIP TO OTHER FILES:
    - Imports `ShortTermMemory` from `src/memory/short_term.py`
    - Imports `LongTermMemory`  from `src/memory/long_term.py`
    - Imports `MemoryRetriever` from `src/memory/retriever.py`
    - All three of those rely on `src/memory/schemas.py` for data models.
    - Consumed by Slack event handlers (e.g. `src/slack/events.py`) and
      potentially by tool/agent code that needs to read back conversation
      history.

SECURITY CONSIDERATIONS:
    - User messages and bot responses are written verbatim to daily log files.
      If messages contain PII or secrets, those will persist on disk.  A
      production deployment should add a sanitisation step before calling
      `store_interaction`.
    - The `recall_memory` method caps results at 5 entries and truncates
      content length inside the retriever, limiting prompt-injection surface
      area when retrieved text is fed back to the LLM.
"""

from typing import List, Dict, Any, Optional

from src.memory.short_term import ShortTermMemory
from src.memory.long_term import LongTermMemory
from src.memory.retriever import MemoryRetriever
from src.utils.logger import get_logger

# WHY module-level logger: Each module gets its own named logger so log output
# can be filtered per-module (e.g. "src.memory.manager DEBUG" only).
logger = get_logger(__name__)


class MemoryManager:
    """
    Central memory management system.

    Acts as the **Facade** over ShortTermMemory, LongTermMemory, and
    MemoryRetriever.  All external code should interact with memory
    exclusively through this class.
    """

    def __init__(self):
        """
        Initialise all memory sub-components and wire them together.

        WHY we create the retriever AFTER short_term and long_term:
            The retriever needs references to both stores so it can search
            across them.  Creating them first, then passing them in, avoids
            circular dependencies and makes the data-flow explicit.
        """
        self.short_term = ShortTermMemory()
        self.long_term = LongTermMemory()
        # WHY dependency injection: The retriever receives concrete instances
        # rather than creating its own.  This means all three objects share
        # the same underlying data, and in tests we can pass in mocks.
        self.retriever = MemoryRetriever(
            short_term=self.short_term, long_term=self.long_term
        )
        logger.info("Memory manager initialized")

    def store_interaction(
        self, user_id: str, channel_id: str, user_message: str, bot_response: str
    ) -> None:
        """
        Store a complete interaction (short-term + long-term).

        WHY dual writes:
            - Short-term keeps the conversation "warm" in RAM so the next LLM
              call has immediate context (fast, ephemeral).
            - Long-term appends to a daily Markdown file so the data survives
              process restarts and can be searched later (slow, durable).
            Writing to both ensures the best of both worlds: low-latency
            context AND persistence.

        Args:
            user_id:      Slack user ID (e.g. "U01ABC23DEF").
            channel_id:   Slack channel or DM ID.
            user_message:  The raw text the human sent.
            bot_response:  The text the bot replied with.
        """
        # --- Short-term: add both sides of the conversation as separate
        # messages so the LLM sees the standard role-based chat format.
        self.short_term.add_message(user_id, channel_id, "user", user_message)
        self.short_term.add_message(user_id, channel_id, "assistant", bot_response)

        # --- Long-term: collapse both sides into one Markdown log entry.
        # WHY Markdown format: Human-readable when opened in any text editor
        # or rendered in GitHub/Notion, and easily parseable by the retriever.
        log_entry = f"""
**User** ({user_id}): {user_message}
**Bot**: {bot_response}
"""
        self.long_term.write_daily_log(log_entry)

        logger.debug(f"Stored interaction: {user_id} in {channel_id}")

    def get_conversation_history(
        self, user_id: str, channel_id: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get recent conversation history.

        WHY a `limit` parameter:
            LLM context windows are finite.  Sending hundreds of messages
            wastes tokens and can exceed the model's maximum input length.
            Defaulting to the last 10 messages provides enough context for
            most follow-up questions without blowing the budget.

        Returns:
            A list of message dicts, each with keys: role, content, timestamp.
        """
        context = self.short_term.get_context(user_id, channel_id)
        # Slice from the END of the list so we always return the most recent
        # messages, not the oldest.
        return context.messages[-limit:]

    def recall_memory(
        self, query: str, user_id: Optional[str] = None, channel_id: Optional[str] = None
    ) -> str:
        """
        Recall relevant memories using the memory retriever.

        WHY this exists separately from `get_conversation_history`:
            `get_conversation_history` returns the last N messages verbatim.
            `recall_memory` performs a *search* across ALL memory layers
            (including long-term logs from previous days/sessions) and returns
            only the entries that match the query.  This powers the "the bot
            remembers things from last week" experience.

        Args:
            query:      Natural-language search string.
            user_id:    If provided, also searches short-term memory for this user.
            channel_id: If provided, scopes the short-term search to this channel.

        Returns:
            A formatted string of matching memories ready to be injected into
            the LLM system prompt, or an empty string if nothing matched.
        """
        results = self.retriever.search(query, user_id=user_id, channel_id=channel_id)

        # WHY return early on empty: Avoids injecting a useless "\n\n"-joined
        # empty string into the prompt.
        if not results:
            return ""

        # --- Format results into a context string --------------------------
        # WHY cap at 5 results: More results = more tokens = more cost and
        # more noise.  The top 5 most relevant hits are usually sufficient.
        # Each result is prefixed with its source (short_term / long_term /
        # daily_log) so the LLM can weigh recency and reliability.
        parts = []
        for result in results[:5]:  # Limit to top 5
            source = result.get("source", "unknown")
            content = result.get("content", "")
            if content:
                parts.append(f"[{source}] {content}")

        return "\n\n".join(parts)
