"""
Short-Term Memory (In-Memory Conversation Buffer)
===================================================

WHY THIS FILE IS REQUIRED:
    Large Language Models are *stateless* -- each API call is independent and
    has no memory of previous calls.  To create the illusion of a continuous
    conversation, the application must store recent messages and re-send them
    with every new request.  This module provides that "sliding window" of
    conversation history, held entirely in RAM for speed.

PROGRAM LOGIC:
    1. Conversations are keyed by `"{user_id}:{channel_id}"`.  This means
       the same user talking in two different Slack channels gets two separate
       context windows -- their DM conversation doesn't bleed into a public
       channel thread.
    2. `get_context` lazily creates a `ConversationContext` on first access,
       so no upfront registration is needed.
    3. `add_message` appends a new message dict and enforces a hard cap
       (`MAX_MESSAGES_PER_CONTEXT`).  When the cap is exceeded, the oldest
       messages are evicted -- a classic **ring-buffer / sliding-window**
       strategy that bounds memory usage.
    4. `clear_context` deletes the entire context for a user-channel pair,
       useful for explicit "/reset" slash commands.

WHY THIS APPROACH (in-memory dict keyed by user:channel):
    - **O(1) lookup**: Python dicts are hash maps; retrieving a conversation
      by its composite key is constant time.
    - **Zero infrastructure**: No database, no Redis, no network round-trips.
      Perfect for single-process development.  In a scaled-out deployment,
      this class could be swapped for a Redis-backed implementation without
      changing the public interface.
    - **Bounded growth**: `MAX_MESSAGES_PER_CONTEXT` prevents a single chatty
      user from consuming unbounded RAM.

RELATIONSHIP TO OTHER FILES:
    - `src/memory/schemas.py` defines `ConversationContext`, the Pydantic
      model that holds messages, timestamps, and metadata for one context.
    - `src/memory/manager.py` creates and owns the single `ShortTermMemory`
      instance and calls `add_message` / `get_context` on it.
    - `src/memory/retriever.py` reads from this store when performing
      keyword searches over recent conversation history.

SECURITY CONSIDERATIONS:
    - Data lives only in the process's heap.  If the process dies, all
      short-term memory is lost (by design -- it is "short-term").
    - No encryption is applied because the data never leaves the process
      boundary.  If you ever serialise this to disk or send it over a
      network, apply encryption at that boundary.
    - The `MAX_MESSAGES_PER_CONTEXT` cap is also a mild defence against
      denial-of-service: a flood of messages cannot grow a context beyond
      100 entries.
"""

from typing import Dict
from datetime import datetime

from src.memory.schemas import ConversationContext
from src.utils.logger import get_logger

logger = get_logger(__name__)


# WHY 100: A typical Claude context window is 100k-200k tokens.  100 messages
# of ~200 tokens each = ~20k tokens -- leaves plenty of room for the system
# prompt, tools, and the model's own output.  Raising this number increases
# recall at the cost of token usage (and therefore latency and money).
MAX_MESSAGES_PER_CONTEXT = 100


class ShortTermMemory:
    """
    In-memory conversation context storage.

    Maintains a dictionary of `ConversationContext` objects keyed by
    `"{user_id}:{channel_id}"`.  Each context is an ordered list of messages
    with a fixed upper bound.

    Design note: This class is intentionally NOT thread-safe.  Python's GIL
    protects simple dict operations in CPython, but if you move to a
    multi-threaded async server, consider wrapping mutations in a lock.
    """

    def __init__(self):
        """
        Initialise an empty context store.

        WHY `Dict[str, ConversationContext]`:
            The string key is the composite `user_id:channel_id`.  The value
            is a Pydantic model that provides automatic validation and clean
            serialisation if we ever need to snapshot the state.
        """
        self.contexts: Dict[str, ConversationContext] = {}
        logger.info("Short-term memory initialized")

    def get_context(self, user_id: str, channel_id: str) -> ConversationContext:
        """
        Get or create conversation context for a user-channel pair.

        WHY lazy creation:
            We cannot predict which user-channel combinations will be active.
            Creating contexts on first access avoids pre-allocating memory for
            channels that may never receive a message, and simplifies the API
            (no explicit "register" step).

        Args:
            user_id:    Slack user ID.
            channel_id: Slack channel or DM ID.

        Returns:
            The existing or newly created ConversationContext.
        """
        # Composite key ensures isolation between different conversations
        # even for the same user.
        key = f"{user_id}:{channel_id}"

        if key not in self.contexts:
            self.contexts[key] = ConversationContext(user_id=user_id, channel_id=channel_id)
            logger.debug(f"Created new context for {key}")

        return self.contexts[key]

    def add_message(self, user_id: str, channel_id: str, role: str, content: str) -> None:
        """
        Add a message to the conversation context and enforce the size cap.

        WHY we store role + content + timestamp:
            The LLM API expects messages in `{"role": ..., "content": ...}`
            format.  Adding a timestamp lets the retriever rank results by
            recency and helps with debugging.

        WHY eviction by slicing (not deque):
            `collections.deque(maxlen=N)` would also work, but Pydantic's
            `ConversationContext.messages` is typed as `List[Dict]`.  Slicing
            the list keeps the schema simple and avoids a custom Pydantic
            validator for deque serialisation.

        Args:
            user_id:    Slack user ID.
            channel_id: Slack channel or DM ID.
            role:       "user" or "assistant".
            content:    The message text.
        """
        context = self.get_context(user_id, channel_id)

        # Append the new message with an ISO-8601 timestamp for consistency
        # across time zones and serialisation formats.
        context.messages.append(
            {"role": role, "content": content, "timestamp": datetime.now().isoformat()}
        )
        # --- Sliding-window eviction ---
        # If the list exceeds the cap, keep only the most recent messages.
        # WHY slice from the end (`-MAX_MESSAGES_PER_CONTEXT:`):
        #   Preserves the NEWEST messages and discards the OLDEST, which
        #   matches the intuition that recent context is more relevant.
        if len(context.messages) > MAX_MESSAGES_PER_CONTEXT:
            context.messages = context.messages[-MAX_MESSAGES_PER_CONTEXT:]
        # Update the "last_updated" timestamp so external code (e.g. a
        # garbage collector) can identify stale contexts.
        context.last_updated = datetime.now()

        logger.debug(f"Added message to context: {user_id}:{channel_id}")

    def clear_context(self, user_id: str, channel_id: str) -> None:
        """
        Clear (delete) the conversation context for a user-channel pair.

        WHY full deletion rather than emptying the message list:
            Deleting the key frees the `ConversationContext` object entirely,
            allowing Python's garbage collector to reclaim the memory.  If we
            merely cleared `context.messages`, the empty object would linger
            in the dict forever.

        Use case: A user types "/reset" to start a fresh conversation.

        Args:
            user_id:    Slack user ID.
            channel_id: Slack channel or DM ID.
        """
        key = f"{user_id}:{channel_id}"
        if key in self.contexts:
            del self.contexts[key]
            logger.debug(f"Cleared context: {key}")
