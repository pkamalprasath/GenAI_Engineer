"""
Tests for long-term memory.
"""

import tempfile
from pathlib import Path

from src.memory.long_term import LongTermMemory


class TestLongTermMemory:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.memory = LongTermMemory(base_path=self.temp_dir)

    def teardown_method(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_init_creates_directories(self):
        assert Path(self.temp_dir).exists()
        assert (Path(self.temp_dir) / "memory").exists()

    def test_write_and_read_memory(self):
        self.memory.write_to_memory("Test content")
        content = self.memory.read_memory()
        assert "Test content" in content

    def test_write_memory_append(self):
        self.memory.write_to_memory("First")
        self.memory.write_to_memory("Second")
        content = self.memory.read_memory()
        assert "First" in content
        assert "Second" in content

    def test_write_memory_overwrite(self):
        self.memory.write_to_memory("First")
        self.memory.write_to_memory("Second", append=False)
        content = self.memory.read_memory()
        assert "First" not in content
        assert "Second" in content

    def test_read_nonexistent_memory(self):
        content = self.memory.read_memory()
        assert content == ""

    def test_write_daily_log(self):
        self.memory.write_daily_log("Log entry")
        content = self.memory.read_daily_log()
        assert "Log entry" in content

    def test_read_nonexistent_daily_log(self):
        content = self.memory.read_daily_log("2020-01-01")
        assert content == ""

    def test_get_all_daily_logs(self):
        self.memory.write_daily_log("Entry 1")
        logs = self.memory.get_all_daily_logs()
        assert len(logs) >= 1

    def test_daily_log_timestamp(self):
        self.memory.write_daily_log("Timestamped entry")
        content = self.memory.read_daily_log()
        assert "###" in content  # Contains timestamp header
