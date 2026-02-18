"""
Memory Data Models (Pydantic Schemas)
======================================

WHY THIS FILE IS REQUIRED:
    Every layer of the memory system needs to agree on what a "conversation
    context" looks like -- which fields exist, what types they have, and what
    the defaults are.  Without a shared schema, each module would invent its
    own ad-hoc dict structure, leading to key mismatches, missing fields, and
    hard-to-debug runtime errors.

    By defining data models with **Pydantic**, we get:
        1. **Compile-time documentation**: The class definition IS the spec.
        2. **Runtime validation**: Assigning a wrong type raises immediately.
        3. **Serialisation for free**: `.model_dump()` / `.model_dump_json()`
           produce clean dicts/JSON for logging, caching, or API responses.

PROGRAM LOGIC:
    Currently there is one model:
        - `ConversationContext`: Represents a single ongoing conversation
          between one user in one channel.  It holds the ordered list of
          messages plus metadata (who, where, when).

    As the memory system grows, additional models will be added here:
        - `MemoryEntry`: A single curated fact stored in MEMORY.md.
        - `EmbeddingRecord`: A vector-embedding row for semantic search.
        - `DistillationResult`: Output of the weekly summarisation job.

WHY THIS APPROACH (Pydantic BaseModel):
    - **Validation on construction**: If someone passes `user_id=123` instead
      of `user_id="U123"`, Pydantic raises a `ValidationError` at the point
      of creation -- not three function calls later when `.startswith("U")`
      blows up.
    - **Immutable-friendly**: Pydantic models can be frozen (`.model_config
      = ConfigDict(frozen=True)`) if immutability is desired later.
    - **IDE support**: Type hints give autocomplete and static analysis in
      VS Code, PyCharm, and mypy.

    Alternative considered: plain `dataclasses`.  Rejected because Pydantic
    gives validation, JSON schema generation, and `.env` integration (in
    `BaseSettings`) that dataclasses lack.

RELATIONSHIP TO OTHER FILES:
    - `src/memory/short_term.py` imports `ConversationContext` and stores
      instances in its `contexts` dictionary.
    - `src/memory/manager.py` accesses `context.messages` when building
      conversation history for the LLM.
    - `src/memory/retriever.py` iterates over `context.messages` during
      keyword search.
    - This file has NO outward dependencies on other project modules, making
      it a leaf node in the import graph -- intentionally, to avoid circular
      imports.

SECURITY CONSIDERATIONS:
    - `messages` is typed as `List[Dict[str, Any]]` -- a flexible schema that
      accepts any dict.  This means there is no validation on individual
      message contents.  A future improvement could define a `Message` model
      with strict field validation (e.g. `role` must be "user" | "assistant").
    - `datetime.now()` uses the LOCAL timezone.  In a distributed system, use
      `datetime.now(timezone.utc)` to avoid ambiguity.
    - Pydantic models serialize cleanly but may include sensitive data (user
      messages).  Avoid logging full model dumps in production.
"""

from typing import Dict, List, Any
from datetime import datetime
from pydantic import BaseModel, Field


class ConversationContext(BaseModel):
    """
    Represents the current conversation state for one user in one channel.

    This is the fundamental unit of short-term memory.  Each instance holds
    an ordered list of messages exchanged between the user and the bot,
    along with timing metadata.

    Design decisions:
        - `messages` is a list of dicts (not a list of typed `Message` models)
          for simplicity in v1.  The dict shape is:
              {"role": str, "content": str, "timestamp": str}
          This mirrors the format expected by most LLM chat APIs.
        - `started_at` and `last_updated` are set to `datetime.now()` at
          creation time.  `last_updated` is mutated by `ShortTermMemory`
          each time a new message is added, enabling stale-context detection.
    """

    # WHY `user_id` and `channel_id` as required strings:
    #   These two fields together form the composite key for looking up a
    #   context in ShortTermMemory.  Making them required (no default) ensures
    #   every context is always associated with a specific user and channel.
    user_id: str
    channel_id: str

    # WHY `List[Dict[str, Any]]` instead of a typed `List[Message]`:
    #   Keeps the schema flexible during rapid prototyping.  The trade-off is
    #   less validation on individual messages.  When the schema stabilises,
    #   consider replacing this with a stricter `Message` model.
    # WHY `default_factory=list`:
    #   Pydantic (and Python in general) require mutable defaults to use a
    #   factory function.  Using `default=[]` would share the SAME list object
    #   across all instances -- a classic Python mutable-default-argument bug.
    messages: List[Dict[str, Any]] = Field(default_factory=list)

    # WHY `default_factory=datetime.now` (not `default=datetime.now()`):
    #   `datetime.now()` (with parentheses) would be evaluated ONCE at class
    #   definition time, making every instance share the same timestamp.
    #   `default_factory=datetime.now` (no parentheses) calls the function
    #   fresh for each new instance, giving each context an accurate creation
    #   time.  This is the same mutable-default pattern as `messages` above.
    started_at: datetime = Field(default_factory=datetime.now)

    # WHY a separate `last_updated`:
    #   `started_at` records when the conversation began and never changes.
    #   `last_updated` is bumped on every new message so external code can
    #   identify stale contexts (e.g. "no activity for 30 minutes -> evict").
    last_updated: datetime = Field(default_factory=datetime.now)
