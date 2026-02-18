# Pattern: Testing Async Services

## Setup

```bash
pip install pytest pytest-asyncio
```

## Pattern 1: Sample Data Generation

Create realistic test data that mimics production:

```python
from datetime import datetime, timezone

def generate_sample_messages():
    base_time = datetime.now(timezone.utc).timestamp()
    return [
        {
            "type": "message",
            "user": "U12345",
            "text": "The login page is broken on mobile Safari. White screen after login.",
            "ts": str(base_time - 3600),
            "channel": "C123ABC",
        },
        {
            "type": "message",
            "user": "U67890",
            "text": "Confirmed on iPhone 14. Also seeing 500 errors on dashboard API.",
            "ts": str(base_time - 3400),
            "channel": "C123ABC",
        },
    ]

SAMPLE_MESSAGES = generate_sample_messages()
```

## Pattern 2: Async Test Functions

```python
import pytest

@pytest.mark.asyncio
async def test_async_service():
    service = SomeAsyncService()
    result = await service.async_method(SAMPLE_MESSAGES)
    assert result["success"] is True
    assert "data" in result
```

## Pattern 3: Service Layer Tests

```python
@pytest.mark.asyncio
async def test_summarization_service():
    service = SummarizationService()
    summary = await service.summarize_messages(
        messages=SAMPLE_MESSAGES, channel_name="test-channel"
    )
    assert summary is not None
    assert len(summary) > 0
```

## Pattern 4: Tool Registration Tests

```python
@pytest.mark.asyncio
async def test_tool_registry():
    registry = ToolRegistry()
    definitions = registry.get_tool_definitions()
    registered = [t["name"] for t in definitions]

    expected = ["get_channel_messages", "post_message", "summarize_channel"]
    missing = [t for t in expected if t not in registered]

    if missing:
        pytest.fail(f"Missing tools: {missing}")
```

## Pattern 5: Shared State Tests

```python
@pytest.mark.asyncio
async def test_shared_memory():
    orchestrator = Orchestrator()

    # Store via orchestrator
    orchestrator.memory_manager.store_interaction(
        conversation_id="test-123", role="user", content="Hello"
    )

    # Retrieve via context_builder — must use SAME instance
    context = await orchestrator.context_builder.build_context("test-123", "Follow-up")
    history = context.get("conversation_history", [])
    assert len(history) > 0, "Separate MemoryManager instances detected!"
```

## Pattern 6: Conditional Tool Registration

```python
def test_conditional_tools():
    from config.settings import settings
    original = settings.github_token

    try:
        settings.github_token = "ghp_test"
        registry = ToolRegistry()
        assert "create_github_issue" in registry.tools

        settings.github_token = None
        registry = ToolRegistry()
        assert "create_github_issue" not in registry.tools
    finally:
        settings.github_token = original
```

## Pattern 7: Defensive Assertions for AI Responses

```python
# BAD — brittle
assert summary == "The team discussed login bugs."

# GOOD — flexible for non-deterministic AI
summary = await service.summarize_messages(SAMPLE_MESSAGES, "test")
assert summary is not None
assert len(summary) > 10       # Not empty
assert len(summary) < 10000    # Not absurdly long
assert any(kw in summary.lower() for kw in ["login", "bug", "error", "api"])
```

## Windows Console Note

**Never use emojis in print/logger statements on Windows** — causes `UnicodeEncodeError`.

```python
# BAD (Windows console)
print(f"✅ Passed: {test_name}")
print(f"❌ Failed: {test_name}")

# GOOD
print(f"[PASS] {test_name}")
print(f"[FAIL] {test_name}")
```

## Complete Test Suite Structure

```python
# test_integration.py

SAMPLE_MESSAGES = generate_sample_messages()

# --- Service Tests ---
@pytest.mark.asyncio
async def test_summarization_service(): ...

@pytest.mark.asyncio
async def test_reminder_service(): ...

# --- Tool Tests ---
@pytest.mark.asyncio
async def test_tool_registry(): ...

@pytest.mark.asyncio
async def test_tool_execution(): ...

# --- Memory Tests ---
@pytest.mark.asyncio
async def test_memory_manager(): ...

@pytest.mark.asyncio
async def test_shared_memory(): ...

# --- Infrastructure ---
def test_scheduler_init(): ...
def test_required_files(): ...
def test_env_vars(): ...

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
```

## Running Tests

```bash
pytest test_integration.py -v -s                   # All tests with output
pytest test_integration.py::test_tool_registry -v  # Specific test
pytest test_integration.py -v -k "memory"          # Tests matching keyword
```
