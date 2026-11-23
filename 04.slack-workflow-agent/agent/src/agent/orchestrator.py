"""
Agent Orchestrator
===================

WHY THIS FILE IS REQUIRED:
    This is the BRAIN of the Slack bot.  When a user sends a message, the
    orchestrator decides what to do: should it call a tool (post a message,
    create an issue, schedule a reminder)?  Should it look up context from
    memory?  Should it just respond with text?

    It implements the ReAct (Reason + Act) pattern with Claude:
      1. REASON: Claude reads the user's message, memory context, and
         conversation history, then decides if it needs a tool.
      2. ACT:    If Claude requests a tool, the orchestrator executes it
         and feeds the result back.
      3. LOOP:   This repeats until Claude has enough information to give
         a final text response (or we hit the iteration limit).

PROGRAM LOGIC (high-level flow):
    1. process_message() is called by Slack event listeners with the user's
       message, user_id, and channel_id.
    2. ContextBuilder assembles context from three sources:
       - Short-term memory (recent conversation history)
       - Long-term memory (MEMORY.md, user preferences)
       - RAG retrieval (semantic search over past channel messages)
    3. The system prompt is enriched with this context.
    4. _react_loop() iterates up to MAX_TOOL_ITERATIONS times:
       a. Call Claude with the system prompt, messages, and tool definitions.
       b. If Claude returns tool_use blocks, execute them via ToolRegistry.
       c. Append tool results to messages and loop.
       d. If Claude returns only text, return it as the final response.
    5. The interaction is stored in memory for future context.

WHY THIS APPROACH:
    - REACT PATTERN is the standard agentic AI pattern: it lets Claude
      chain multiple tool calls to answer complex questions (e.g. "summarize
      #general and create a Notion page" requires get_messages → summarize →
      create_notion_page — three tool calls in sequence).
    - MAX_TOOL_ITERATIONS (5) prevents infinite loops if Claude keeps
      calling tools without converging on an answer.
    - SINGLETON PATTERN (get_orchestrator()) ensures one shared instance
      across all Slack event listeners, so memory and tool caches are shared.
    - CONTEXT ENRICHMENT via system prompt injection means Claude sees
      relevant history without the user having to repeat themselves.

RELATIONSHIP TO OTHER FILES:
    - Called by: src/slack/listeners/messages.py, mentions.py, commands.py
    - Uses: src/agent/tools.py (ToolRegistry), src/agent/context_builder.py,
            src/memory/manager.py (MemoryManager)
    - Reads: config/prompts/system_prompt.txt
"""

from pathlib import Path
from typing import Dict, Any, List

from anthropic import AsyncAnthropic

from config.settings import settings
from src.agent.tools import ToolRegistry
from src.agent.context_builder import ContextBuilder
from src.memory.manager import MemoryManager
from src.utils.logger import get_logger

logger = get_logger(__name__)

# ──────────────────────────────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────────────────────────────

# Safety limit: maximum number of tool-call → result cycles in one request.
# If Claude hasn't converged after 5 tool calls, we force a final text
# response.  This prevents infinite loops and runaway API costs.
MAX_TOOL_ITERATIONS = 5

# Path to the system prompt file.  Uses Path relative to this file's
# location so it works regardless of the working directory.
# __file__ → src/agent/orchestrator.py
# .parent.parent.parent → project root
# / "config/prompts/system_prompt.txt"
SYSTEM_PROMPT_PATH = Path(__file__).parent.parent.parent / "config" / "prompts" / "system_prompt.txt"


