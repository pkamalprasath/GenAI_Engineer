"""
Context Builder
================

WHY THIS FILE IS REQUIRED:
    The AI agent needs context to give good answers.  Without context,
    Claude would treat every message as an isolated question — it wouldn't
    remember past conversations, know the user's preferences, or understand
    what's been discussed in the channel before.

    This module assembles context from THREE sources:
      1. SHORT-TERM MEMORY: Recent conversation history (last ~10 messages)
         between this user and the bot in this channel.
      2. LONG-TERM MEMORY: Curated notes from MEMORY.md, user preferences,
         and daily conversation logs.
      3. RAG RETRIEVAL: Semantically similar past messages from the channel,
         found via vector search over the ChromaDB knowledge base.

    The assembled context dict is passed to the orchestrator, which injects
    it into Claude's system prompt so the agent can reference it naturally.

PROGRAM LOGIC:
    1. build_context() is called with user_id, channel_id, and user_message.
    2. It calls MemoryManager.get_conversation_history() for short-term memory.
    3. It calls MemoryManager.recall_memory() for long-term memory.
    4. If RAG is enabled, it calls SemanticRetriever.retrieve() to find
       relevant past messages and format them for the prompt.
    5. Returns a dict with all three context components.

WHY THIS APPROACH:
    - SEPARATION OF CONCERNS: The orchestrator shouldn't know how to query
      memory or run vector searches.  The ContextBuilder encapsulates that.
    - THREE-LAYER CONTEXT gives the agent both recency (short-term) and
      relevance (RAG) awareness, plus persistent knowledge (long-term).
    - GRACEFUL RAG FAILURE: If the vector store isn't set up or the search
      fails, we return empty string rather than crashing.  The agent works
      fine without RAG — it just has less context.
    - MEMORY LENGTH CAP: Long-term memory is truncated to 1000 chars to
      avoid bloating the system prompt (which affects API costs and latency).

RELATIONSHIP TO OTHER FILES:
    - Used by: src/agent/orchestrator.py (AgentOrchestrator.process_message)
    - Uses: src/memory/manager.py (MemoryManager)
    - Uses: src/rag/retriever.py (SemanticRetriever)
"""

from typing import Dict, Any

from src.memory.manager import MemoryManager
from src.rag.retriever import SemanticRetriever
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ContextBuilder:
    """
    Builds comprehensive context for the agent from multiple sources.

    Architecture:
        ContextBuilder → MemoryManager (short-term + long-term memory)
                       → SemanticRetriever (RAG vector search)

    The returned dict has three keys:
        - conversation_history: List of recent {role, content} messages
        - memory_context: String of relevant long-term memories
        - rag_context: String of semantically similar past messages
    """

    def __init__(self, memory_manager: MemoryManager = None):
        # Accept an existing MemoryManager so that the orchestrator and
        # context builder share the SAME short-term memory.  Without this,
        # each would create its own ShortTermMemory dict and conversation
        # history stored by the orchestrator would never be visible here.
        self.memory_manager = memory_manager or MemoryManager()

        # SemanticRetriever performs vector similarity search over the
        # ChromaDB knowledge base of indexed channel messages.
        self.rag_retriever = SemanticRetriever()
        logger.info("Context builder initialized")

    async def build_context(
        self, user_id: str, channel_id: str, user_message: str, use_rag: bool = True
    ) -> Dict[str, Any]:
        """
        Build comprehensive context for the agent.

        HOW IT WORKS:
            1. Fetch the last 10 messages from short-term memory (in-memory
               conversation buffer for this user+channel pair).
            2. Recall relevant long-term memories by semantic matching
               against the user's current message.
            3. If RAG is enabled, search the ChromaDB vector store for
               past channel messages that are semantically similar to
               the current query.

        WHY THREE SOURCES:
            - Short-term memory gives continuity within the current session
              ("you just asked about X, now you're asking about Y").
            - Long-term memory gives persistence across sessions
              ("last week you mentioned you prefer Python").
            - RAG gives channel awareness ("this topic was discussed
              3 days ago in #engineering").

        Args:
            user_id:      Slack user ID.
            channel_id:   Slack channel ID.
            user_message: The current message text (used for semantic search).
            use_rag:      Whether to include RAG retrieval (can be disabled
                          for performance or when the vector store isn't ready).

        Returns:
            Dict with keys: conversation_history, memory_context, rag_context.
        """
        logger.debug(f"Building context for {user_id} in {channel_id}")

        # ── Source 1: Short-term memory (recent conversation history) ──
        # Returns a list of {role: "user"|"assistant", content: "..."} dicts.
        # Limited to 10 messages to keep context manageable.
        conversation_history = self.memory_manager.get_conversation_history(
            user_id, channel_id, limit=10
        )

        # ── Source 2: Long-term memory (MEMORY.md, user notes) ──
        # Semantic recall: finds memory entries that are relevant to the
        # current user message.  Returns a formatted string.
        memory_context = self.memory_manager.recall_memory(
            user_message, user_id=user_id, channel_id=channel_id
        )

        # ── Source 3: RAG retrieval (vector search over past messages) ──
        # This is the most expensive step (embedding + vector search), so
        # it can be disabled via use_rag=False for performance.
        rag_context = ""
        if use_rag:
            try:
                # retrieve() returns a list of context objects (text + metadata).
                # top_k=5 means we fetch the 5 most relevant past messages.
                contexts = await self.rag_retriever.retrieve(
                    query=user_message, channel_id=channel_id, top_k=5
                )
                # format_context_for_prompt() turns the raw results into a
                # string suitable for injection into the system prompt.
                rag_context = self.rag_retriever.format_context_for_prompt(contexts)
            except Exception as e:
                # Graceful failure: RAG is an enhancement, not a requirement.
                # If the vector store isn't set up or the search fails, the
                # agent still works — it just has less context.
                logger.warning(f"RAG retrieval failed: {e}")
                rag_context = ""

        logger.info("Context built successfully")

        return {
            "conversation_history": conversation_history,
            "memory_context": memory_context[:1000],  # Cap at 1000 chars to limit prompt size
            "rag_context": rag_context,
        }
