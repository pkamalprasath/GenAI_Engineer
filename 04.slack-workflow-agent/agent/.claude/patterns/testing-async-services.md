# Pattern: Testing Async Services

## Comprehensive Testing Strategy for Async Python Services

### Learned from: Creating test_integration.py

---

## Pattern 1: Sample Data Generation

### Create Realistic Test Data

**Purpose:** Test with data that mimics production scenarios

**Example: Slack Messages with Bug Reports**

```python
# test_integration.py
from datetime import datetime, timezone

def generate_sample_messages():
    """Generate realistic Slack messages for testing."""
    base_time = datetime.now(timezone.utc).timestamp()

    messages = [
        {
            "type": "message",
            "user": "U12345",
            "text": "The login page is completely broken on mobile Safari. Getting a white screen after submitting credentials.",
            "ts": str(base_time - 3600),
            "channel": "C123ABC",
        },
        {
            "type": "message",
            "user": "U67890",
            "text": "I can confirm this issue. Tested on iPhone 14, iOS 16.3. Same white screen.",
            "ts": str(base_time - 3400),
            "channel": "C123ABC",
        },
        {
            "type": "message",
            "user": "U12345",
            "text": "Checked console logs - seeing a CORS error from /api/auth endpoint. Might be related to yesterday's nginx config change.",
            "ts": str(base_time - 3000),
            "channel": "C123ABC",
        },
        {
            "type": "message",
            "user": "U11111",
            "text": "Also seeing intermittent 500 errors on the dashboard API. About 30% of requests failing.",
            "ts": str(base_time - 2600),
            "channel": "C123ABC",
        },
        {
            "type": "message",
            "user": "U22222",
            "text": "I'll investigate both issues this afternoon and report back.",
            "ts": str(base_time - 2400),
            "channel": "C123ABC",
        }
    ]

    return messages

# Use in tests
SAMPLE_MESSAGES = generate_sample_messages()
```

**Why this works:**
- Realistic content (bug reports, confirmations, investigations)
- Proper Slack message format (type, user, text, ts, channel)
- Multiple message types (bug reports, confirmations, action items)
- Varied timestamps (simulates conversation flow)
- Designed to trigger expected behaviors (issue detection)

---

## Pattern 2: Async Test Functions

### Use pytest-asyncio for Async Tests

**Setup:**
```bash
pip install pytest pytest-asyncio
```

**Pattern:**
```python
import pytest
import asyncio

@pytest.mark.asyncio
async def test_async_service():
    """Test an async service method."""

    # Arrange
    service = SomeAsyncService()
    input_data = {"key": "value"}

    # Act
    result = await service.async_method(input_data)

    # Assert
    assert result["success"] is True
    assert "data" in result
```

**Key points:**
- Mark with `@pytest.mark.asyncio`
- Use `async def` for test functions
- Use `await` for async calls
- Follow AAA pattern (Arrange, Act, Assert)

---

## Pattern 3: Test Service Layer with Real API Calls

### When to Use Real APIs in Tests

**Integration tests** (not unit tests) should use real APIs to verify:
- Service actually works with external dependencies
- API responses are parsed correctly
- Error handling works with real error responses

**Example: Testing SummarizationService**

```python
@pytest.mark.asyncio
async def test_summarization_service():
    """Test SummarizationService with real Claude API."""

    # Arrange
    service = SummarizationService()
    messages = generate_sample_messages()

    # Act
    summary = await service.summarize_messages(
        messages=messages,
        channel_name="test-channel"
    )

    # Assert
    assert summary is not None
    assert len(summary) > 0
    assert "login" in summary.lower() or "bug" in summary.lower()

    print(f"[PASS] SummarizationService generated summary: {len(summary)} chars")
```

**Why use real API:**
- Validates actual Claude API integration
- Catches API changes or deprecations
- Verifies response parsing logic
- Tests realistic latency and errors

**When NOT to use real API:**
- Unit tests (use mocks)
- CI/CD pipelines (use mocks or test mode)
- Rate limit concerns (use mocks)

---

## Pattern 4: Test Error Handling

### Verify Services Handle Errors Gracefully

**Example: Test with Invalid Input**

```python
@pytest.mark.asyncio
async def test_summarization_with_empty_messages():
    """Service should handle empty input gracefully."""

    service = SummarizationService()

    # Test with empty messages
    summary = await service.summarize_messages(
        messages=[],
        channel_name="empty-channel"
    )

    # Should return empty or error message, not crash
    assert summary is not None
```

**Example: Test with Invalid API Token**

```python
@pytest.mark.asyncio
async def test_service_with_invalid_token():
    """Service should return error dict, not raise exception."""

    # Temporarily override token
    original_token = settings.anthropic_api_key
    settings.anthropic_api_key = "invalid-token"

    try:
        service = SummarizationService()
        messages = generate_sample_messages()

        # Should return error, not raise
        result = await service.summarize_messages(messages, "test")

        # Verify error handling
        assert result is not None
        # Service might return empty string or error message

    finally:
        # Restore original token
        settings.anthropic_api_key = original_token
```

---

