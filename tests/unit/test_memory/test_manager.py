"""
Tests for memory manager.
"""

import tempfile
from unittest.mock import patch
from src.memory.manager import MemoryManager


class TestMemoryManager:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        with patch("src.memory.long_term.settings") as mock_settings:
            mock_settings.memory_store_path = self.temp_dir
            self.manager = MemoryManager()

    def teardown_method(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_init(self):
        assert self.manager.short_term is not None
        assert self.manager.long_term is not None

    def test_store_interaction(self):
        self.manager.store_interaction(
            user_id="U123", channel_id="C456", user_message="Hello", bot_response="Hi there!"
        )
        # Check short-term
        history = self.manager.get_conversation_history("U123", "C456")
        assert len(history) == 2

    def test_get_conversation_history(self):
        self.manager.short_term.add_message("U123", "C456", "user", "msg1")
        self.manager.short_term.add_message("U123", "C456", "assistant", "resp1")
        self.manager.short_term.add_message("U123", "C456", "user", "msg2")

        history = self.manager.get_conversation_history("U123", "C456", limit=2)
        assert len(history) == 2

    def test_recall_memory_found(self):
        self.manager.long_term.write_to_memory("Important project info")
        result = self.manager.recall_memory("project")
        assert "project" in result.lower()

    def test_recall_memory_not_found(self):
        self.manager.long_term.write_to_memory("Some content")
        result = self.manager.recall_memory("nonexistent_keyword_xyz")
        assert result == ""
