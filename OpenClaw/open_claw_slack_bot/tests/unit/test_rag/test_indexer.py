"""
Tests for RAG conversation indexer.
"""

import pytest
import tempfile
from unittest.mock import patch

from src.rag.indexer import ConversationIndexer


class TestConversationIndexer:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        with (
            patch("src.rag.store.settings") as store_settings,
            patch("src.rag.indexer.settings") as indexer_settings,
        ):
            store_settings.chroma_persist_directory = self.temp_dir
            indexer_settings.rag_message_limit = 200
            self.indexer = ConversationIndexer()

    @pytest.mark.asyncio
    async def test_index_messages(self):
        messages = [
            {"text": "Hello everyone", "ts": "1234567890.000001", "user": "U123"},
            {"text": "How is the project going?", "ts": "1234567890.000002", "user": "U456"},
        ]
        count = await self.indexer.index_messages("C123", messages)
        assert count == 2

    @pytest.mark.asyncio
    async def test_index_empty_messages(self):
        count = await self.indexer.index_messages("C123", [])
        assert count == 0

    @pytest.mark.asyncio
    async def test_index_skips_empty_text(self):
        messages = [
            {"text": "", "ts": "1234567890.000001", "user": "U123"},
            {"text": "Valid message", "ts": "1234567890.000002", "user": "U456"},
        ]
        count = await self.indexer.index_messages("C123", messages)
        assert count == 1

    @pytest.mark.asyncio
    async def test_reindex_channel(self):
        messages = [
            {"text": "First batch", "ts": "1234567890.000001", "user": "U123"},
        ]
        await self.indexer.index_messages("C_REINDEX", messages)

        new_messages = [
            {"text": "New batch 1", "ts": "1234567890.000003", "user": "U123"},
            {"text": "New batch 2", "ts": "1234567890.000004", "user": "U456"},
        ]
        count = await self.indexer.reindex_channel("C_REINDEX", new_messages)
        assert count == 2
