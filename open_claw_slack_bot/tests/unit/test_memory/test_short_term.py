"""
Tests for short-term memory.
"""

from src.memory.short_term import ShortTermMemory


class TestShortTermMemory:
    def setup_method(self):
        self.memory = ShortTermMemory()

    def test_get_context_creates_new(self):
        ctx = self.memory.get_context("U123", "C456")
        assert ctx.user_id == "U123"
        assert ctx.channel_id == "C456"
        assert ctx.messages == []

    def test_get_context_returns_existing(self):
        ctx1 = self.memory.get_context("U123", "C456")
        ctx1.messages.append({"role": "user", "content": "test"})
        ctx2 = self.memory.get_context("U123", "C456")
        assert len(ctx2.messages) == 1

    def test_add_message(self):
        self.memory.add_message("U123", "C456", "user", "Hello")
        ctx = self.memory.get_context("U123", "C456")
        assert len(ctx.messages) == 1
        assert ctx.messages[0]["role"] == "user"
        assert ctx.messages[0]["content"] == "Hello"

    def test_add_multiple_messages(self):
        self.memory.add_message("U123", "C456", "user", "Hello")
        self.memory.add_message("U123", "C456", "assistant", "Hi there!")
        ctx = self.memory.get_context("U123", "C456")
        assert len(ctx.messages) == 2

    def test_clear_context(self):
        self.memory.add_message("U123", "C456", "user", "test")
        self.memory.clear_context("U123", "C456")
        ctx = self.memory.get_context("U123", "C456")
        assert ctx.messages == []

    def test_clear_nonexistent_context(self):
        # Should not raise
        self.memory.clear_context("U999", "C999")

    def test_separate_user_contexts(self):
        self.memory.add_message("U123", "C456", "user", "From user 1")
        self.memory.add_message("U789", "C456", "user", "From user 2")
        ctx1 = self.memory.get_context("U123", "C456")
        ctx2 = self.memory.get_context("U789", "C456")
        assert len(ctx1.messages) == 1
        assert len(ctx2.messages) == 1
        assert ctx1.messages[0]["content"] == "From user 1"
        assert ctx2.messages[0]["content"] == "From user 2"