class AgentOrchestrator:
    """
    Main agent orchestrator using Claude with tool calling (ReAct pattern).

    Architecture:
        AgentOrchestrator ties together:
          - Claude API (AsyncAnthropic) for reasoning
          - ToolRegistry for executing actions
          - ContextBuilder for assembling memory + RAG context
          - MemoryManager for storing interactions

    Lifecycle of a request:
        User message → build context → enrich system prompt →
        ReAct loop (reason → act → repeat) → store in memory → return response
    """

    def __init__(self):
        # The Anthropic async client — used for all Claude API calls.
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)

        # ToolRegistry manages all available tools (Slack, GitHub, Notion,
        # issue detection, reminders).  It provides both JSON schemas (for
        # Claude) and callable implementations (for execution).
        self.tool_registry = ToolRegistry()

        # MemoryManager persists interactions (user message + agent response)
        # so they're available as context for future requests.
        # Created BEFORE ContextBuilder so both share the same instance —
        # this ensures short-term memory written by the orchestrator is
        # visible when the context builder reads conversation history.
        self.memory_manager = MemoryManager()

        # ContextBuilder assembles context from short-term memory, long-term
        # memory, and RAG retrieval.  It receives our MemoryManager so that
        # both components share the same ShortTermMemory dict.
        self.context_builder = ContextBuilder(memory_manager=self.memory_manager)

        # Load the system prompt template from file.  This defines the
        # agent's personality, capabilities, and behavioral guidelines.
        self._system_prompt_base = self._load_system_prompt()
        logger.info("Agent orchestrator initialized")

    def _load_system_prompt(self) -> str:
        """
        Load the system prompt from config/prompts/system_prompt.txt.

        WHY A FILE (not hardcoded):
            - Easy to edit without changing Python code.
            - Can be version-controlled independently.
            - Non-developers can modify the agent's personality.

        FALLBACK:
            If the file is missing (e.g. fresh checkout), we use a sensible
            default so the agent doesn't crash — it just has a generic personality.
        """
        try:
            return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            logger.warning("System prompt file not found, using default")
            return (
                "You are a helpful Slack assistant bot. You have access to tools to "
                "retrieve and summarize channel messages, schedule messages and reminders, "
                "create GitHub issues, and create Notion pages. Respond helpfully and use "
                "tools when appropriate."
            )

    # ──────────────────────────────────────────────────────────────────
    # PUBLIC: Main entry point for processing user messages
    # ──────────────────────────────────────────────────────────────────

    async def process_message(self, user_message: str, user_id: str, channel_id: str) -> str:
        """
        Process a user message and generate an agent response.

        This is the main entry point called by Slack event listeners.

        HOW IT WORKS:
            1. Build context (memory + RAG) for the current user/channel.
            2. Enrich the system prompt with that context.
            3. Build the messages array (history + current message).
            4. Run the ReAct loop (Claude reasons, calls tools, repeats).
            5. Store the interaction in memory for future context.
            6. Return the final text response to be posted in Slack.

        Args:
            user_message: The text the user sent in Slack.
            user_id:      Slack user ID (e.g. "U1234567890").
            channel_id:   Slack channel ID (e.g. "C1234567890").

        Returns:
            The agent's text response (to be posted back to Slack).
        """
        logger.info(f"Processing message from {user_id}")

        try:
            # Step 1: Build context from memory + RAG.
            # This gives Claude access to conversation history, long-term
            # memories (MEMORY.md), and semantically relevant past messages.
            context = await self.context_builder.build_context(user_id, channel_id, user_message)

            # Step 2: Enrich the system prompt with context.
            # The base prompt (personality + guidelines) gets appended with
            # memory and RAG results so Claude has maximum context.
            system_prompt = self._build_system_prompt(context)

            # Step 3: Build the messages array.
            # Conversation history comes first, then the current message.
            # This gives Claude the full thread of conversation.
            messages = self._build_messages(context, user_message)

            # Step 4: Get tool definitions (JSON schemas for Claude).
            tools = self.tool_registry.get_tool_definitions()

            # Step 5: Run the ReAct loop.
            # Claude may call 0 or more tools before giving a final answer.
            agent_response = await self._react_loop(system_prompt, messages, tools)

            # Step 6: Store the interaction in memory.
            # This makes it available as conversation history for the next
            # message from this user in this channel.
            self.memory_manager.store_interaction(user_id, channel_id, user_message, agent_response)

            logger.info("Message processed successfully")
            return agent_response

        except Exception as e:
            # Catch-all: if anything fails (API error, tool crash, etc.),
            # return a friendly error message rather than crashing the bot.
            logger.exception(f"Agent processing failed: {e}")
            return "I encountered an error processing your request. Please try again."

    # ──────────────────────────────────────────────────────────────────
    # PRIVATE: System prompt construction
    # ──────────────────────────────────────────────────────────────────

    def _build_system_prompt(self, context: Dict[str, Any]) -> str:
        """
        Build the final system prompt by appending context to the base prompt.

        WHY APPEND (not replace):
            The base prompt defines personality and guidelines.  Context is
            additive — it gives Claude extra information without changing
            the core behavior instructions.

        The resulting prompt looks like:
            [base prompt from system_prompt.txt]
            # Memory
            [long-term memory entries]
            # Relevant Past Conversations
            [RAG retrieval results]
        """
        prompt = self._system_prompt_base

        # Append long-term memory context (user preferences, past notes).
        if context.get("memory_context"):
            prompt += f"\n\n# Memory\n{context['memory_context']}"

        # Append RAG context (semantically similar past conversations).
        if context.get("rag_context"):
            prompt += f"\n\n# Relevant Past Conversations\n{context['rag_context']}"

        return prompt

    def _build_messages(self, context: Dict[str, Any], user_message: str) -> List[Dict[str, Any]]:
        """
        Build the messages array from conversation history + current message.

        WHY HISTORY FIRST:
            Claude sees messages in order.  By putting history first and the
            current message last, Claude understands the conversation flow
            and can reference earlier context naturally.

        FILTERING:
            Only "user" and "assistant" roles are included (system messages
            and tool results are handled separately).  Empty messages are
            skipped to avoid confusing Claude.
        """
        messages = []

        # Add conversation history (from short-term memory).
        history = context.get("conversation_history", [])
        for entry in history:
            role = entry.get("role", "user")
            content = entry.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

        # Add the current user message at the end.
        messages.append({"role": "user", "content": user_message})

        return messages

    # ──────────────────────────────────────────────────────────────────
    # PRIVATE: ReAct loop (the core agent reasoning loop)
    # ──────────────────────────────────────────────────────────────────

    async def _react_loop(
        self, system_prompt: str, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]
    ) -> str:
        """
        ReAct loop: call Claude → execute tools → feed results → repeat.

        HOW THE REACT PATTERN WORKS:
            1. Call Claude with the system prompt, conversation, and tool schemas.
            2. Claude's response may contain:
               a. Only text blocks → done, return the text.
               b. tool_use blocks → execute each tool, get results.
            3. If tools were called:
               a. Append Claude's response (with tool_use) as an assistant message.
               b. Append tool results as a user message (Anthropic API format).
               c. Go to step 1 (loop).
            4. Repeat up to MAX_TOOL_ITERATIONS times.
            5. If iterations are exhausted, call Claude one final time WITHOUT
               tools to force a text-only response.

        WHY THIS LOOP STRUCTURE:
            - Claude may need multiple tool calls to answer one question.
              Example: "Summarize #general and create a GitHub issue" requires
              get_messages → detect_issues → create_issue — 3 tool calls.
            - The iteration limit prevents infinite loops (e.g. if Claude
              keeps calling the same tool with different parameters).

        WHY TOOL RESULTS AS "user" MESSAGES:
            The Anthropic API requires tool results to be sent as user
            messages with type="tool_result" content blocks.  This is how
            Claude knows the result of its tool call.
        """
        for iteration in range(MAX_TOOL_ITERATIONS):
            # Call Claude with current messages + available tools.
            response = await self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=4096,
                system=system_prompt,
                messages=messages,
                tools=tools if tools else [],
            )

            # Check if the response contains any tool_use blocks.
            has_tool_use = any(block.type == "tool_use" for block in response.content)

            if not has_tool_use:
                # No tool calls → Claude has a final answer.  Extract and return text.
                return self._extract_text(response)

            # ── Tool calls detected: execute them ──
            logger.info(f"ReAct iteration {iteration + 1}: processing tool calls")

            # Append Claude's full response (including tool_use blocks) as
            # an assistant message.  The Anthropic API requires this so it
            # can match tool results to their corresponding tool_use blocks.
            messages.append({"role": "assistant", "content": response.content})

            # Execute each tool_use block and collect results.
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_name = block.name      # e.g. "post_message"
                    tool_input = block.input    # e.g. {"channel_id": "C123", "text": "Hi"}
                    tool_use_id = block.id      # Unique ID to match result to call

                    logger.info(f"Executing tool: {tool_name}")
                    try:
                        # Execute via ToolRegistry (which dispatches to the right service).
                        result = await self.tool_registry.execute_tool(tool_name, **tool_input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": str(result),
                        })
                    except Exception as e:
                        # If a tool fails, send the error back to Claude so it
                        # can decide what to do (retry, inform user, try another approach).
                        logger.error(f"Tool execution failed: {e}")
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": f"Error: {str(e)}",
                            "is_error": True,  # Tells Claude this is an error
                        })

            # Append tool results as a user message (Anthropic API format).
            messages.append({"role": "user", "content": tool_results})

        # ── Safety valve: exhausted all iterations ──
        # If we've hit the limit, call Claude one final time WITHOUT tools
        # to force a text-only response.  This ensures we always return something.
        logger.warning("ReAct loop exhausted max iterations, getting final response")
        response = await self.client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=4096,
            system=system_prompt,
            messages=messages,
        )
        return self._extract_text(response)

    def _extract_text(self, response: Any) -> str:
        """
        Extract text content from Claude's response.

        Claude's response contains a list of content blocks.  Some are
        text blocks (the actual response), some may be tool_use blocks.
        This method filters for text blocks only and joins them.

        FALLBACK:
            If there are no text blocks (rare edge case), return a generic
            message rather than an empty string.
        """
        text_parts = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
        return "\n".join(text_parts) or "I processed your request but have no response to share."


# ──────────────────────────────────────────────────────────────────────
# SINGLETON ACCESSOR
#
# WHY A SINGLETON:
#   Multiple Slack event listeners (messages, mentions, commands) all need
#   to call the same orchestrator.  Creating a new one per request would:
#   - Re-initialize API clients (wasteful).
#   - Lose cached tool services (ReminderService state, etc.).
#   - Re-load the system prompt file (unnecessary I/O).
#
# WHY LAZY INITIALIZATION:
#   The orchestrator isn't created at import time — it's created on the
#   first call to get_orchestrator().  This avoids errors if settings
#   aren't fully loaded yet (e.g. during tests or imports).
# ──────────────────────────────────────────────────────────────────────

_instance: AgentOrchestrator | None = None


def get_orchestrator() -> AgentOrchestrator:
    """Return a lazily-initialised singleton orchestrator."""
    global _instance
    if _instance is None:
        _instance = AgentOrchestrator()
    return _instance
