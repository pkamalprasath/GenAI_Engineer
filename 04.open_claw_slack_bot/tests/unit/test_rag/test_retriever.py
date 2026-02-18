"""
Tests for RAG semantic retriever.
"""

import pytest
import tempfile
from unittest.mock import patch

from src.rag.retriever import SemanticRetriever


class TestSemanticRetriever:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        with patch("src.rag.store.settings") as mock_settings:
            mock_settings.chroma_persist_directory = self.temp_dir
            self.retriever = SemanticRetriever()

    @pytest.mark.asyncio
    async def test_retrieve_returns_list(self):
        # Add some documents first
        self.retriever.vector_store.add_documents(
            documents=["Important meeting about Python project"],
            metadatas=[{"channel_id": "C123"}],
            ids=["msg1"],
        )
        results = await self.retriever.retrieve("Python project")
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_retrieve_with_channel_filter(self):
        self.retriever.vector_store.add_documents(
            documents=["Test message in channel A"],
            metadatas=[{"channel_id": "C_A"}],
            ids=["ch_a_1"],
        )
        results = await self.retriever.retrieve("test", channel_id="C_A")
        assert isinstance(results, list)

    def test_format_context_empty(self):
        result = self.retriever.format_context_for_prompt([])
        assert result == ""

    def test_format_context_with_data(self):
        contexts = [
            {"text": "Some relevant info", "similarity": 0.85, "metadata": {}},
            {"text": "More context", "similarity": 0.75, "metadata": {}},
        ]
        result = self.retriever.format_context_for_prompt(contexts)
        assert "Context 1" in result
        assert "Context 2" in result
        assert "0.85" in result
        assert "Some relevant info" in result
