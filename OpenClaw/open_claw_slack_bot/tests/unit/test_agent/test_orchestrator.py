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

    @pytest.mark.asyncio
    async def test_process_response_text_only(self):
        mock_response = MagicMock()
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Here is my response"
        mock_response.content = [text_block]

        result = await self.orchestrator._process_response(mock_response)
        assert result == "Here is my response"

    @pytest.mark.asyncio
    async def test_process_response_empty(self):
        mock_response = MagicMock()
        mock_response.content = []

        result = await self.orchestrator._process_response(mock_response)
        assert "no response" in result.lower()

    @pytest.mark.asyncio
    async def test_process_message_error_handling(self):
        self.orchestrator.context_builder.build_context = AsyncMock(
            side_effect=Exception("Context build failed")
        )
        result = await self.orchestrator.process_message("test", "U123", "C456")
        assert "error" in result.lower()
