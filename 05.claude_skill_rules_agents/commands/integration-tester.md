Create and run comprehensive integration tests with sample data to verify all functionalities work correctly before production deployment.

## When to Use
- After implementing new features
- After fixing bugs
- Before deploying to production
- When validating service integrations

## Approach

### 1. Create Test Results Tracker

```python
class TestResults:
    def __init__(self):
        self.passed = []
        self.failed = []
        self.issues = []

    def add_pass(self, test_name: str):
        self.passed.append(test_name)
        print(f"[PASS] {test_name}")

    def add_fail(self, test_name: str, error: str):
        self.failed.append((test_name, error))
        print(f"[FAIL] {test_name} - {error}")

    def add_issue(self, title: str, description: str, severity: str):
        self.issues.append({"title": title, "description": description, "severity": severity})

    def print_summary(self):
        print("="*80)
        print("TEST SUMMARY")
        print("="*80)
        print(f"[PASS] Passed: {len(self.passed)}")
        print(f"[FAIL] Failed: {len(self.failed)}")
        print(f"[ISSUE] Issues Found: {len(self.issues)}")
        return len(self.failed) == 0

results = TestResults()
```

### 2. Create Realistic Sample Data

```python
from datetime import datetime, timezone

def generate_sample_messages():
    """Generate realistic Slack messages for testing."""
    base_time = datetime.now(timezone.utc).timestamp()
    return [
        {
            "type": "message",
            "user": "U12345",
            "text": "The login page is completely broken on mobile Safari. Getting a white screen.",
            "ts": str(base_time - 3600),
            "channel": "C123ABC",
        },
        {
            "type": "message",
            "user": "U67890",
            "text": "Confirmed. Tested on iPhone 14 iOS 16.3. Same white screen.",
            "ts": str(base_time - 3400),
            "channel": "C123ABC",
        },
        {
            "type": "message",
            "user": "U12345",
            "text": "Seeing a CORS error from /api/auth endpoint in console logs.",
            "ts": str(base_time - 3000),
            "channel": "C123ABC",
        },
    ]

SAMPLE_MESSAGES = generate_sample_messages()
```

### 3. Test Each Service Layer

```python
@pytest.mark.asyncio
async def test_service():
    try:
        service = ServiceClass()
        result = await service.method(SAMPLE_MESSAGES)

        if not result:
            results.add_fail("ServiceClass", "Returned empty result")
            return

        results.add_pass("ServiceClass")
    except Exception as e:
        results.add_fail("ServiceClass", str(e))
        results.add_issue(
            "ServiceClass crashes",
            f"Exception: {e}",
            "CRITICAL"
        )
```

### 4. Test Tool Registration

```python
@pytest.mark.asyncio
async def test_tool_registry():
    registry = ToolRegistry()
    definitions = registry.get_tool_definitions()
    registered_tools = [tool["name"] for tool in definitions]

    expected_tools = ["get_channel_messages", "post_message", "summarize_channel"]
    missing_tools = [t for t in expected_tools if t not in registered_tools]

    if missing_tools:
        results.add_fail("ToolRegistry", f"Missing: {missing_tools}")
        results.add_issue("Missing critical tools", f"Not registered: {', '.join(missing_tools)}", "HIGH")
    else:
        results.add_pass("ToolRegistry")
```

### 5. Test Shared State

```python
@pytest.mark.asyncio
async def test_shared_memory():
    memory_manager = MemoryManager()

    # Store via one component
    memory_manager.store_interaction(conversation_id="test-123", role="user", content="Hello")

    # Retrieve via another
    builder = ContextBuilder(memory_manager=memory_manager)
    context = await builder.build_context("test-123", "Follow-up")

    history = context.get("conversation_history", [])
    if not history:
        results.add_fail("SharedMemory", "Memory not shared between components (separate instances!)")
    else:
        results.add_pass("SharedMemory")
```

## Key Lessons

### Good Practices
1. **Use realistic sample data** — Mimics real-world scenarios
2. **Test each layer independently** — Services, tools, memory, etc.
3. **Auto-update issue tracking** — Discovered issues go straight to PROBLEMS.md
4. **Use `[PASS]` instead of emojis** — Windows console `UnicodeEncodeError`
5. **Defensive validation** — Check types, lengths, required fields

### Common Pitfalls
1. **Don't use emojis in Windows console** — Causes `UnicodeEncodeError`
2. **Don't assume API responses** — Services might return errors
3. **Don't test with real Slack channels** — Use mock data for unit tests
4. **Don't ignore parameter names** — `bot_response` not `agent_response`

## Test Suite Structure

```python
# test_integration.py
import pytest
import asyncio

SAMPLE_MESSAGES = generate_sample_messages()

# Service Tests
@pytest.mark.asyncio
async def test_summarization_service(): ...

@pytest.mark.asyncio
async def test_issue_detection_service(): ...

@pytest.mark.asyncio
async def test_reminder_service(): ...

# Tool Tests
@pytest.mark.asyncio
async def test_tool_registry(): ...

@pytest.mark.asyncio
async def test_tool_execution(): ...

# Memory Tests
@pytest.mark.asyncio
async def test_memory_manager(): ...

@pytest.mark.asyncio
async def test_shared_memory(): ...

# Infrastructure Tests
def test_scheduler(): ...
def test_required_files(): ...
def test_environment_variables(): ...

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
```

## Defensive Assertions for AI Responses

```python
# BAD - brittle
assert summary == "The team discussed login bugs."

# GOOD - flexible
assert summary is not None
assert len(summary) > 10
assert len(summary) < 10000
assert any(kw in summary.lower() for kw in ["login", "bug", "error", "issue"])
```

## Success Criteria
- All services handle sample data without crashes
- Tool registry has all expected tools
- Memory persists across components
- Scheduler initializes successfully
- No critical issues found

## Output Format
```
================================================================================
TEST SUMMARY
================================================================================
[PASS] Passed: 11
[FAIL] Failed: 0
[ISSUE] Issues Found: 0
================================================================================
```