## Pattern 5: Test Tool Execution via ToolRegistry

### Test Tools in Isolation and via Registry

**Direct Method Test:**
```python
@pytest.mark.asyncio
async def test_tool_method_directly():
    """Test tool method directly (bypass registry)."""

    registry = ToolRegistry()

    result = await registry._summarize_channel(
        channel_id="C123ABC",
        hours=24
    )

    assert "success" in result
    assert "summary" in result or "error" in result
```

**Registry Execution Test:**
```python
@pytest.mark.asyncio
async def test_tool_via_registry():
    """Test tool execution via registry (full flow)."""

    registry = ToolRegistry()

    result = await registry.execute_tool(
        "summarize_channel",
        channel_id="C123ABC",
        hours=24
    )

    assert isinstance(result, dict)
    assert "success" in result

    print(f"[PASS] Tool execution returned: {result.keys()}")
```

**Why test both:**
- Direct method: Tests implementation
- Via registry: Tests registration and dispatch

---

## Pattern 6: Test Stateful Components

### Verify Shared State Works Correctly

**Example: Testing MemoryManager Persistence**

```python
@pytest.mark.asyncio
async def test_memory_manager_persistence():
    """Test that MemoryManager stores and retrieves correctly."""

    # Arrange
    memory_manager = MemoryManager()
    conv_id = "test-conversation-123"

    # Act: Store interaction
    memory_manager.store_interaction(
        conversation_id=conv_id,
        role="user",
        content="Hello, bot!"
    )

    memory_manager.store_interaction(
        conversation_id=conv_id,
        role="bot",
        content="Hi there! How can I help?"
    )

    # Act: Retrieve history
    history = memory_manager.get_conversation_history(conv_id)

    # Assert
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "Hello, bot!"
    assert history[1]["role"] == "bot"
    assert history[1]["content"] == "Hi there! How can I help?"

    print(f"[PASS] MemoryManager stored and retrieved {len(history)} interactions")
```

