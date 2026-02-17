# Integration Testing Agent

## Purpose
Create and run comprehensive integration tests with sample data to verify all functionalities work correctly before production deployment.

## When to Use
- After implementing new features
- After fixing bugs
- Before deploying to production
- When validating service integrations
- To catch integration issues early

## Approach

### 1. Create Test Suite Structure
```python
class TestResults:
    """Track test results across all test functions."""
    def __init__(self):
        self.passed = []
        self.failed = []
        self.issues = []

    def add_pass(self, test_name: str):
        self.passed.append(test_name)
        logger.info(f"[PASS] {test_name}")

    def add_fail(self, test_name: str, error: str):
        self.failed.append((test_name, error))
        logger.error(f"[FAIL] {test_name} - {error}")
```

### 2. Create Realistic Sample Data
```python
SAMPLE_MESSAGES = [
    {
        "user": "U12345",
        "text": "The login page is broken on mobile Safari",
        "ts": "1234567890.123456",
    },
    # More messages that simulate real scenarios
]
```

### 3. Test Each Service Layer
- **Services**: Test business logic with sample data
- **Agents/Tools**: Test tool registration and execution
- **Memory**: Test store/retrieve operations
- **RAG**: Test retrieval (even with empty vector store)
- **Scheduler**: Test initialization

### 4. Auto-Update Issue Tracking
```python
def update_problems_md(issues):
    """Append new issues to PROBLEMS.md automatically."""
    # Find highest problem number
    # Append new issues with proper formatting
    # Write back to file
```

## Key Patterns

### Pattern 1: Test Service with Sample Data
```python
async def test_service():
    try:
        service = ServiceClass()
        result = await service.method(SAMPLE_DATA)

        if not result:
            results.add_fail("ServiceClass", "Returned empty result")
            return

        # Validate result structure
        if expected_condition_not_met:
            results.add_issue(
                "ServiceClass may not be working correctly",
                f"Expected X, got Y",
                "HIGH"
            )
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

### Pattern 2: Test Tool Registration
```python
async def test_tool_registry():
    registry = ToolRegistry()
    definitions = registry.get_tool_definitions()

    expected_tools = ["tool1", "tool2", "tool3"]
    registered_tools = [tool["name"] for tool in definitions]

    missing_tools = [t for t in expected_tools if t not in registered_tools]
    if missing_tools:
        results.add_fail("ToolRegistry", f"Missing: {missing_tools}")
        results.add_issue(
            "Missing critical tools",
            f"Tools not registered: {', '.join(missing_tools)}",
            "HIGH"
        )
```

### Pattern 3: Test Shared Instances
```python
async def test_shared_memory():
    # Create shared instance
    memory_manager = MemoryManager()

    # Store data through one component
    memory_manager.store_interaction(...)

    # Retrieve through another component
    builder = ContextBuilder(memory_manager=memory_manager)
    context = await builder.build_context(...)

    # Verify data is shared
    if not context_includes_stored_data:
        results.add_fail("Shared memory not working")
```

## Lessons Learned

### ✅ Good Practices
1. **Use realistic sample data** — Mimics real-world scenarios
2. **Test each layer independently** — Services, tools, memory, etc.
3. **Auto-update issue tracking** — Discovered issues go straight to PROBLEMS.md
4. **Non-blocking output** — Use `[PASS]` instead of emojis (encoding issues)
5. **Defensive validation** — Check types, lengths, required fields

### ❌ Common Pitfalls
1. **Don't use emojis in Windows console** — Causes `UnicodeEncodeError`
2. **Don't assume API responses** — Services might return errors
3. **Don't test with real APIs** — Use mock data or conditional tests
4. **Don't ignore parameter names** — `bot_response` not `agent_response`

## Example Test Suite
```python
async def main():
    print("="*80)
    print("INTEGRATION TEST SUITE")
    print("="*80)

    # Prerequisite checks
    check_required_files()
    check_environment_variables()

    # Service tests
    await test_summarization_service()
    await test_issue_detection_service()
    await test_reminder_service()

    # Agent tests
    await test_tool_registry()
    await test_tool_execution()

    # Memory tests
    await test_memory_manager()
    await test_context_builder()

    # Infrastructure tests
    await test_scheduler_jobs()

    # Print summary
    success = results.print_summary()

    # Update PROBLEMS.md
    if results.issues:
        update_problems_md(results.issues)

    return 0 if success else 1
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
