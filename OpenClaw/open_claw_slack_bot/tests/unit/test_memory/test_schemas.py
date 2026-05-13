"""
Tests for memory data models.
"""

import pytest
from datetime import datetime
from src.memory.schemas import MemoryEntry, ConversationContext, UserProfile


class TestMemoryEntry:
    def test_create_basic_entry(self):
        entry = MemoryEntry(id="1", content="test content", source="user")
        assert entry.id == "1"
        assert entry.content == "test content"
        assert entry.source == "user"
        assert entry.importance == 1

    def test_default_timestamp(self):
        entry = MemoryEntry(id="1", content="test", source="user")
        assert isinstance(entry.timestamp, datetime)

    def test_importance_validation(self):
        entry = MemoryEntry(id="1", content="test", source="user", importance=5)
        assert entry.importance == 5

    def test_importance_out_of_range(self):
        with pytest.raises(Exception):
            MemoryEntry(id="1", content="test", source="user", importance=6)

    def test_metadata_default(self):
        entry = MemoryEntry(id="1", content="test", source="user")
        assert entry.metadata == {}

    def test_custom_metadata(self):
        entry = MemoryEntry(id="1", content="test", source="user", metadata={"channel": "C123"})
        assert entry.metadata["channel"] == "C123"


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


class TestUserProfile:
    def test_create_profile(self):
        profile = UserProfile(user_id="U123")
        assert profile.user_id == "U123"
        assert profile.name is None
        assert profile.interaction_count == 0
        assert profile.preferences == {}

    def test_profile_with_data(self):
        profile = UserProfile(
            user_id="U123", name="John", interaction_count=10, preferences={"theme": "dark"}
        )
        assert profile.name == "John"
        assert profile.interaction_count == 10
        assert profile.preferences["theme"] == "dark"