**Example: Testing Shared Instance (Problem #5 Fix)**

```python
@pytest.mark.asyncio
async def test_orchestrator_context_builder_share_memory():
    """Verify Orchestrator and ContextBuilder share MemoryManager."""

    # Arrange
    orchestrator = Orchestrator()
    conv_id = "test-shared-memory"

    # Act: Store via orchestrator
    orchestrator.memory_manager.store_interaction(
        conversation_id=conv_id,
        role="user",
        content="Test message"
    )

    # Act: Retrieve via context_builder
    context = await orchestrator.context_builder.build_context(
        conversation_id=conv_id,
        user_message="Follow-up"
    )

    # Assert: Should see the stored interaction
    history = context.get("conversation_history", [])
    assert len(history) > 0
    assert any("Test message" in str(interaction) for interaction in history)

    print("[PASS] MemoryManager is shared between components")
```

---

## Pattern 7: Test Background Jobs

### Verify Scheduler Starts and Jobs Are Configured

**Example: Test Scheduler Initialization**

```python
def test_scheduler_initialization():
    """Test that APScheduler starts with all jobs."""

    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from src.app import create_app

    # Create app (which starts scheduler)
    app = create_app()

    # Note: Can't easily test scheduler in isolation
    # This test verifies app creation doesn't crash

    print("[PASS] Scheduler initialization didn't crash")
```

**Better approach: Test jobs can be called manually**

```python
@pytest.mark.asyncio
async def test_reminder_delivery_job():
    """Test reminder delivery job logic (without scheduler)."""

    # Create test reminder
    service = ReminderService()
    user_id = "U123"
    channel_id = "C123"
    message = "Test reminder"
    deliver_at = datetime.now(timezone.utc) - timedelta(seconds=10)  # Past

    # Schedule reminder
    result = await service.schedule_reminder(user_id, channel_id, message, deliver_at)
    assert result["success"] is True

    # Execute delivery job manually
    from src.app import _deliver_reminders  # Hypothetical job function
    delivered = await _deliver_reminders()

    # Verify reminder was delivered
    assert delivered is not None

    print("[PASS] Reminder delivery job logic works")
```

---

## Pattern 8: Test Conditional Registration

### Verify Tools Register Based on Configuration

**Example: GitHub Tools Only Register When Token Present**

```python
def test_conditional_tool_registration():
    """GitHub tools should only register if token is configured."""

    from config.settings import settings

    # Save original token
    original_token = settings.github_token

    try:
        # Test WITH GitHub token
        settings.github_token = "ghp_test_token"
        registry = ToolRegistry()
        assert "create_github_issue" in registry.tools
        assert "list_github_issues" in registry.tools

        # Test WITHOUT GitHub token
        settings.github_token = None
        registry = ToolRegistry()
        assert "create_github_issue" not in registry.tools
        assert "list_github_issues" not in registry.tools

        print("[PASS] Conditional tool registration works")

    finally:
        # Restore original
        settings.github_token = original_token
```

---

## Pattern 9: Defensive Assertions

### Test Should Handle Variability in Responses

**Problem:** AI responses are non-deterministic

**Solution:** Use flexible assertions

**❌ Brittle:**
```python
summary = await service.summarize_messages(messages, "test")
assert summary == "The team discussed login bugs and API errors."
```

**✅ Flexible:**
```python
summary = await service.summarize_messages(messages, "test")

# Check that summary exists and is reasonable
assert summary is not None
assert len(summary) > 10  # Not empty
assert len(summary) < 10000  # Not absurdly long

# Check for expected keywords (loose matching)
summary_lower = summary.lower()
assert any(keyword in summary_lower for keyword in ["login", "bug", "error", "issue"])

print(f"[PASS] Summary generated: {len(summary)} chars, contains relevant keywords")
```

---

## Pattern 10: Auto-Update Documentation from Tests

### Tests Can Generate/Update Documentation

**Example: Auto-update PROBLEMS.md**

```python
def update_problems_file(problem_number: int, title: str, details: dict):
    """Automatically update PROBLEMS.md with test findings."""

    problems_file = "PROBLEMS.md"

    # Read existing content
    with open(problems_file, "r") as f:
        content = f.read()

    # Generate problem entry
    new_problem = f"""
### Problem #{problem_number}: {title}

**Status:** 🔴 FOUND (via integration test)
**Severity:** {details['severity']}
**Impact:** {details['impact']}

**What's Wrong:**
{details['description']}

**How to Fix:**
{details['fix']}

**Test:** `{details['test_name']}`

---
"""

    # Append to file
    with open(problems_file, "a") as f:
        f.write(new_problem)

    print(f"[INFO] Added Problem #{problem_number} to PROBLEMS.md")
```

**Usage in test:**
```python
@pytest.mark.asyncio
async def test_mcp_function_imports():
    """Test that tools don't import MCP-decorated functions."""

    registry = ToolRegistry()

    try:
        result = await registry.execute_tool("get_channel_messages", channel_id="C123")

        if "'FunctionTool' object is not callable" in str(result.get("error", "")):
            # Found the issue! Document it
            update_problems_file(
                problem_number=13,
                title="MCP Function Import Issue",
                details={
                    "severity": "CRITICAL",
                    "impact": "All agent Slack tools broken",
                    "description": "Tools importing FastMCP-decorated functions fail with 'FunctionTool' object is not callable",
                    "fix": "Rewrite tools to use Slack SDK directly instead of importing MCP functions",
                    "test_name": "test_mcp_function_imports"
                }
            )

            pytest.fail("MCP function import issue detected (Problem #13)")

    except Exception as e:
        print(f"[FAIL] Tool execution raised exception: {e}")
        pytest.fail(str(e))
```

---

## Complete Test Suite Structure

```python
# test_integration.py
import pytest
import asyncio
from datetime import datetime, timezone

# ========================================
# Sample Data
# ========================================

def generate_sample_messages():
    """Realistic test data."""
    # ...
    return messages

SAMPLE_MESSAGES = generate_sample_messages()

# ========================================
# Service Tests
# ========================================

@pytest.mark.asyncio
async def test_summarization_service():
    """Test SummarizationService with real API."""
    # ...

@pytest.mark.asyncio
async def test_issue_detection_service():
    """Test IssueDetectionService with sample data."""
    # ...

@pytest.mark.asyncio
async def test_reminder_service():
    """Test ReminderService CRUD operations."""
    # ...

# ========================================
# Tool Tests
# ========================================

@pytest.mark.asyncio
async def test_tool_registry():
    """Test all tools are registered."""
    # ...

@pytest.mark.asyncio
async def test_tool_execution():
    """Test tool dispatch mechanism."""
    # ...

# ========================================
# Memory Tests
# ========================================

@pytest.mark.asyncio
async def test_memory_manager():
    """Test memory storage and retrieval."""
    # ...

@pytest.mark.asyncio
async def test_shared_memory():
    """Test MemoryManager is shared (Problem #5 fix)."""
    # ...

# ========================================
# Infrastructure Tests
# ========================================

def test_scheduler():
    """Test scheduler starts successfully."""
    # ...

def test_required_files():
    """Test all required files exist."""
    # ...

def test_environment_variables():
    """Test required env vars are set."""
    # ...

# ========================================
# Run Tests
# ========================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
```

---

## Running Tests

### Command Line

```bash
# Run all tests
pytest test_integration.py -v

# Run specific test
pytest test_integration.py::test_summarization_service -v

# Run with output
pytest test_integration.py -v -s

# Run async tests only
pytest test_integration.py -v -k asyncio
```

### Programmatic

```python
# At end of test file
if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "-s"])
```

---

## Success Criteria

- [ ] All critical services tested (Summarization, IssueDetection, Reminder)
- [ ] All tools tested (registration and execution)
- [ ] Memory management tested (storage, retrieval, sharing)
- [ ] Infrastructure tested (scheduler, files, environment)
- [ ] Error handling tested (invalid input, missing tokens)
- [ ] Sample data is realistic and covers edge cases
- [ ] Tests use flexible assertions (handle AI variability)
- [ ] Tests auto-document issues (update PROBLEMS.md)

**Result:** Comprehensive test suite that catches integration issues before production.
