"""
Tests for agent orchestrator.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from src.agent.orchestrator import AgentOrchestrator


class TestAgentOrchestrator:
    def setup_method(self):
        with (
            patch("src.agent.orchestrator.AsyncAnthropic"),
            patch("src.agent.orchestrator.ToolRegistry"),
            patch("src.agent.orchestrator.ContextBuilder") as mock_cb,
            patch("src.agent.orchestrator.MemoryManager"),
        ):
            # Mock context builder
            mock_cb_instance = MagicMock()
            mock_cb_instance.build_context = AsyncMock(
                return_value={
                    "conversation_history": [],
                    "memory_context": "",
                    "rag_context": "",
                }
            )
            mock_cb.return_value = mock_cb_instance
            self.orchestrator = AgentOrchestrator()

    def test_build_system_prompt_basic(self):
        context = {"memory_context": "", "rag_context": ""}
        prompt = self.orchestrator._build_system_prompt(context)
        assert "Slack assistant" in prompt
        assert "tools" in prompt

    def test_build_system_prompt_with_memory(self):
        context = {"memory_context": "User prefers dark mode", "rag_context": ""}
        prompt = self.orchestrator._build_system_prompt(context)
        assert "Memory" in prompt
        assert "dark mode" in prompt

    def test_build_system_prompt_with_rag(self):
        context = {"memory_context": "", "rag_context": "# Relevant past conversations"}
        prompt = self.orchestrator._build_system_prompt(context)
        assert "past conversations" in prompt

    def test_extract_text_joins_text_blocks(self):
        tool_block = MagicMock(type="tool_use")
        text_a = MagicMock(type="text", text="Here is")
        text_b = MagicMock(type="text", text="my response")
        response = MagicMock(content=[text_a, tool_block, text_b])
        assert self.orchestrator._extract_text(response) == "Here is\nmy response"

    def test_extract_text_empty_falls_back(self):
        response = MagicMock(content=[])
        assert "no response" in self.orchestrator._extract_text(response).lower()

    @pytest.mark.asyncio
    async def test_react_loop_executes_tool_then_answers(self):
        tool_call = MagicMock(type="tool_use", id="tu_1", input={"channel_id": "C1"})
        tool_call.name = "list_channels"
        first = MagicMock(content=[tool_call])
        final = MagicMock(content=[MagicMock(type="text", text="You have 3 channels")])
        self.orchestrator.client.messages.create = AsyncMock(side_effect=[first, final])
        self.orchestrator.tool_registry.execute_tool = AsyncMock(return_value={"count": 3})

        messages = [{"role": "user", "content": "how many channels?"}]
        answer = await self.orchestrator._react_loop("sys", messages, tools=[{"name": "list_channels"}])

        assert answer == "You have 3 channels"
        self.orchestrator.tool_registry.execute_tool.assert_awaited_once_with("list_channels", channel_id="C1")
        tool_result = messages[-1]["content"][0]
        assert tool_result["type"] == "tool_result" and tool_result["tool_use_id"] == "tu_1"

    @pytest.mark.asyncio
    async def test_react_loop_returns_tool_errors_to_claude(self):
        tool_call = MagicMock(type="tool_use", id="tu_2", input={})
        tool_call.name = "create_github_issue"
        first = MagicMock(content=[tool_call])
        final = MagicMock(content=[MagicMock(type="text", text="GitHub is unavailable")])
        self.orchestrator.client.messages.create = AsyncMock(side_effect=[first, final])
        self.orchestrator.tool_registry.execute_tool = AsyncMock(side_effect=RuntimeError("503"))

        messages = [{"role": "user", "content": "file an issue"}]
        answer = await self.orchestrator._react_loop("sys", messages, tools=[{"name": "x"}])

        assert answer == "GitHub is unavailable"
        tool_result = messages[-1]["content"][0]
        assert tool_result["is_error"] is True and "503" in tool_result["content"]

    @pytest.mark.asyncio
    async def test_process_message_error_handling(self):
        self.orchestrator.context_builder.build_context = AsyncMock(
            side_effect=Exception("Context build failed")
        )
        result = await self.orchestrator.process_message("test", "U123", "C456")
        assert "error" in result.lower()
