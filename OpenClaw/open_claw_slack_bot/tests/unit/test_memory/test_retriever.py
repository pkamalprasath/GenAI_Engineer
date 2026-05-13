"""
Tests for memory retriever.
"""

import tempfile
from unittest.mock import patch
from src.memory.retriever import MemoryRetriever
from src.memory.short_term import ShortTermMemory
from src.memory.long_term import LongTermMemory


class TestMemoryRetriever:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.short_term = ShortTermMemory()
        with patch("src.memory.long_term.settings") as mock_settings:
            mock_settings.memory_store_path = self.temp_dir
            self.long_term = LongTermMemory(base_path=self.temp_dir)
        self.retriever = MemoryRetriever(
            short_term=self.short_term,
            long_term=self.long_term,
        )

    def teardown_method(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_search_short_term(self):
        self.short_term.add_message("U123", "C456", "user", "Python is great")
        results = self.retriever.search("Python", user_id="U123", channel_id="C456")
        assert len(results) >= 1
        assert results[0]["source"] == "short_term"

    def test_search_long_term(self):
        self.long_term.write_to_memory("Important deployment notes")
        results = self.retriever.search("deployment")
        assert len(results) >= 1
        assert results[0]["source"] == "long_term"

    def test_search_daily_log(self):
        self.long_term.write_daily_log("Meeting about API redesign")
        results = self.retriever.search("API redesign")
        assert len(results) >= 1
        assert results[0]["source"] == "daily_log"

    def test_search_no_results(self):
        results = self.retriever.search("nonexistent_query_xyz")
        assert results == []

    def test_search_without_user_context(self):
        self.long_term.write_to_memory("General knowledge")
        results = self.retriever.search("General")
        assert len(results) >= 1
