"""
Tests for agent tool registry.
"""

import pytest
from unittest.mock import patch

from src.agent.tools import ToolRegistry


class TestToolRegistry:
    def setup_method(self):
        with patch("src.agent.tools.MCPRegistry"):
            self.registry = ToolRegistry()

    def test_init_registers_tools(self):
        assert len(self.registry.tools) > 0
        assert "get_channel_messages" in self.registry.tools
        assert "post_message" in self.registry.tools
        assert "schedule_message" in self.registry.tools
        assert "create_github_issue" in self.registry.tools
        assert "create_notion_page" in self.registry.tools

    def test_get_tool_definitions(self):
        definitions = self.registry.get_tool_definitions()
        assert isinstance(definitions, list)
        assert len(definitions) >= 3

        # Check structure
        for defn in definitions:
            assert "name" in defn
            assert "description" in defn
            assert "input_schema" in defn
            assert "type" in defn["input_schema"]

    @pytest.mark.asyncio
    async def test_execute_nonexistent_tool(self):
        with pytest.raises(ValueError, match="Tool not found"):
            await self.registry.execute_tool("nonexistent_tool")

    @pytest.mark.asyncio
    async def test_execute_tool_with_error(self):
        # Mock a tool that raises an exception
        async def failing_tool(**kwargs):
            raise RuntimeError("Tool crashed")

        self.registry.tools["failing_tool"] = failing_tool
        result = await self.registry.execute_tool("failing_tool")
        assert "error" in result
