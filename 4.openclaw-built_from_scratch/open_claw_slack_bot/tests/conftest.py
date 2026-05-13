"""
Pytest Configuration and Fixtures

Shared test fixtures and configuration.
"""

import sys
import os
import pytest
from pathlib import Path
from unittest.mock import AsyncMock

# Ensure project root is in path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Set environment variables for testing
os.environ.setdefault("SLACK_BOT_TOKEN", "xoxb-test-token-for-testing")
os.environ.setdefault("SLACK_APP_TOKEN", "xapp-test-token-for-testing")
os.environ.setdefault("SLACK_SIGNING_SECRET", "test-signing-secret")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-key")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-openai-key")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test-github-token")
os.environ.setdefault("NOTION_TOKEN", "secret_test-notion-token")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("MEMORY_STORE_PATH", "./memory_store")
os.environ.setdefault("CHROMA_PERSIST_DIRECTORY", "./memory_store/chroma_db")


@pytest.fixture
def mock_slack_client():
    """Mock Slack WebClient."""
    client = AsyncMock()
    client.chat_postMessage = AsyncMock(return_value={"ts": "1234567890.123456", "channel": "C123"})
    client.conversations_history = AsyncMock(return_value={"messages": []})
    client.reactions_add = AsyncMock(return_value={"ok": True})
    client.reactions_remove = AsyncMock(return_value={"ok": True})
    return client


@pytest.fixture
def sample_message_event():
    """Sample Slack message event."""
    return {
        "type": "message",
        "text": "Hello bot!",
        "user": "U123ABC456",
        "channel": "C123ABC456",
        "ts": "1234567890.123456",
    }


@pytest.fixture
def sample_messages():
    """Sample list of Slack messages."""
    return [
        {"text": "Hey everyone!", "user": "U123", "ts": "1234567890.000001"},
        {"text": "How's the project going?", "user": "U456", "ts": "1234567890.000002"},
        {"text": "We just shipped v2.0!", "user": "U789", "ts": "1234567890.000003"},
    ]
