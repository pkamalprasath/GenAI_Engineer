"""
Tests for memory data models.
"""

from datetime import datetime

from src.memory.schemas import ConversationContext


class TestConversationContext:
    def test_create_context(self):
        ctx = ConversationContext(user_id="U123", channel_id="C456")
        assert ctx.user_id == "U123"
        assert ctx.channel_id == "C456"
        assert ctx.messages == []

    def test_default_timestamps(self):
        ctx = ConversationContext(user_id="U123", channel_id="C456")
        assert isinstance(ctx.started_at, datetime)
        assert isinstance(ctx.last_updated, datetime)

    def test_messages_not_shared_between_instances(self):
        a = ConversationContext(user_id="U1", channel_id="C1")
        b = ConversationContext(user_id="U2", channel_id="C2")
        a.messages.append({"role": "user", "content": "hi"})
        assert b.messages == []
