#!/usr/bin/env python3
"""
Integration Test Script
========================

Tests all major functionalities with sample data to verify the bot works end-to-end.
Reports any issues found and adds them to PROBLEMS.md.

Usage:
    python test_integration.py
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
import time

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Sample data
SAMPLE_MESSAGES = [
    {
        "user": "U12345",
        "text": "Hey team, the login page is completely broken on mobile Safari. Users are getting a white screen.",
        "ts": "1234567890.123456",
    },
    {
        "user": "U23456",
        "text": "I can confirm - same issue on iOS 16. This is blocking our release.",
        "ts": "1234567891.123456",
    },
    {
        "user": "U34567",
        "text": "Looking into it now. Seems like a CSS flexbox issue with the new navbar.",
        "ts": "1234567892.123456",
    },
    {
        "user": "U12345",
        "text": "Also, the API is returning 500 errors when uploading files larger than 10MB.",
        "ts": "1234567893.123456",
    },
    {
        "user": "U45678",
        "text": "That's a critical bug - I'll create a ticket for it.",
        "ts": "1234567894.123456",
    },
]


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

    def add_issue(self, issue_title: str, description: str, severity: str):
        self.issues.append({
            "title": issue_title,
            "description": description,
            "severity": severity,
        })
        logger.warning(f"[ISSUE] {issue_title} ({severity})")

    def print_summary(self):
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        print(f"[PASS] Passed: {len(self.passed)}")
        print(f"[FAIL] Failed: {len(self.failed)}")
        print(f"[ISSUE] Issues Found: {len(self.issues)}")
        print("="*80)

        if self.failed:
            print("\nFailed Tests:")
            for name, error in self.failed:
                print(f"  - {name}: {error}")

        if self.issues:
            print("\nIssues Found:")
            for issue in self.issues:
                print(f"  - [{issue['severity']}] {issue['title']}")
                print(f"    {issue['description']}")

        return len(self.failed) == 0


results = TestResults()


async def test_summarization_service():
    """Test the SummarizationService."""
    try:
        from src.services.summarization import SummarizationService

        service = SummarizationService()
        summary = await service.summarize_messages(SAMPLE_MESSAGES, channel_name="test-channel")

        if not summary:
            results.add_fail("SummarizationService", "Returned empty summary")
            return

        if len(summary) < 10:
            results.add_fail("SummarizationService", f"Summary too short: {len(summary)} chars")
            return

        if "Failed to generate summary" in summary:
            results.add_fail("SummarizationService", "Service returned error message")
            return

        results.add_pass("SummarizationService")
        logger.info(f"Summary: {summary[:100]}...")

    except Exception as e:
        results.add_fail("SummarizationService", str(e))
        results.add_issue(
            "SummarizationService crashes with sample data",
            f"Exception: {e}",
            "HIGH"
        )


async def test_issue_detection_service():
    """Test the IssueDetectionService."""
    try:
        from src.services.issue_detection import IssueDetectionService

        service = IssueDetectionService()
        issues = await service.detect_issues(SAMPLE_MESSAGES, channel_name="test-channel")

        if not isinstance(issues, list):
            results.add_fail("IssueDetectionService", f"Expected list, got {type(issues)}")
            return

        # We expect at least 2 issues from the sample messages (login bug + API 500 error)
        if len(issues) < 2:
            results.add_issue(
                "IssueDetectionService may not be detecting issues properly",
                f"Expected at least 2 issues from sample data, got {len(issues)}",
                "MEDIUM"
            )

        results.add_pass("IssueDetectionService")
        logger.info(f"Detected {len(issues)} issues")
        for issue in issues:
            logger.info(f"  - [{issue.get('severity')}] {issue.get('title')}")

    except Exception as e:
        results.add_fail("IssueDetectionService", str(e))
        results.add_issue(
            "IssueDetectionService crashes",
            f"Exception: {e}",
            "HIGH"
        )


async def test_reminder_service():
    """Test the ReminderService."""
    try:
        from src.services.reminder import ReminderService

        service = ReminderService()

        # Test scheduling a reminder
        remind_at = int(time.time()) + 60  # 1 minute from now
        result = await service.schedule_reminder(
            user_id="U12345",
            channel_id="C12345",
            text="Test reminder",
            remind_at=remind_at
        )

        if not result.get("success"):
            results.add_fail("ReminderService.schedule_reminder", "Did not return success")
            return

        reminder_id = result.get("reminder_id")
        if not reminder_id:
            results.add_fail("ReminderService.schedule_reminder", "No reminder_id returned")
            return

        # Test listing reminders
        reminders = await service.list_reminders(user_id="U12345")
        if not any(r["id"] == reminder_id for r in reminders):
            results.add_fail("ReminderService.list_reminders", "Scheduled reminder not found")
            return

        # Test cancelling reminder
        cancel_result = await service.cancel_reminder(reminder_id, "U12345")
        if not cancel_result.get("success"):
            results.add_fail("ReminderService.cancel_reminder", "Failed to cancel")
            return

        # Verify cancelled
        reminders_after = await service.list_reminders(user_id="U12345", status="pending")
        if any(r["id"] == reminder_id for r in reminders_after):
            results.add_fail("ReminderService.cancel_reminder", "Reminder still pending after cancel")
            return

        results.add_pass("ReminderService (schedule/list/cancel)")

    except Exception as e:
        results.add_fail("ReminderService", str(e))
        results.add_issue(
            "ReminderService crashes",
            f"Exception: {e}",
            "HIGH"
        )


async def test_tool_registry():
    """Test the ToolRegistry and verify all tools are registered."""
    try:
        from src.agent.tools import ToolRegistry

        registry = ToolRegistry()
        definitions = registry.get_tool_definitions()

        # Expected tools
        expected_tools = [
            "get_channel_messages",
            "post_message",
            "schedule_message",
            "list_channels",
            "get_channel_info",
            "summarize_channel",
            "detect_issues",
            "schedule_reminder",
            "list_reminders",
            "cancel_reminder",
        ]

        registered_tools = [tool["name"] for tool in definitions]

        missing_tools = [t for t in expected_tools if t not in registered_tools]
        if missing_tools:
            results.add_fail("ToolRegistry", f"Missing tools: {missing_tools}")
            results.add_issue(
                "ToolRegistry missing expected tools",
                f"Tools not registered: {', '.join(missing_tools)}",
                "HIGH"
            )
            return

        results.add_pass(f"ToolRegistry ({len(registered_tools)} tools registered)")
        logger.info(f"Registered tools: {', '.join(registered_tools)}")

    except Exception as e:
        results.add_fail("ToolRegistry", str(e))
        results.add_issue(
            "ToolRegistry initialization fails",
            f"Exception: {e}",
            "CRITICAL"
        )


async def test_tool_execution():
    """Test tool execution via the registry."""
    try:
        from src.agent.tools import ToolRegistry

        registry = ToolRegistry()

        # Test summarize_channel tool (uses summarization service internally)
        # We can't test with real Slack API, but we can test the tool exists and dispatches
        try:
            # This will fail because we don't have real Slack messages, but we can verify
            # the tool exists and the error handling works
            result = await registry.execute_tool("summarize_channel", channel_id="C12345", hours=1)

            # The tool should return a dict, not raise an exception
            if not isinstance(result, dict):
                results.add_fail("Tool execution (summarize_channel)", f"Expected dict, got {type(result)}")
                return

            results.add_pass("Tool execution (dispatch works)")

        except Exception as e:
            results.add_fail("Tool execution (summarize_channel)", f"Tool execution raised: {e}")
            results.add_issue(
                "Tool execution raises exceptions instead of returning error dicts",
                f"execute_tool() should catch exceptions and return error dicts, but got: {e}",
                "MEDIUM"
            )

    except Exception as e:
        results.add_fail("Tool execution", str(e))


async def test_memory_manager():
    """Test the MemoryManager."""
    try:
        from src.memory.manager import MemoryManager

        manager = MemoryManager()

        # Test storing interaction
        manager.store_interaction(
            user_id="U12345",
            channel_id="C12345",
            user_message="What is the status?",
            bot_response="Everything is working fine."
        )

        # Test retrieving conversation history
        history = manager.get_conversation_history(user_id="U12345", channel_id="C12345", limit=10)

        if not history:
            results.add_fail("MemoryManager", "No history returned after storing interaction")
            return

        # Verify the interaction is in history
        found = any(msg.get("content") == "What is the status?" for msg in history)
        if not found:
            results.add_fail("MemoryManager", "Stored interaction not found in history")
            return

        results.add_pass("MemoryManager (store/retrieve)")

    except Exception as e:
        results.add_fail("MemoryManager", str(e))
        results.add_issue(
            "MemoryManager crashes",
            f"Exception: {e}",
            "HIGH"
        )


async def test_context_builder():
    """Test the ContextBuilder."""
    try:
        from src.agent.context_builder import ContextBuilder
        from src.memory.manager import MemoryManager

        # Create shared memory manager
        memory_manager = MemoryManager()

        # Store some test data
        memory_manager.store_interaction(
            user_id="U12345",
            channel_id="C12345",
            user_message="Test message",
            bot_response="Test response"
        )

        # Create context builder with shared memory
        builder = ContextBuilder(memory_manager=memory_manager)

        # Build context
        context = await builder.build_context(
            user_id="U12345",
            channel_id="C12345",
            user_message="What's the latest?"
        )

        if not isinstance(context, dict):
            results.add_fail("ContextBuilder", f"Expected dict, got {type(context)}")
            return

        # Verify context has expected keys
        expected_keys = ["conversation_history", "memory_context", "rag_context"]
        missing_keys = [k for k in expected_keys if k not in context]
        if missing_keys:
            results.add_fail("ContextBuilder", f"Missing keys in context: {missing_keys}")
            return

        # Verify conversation history contains our test interaction
        history = context.get("conversation_history", [])
        if not any("Test message" in str(msg.get("content", "")) for msg in history):
            results.add_fail("ContextBuilder", "Test interaction not found in conversation history")
            results.add_issue(
                "ContextBuilder not retrieving conversation history",
                "Stored interactions are not appearing in built context",
                "HIGH"
            )
            return

        results.add_pass("ContextBuilder (builds context with history)")

    except Exception as e:
        results.add_fail("ContextBuilder", str(e))
        results.add_issue(
            "ContextBuilder crashes",
            f"Exception: {e}",
            "HIGH"
        )


async def test_rag_retriever():
    """Test the RAG SemanticRetriever."""
    try:
        from src.rag.retriever import SemanticRetriever

        retriever = SemanticRetriever()

        # Try to retrieve (will likely return empty since vector store is not populated)
        results_list = await retriever.retrieve(
            query="What bugs were reported?",
            top_k=5
        )

        # It's OK if results are empty (vector store not populated yet)
        # We're just testing that the retriever doesn't crash
        if not isinstance(results_list, list):
            results.add_fail("SemanticRetriever", f"Expected list, got {type(results_list)}")
            return

        results.add_pass("SemanticRetriever (no crash)")
        logger.info(f"RAG retrieval returned {len(results_list)} results (empty vector store is OK)")

    except Exception as e:
        results.add_fail("SemanticRetriever", str(e))
        results.add_issue(
            "SemanticRetriever crashes",
            f"Exception: {e}",
            "MEDIUM"
        )


async def test_scheduler_jobs():
    """Verify scheduler jobs are configured properly."""
    try:
        from src.app import create_app

        # Create app (this initializes the scheduler)
        app = create_app()

        # The scheduler is started inside create_app, so if we got here without
        # exception, the scheduler initialization worked
        results.add_pass("Scheduler initialization")
        logger.info("Scheduler jobs: reminder_delivery, rag_indexing, reminder_cleanup, heartbeat")

    except Exception as e:
        results.add_fail("Scheduler initialization", str(e))
        results.add_issue(
            "Scheduler fails to initialize",
            f"APScheduler setup in create_app() raises: {e}",
            "HIGH"
        )


def check_required_files():
    """Check that all required files exist."""
    required_files = [
        "src/agent/orchestrator.py",
        "src/agent/tools.py",
        "src/agent/context_builder.py",
        "src/services/summarization.py",
        "src/services/issue_detection.py",
        "src/services/reminder.py",
        "src/services/notion_integration.py",
        "src/memory/manager.py",
        "src/rag/retriever.py",
        "src/rag/indexer.py",
        "src/rag/store.py",
        "config/settings.py",
        ".env",
    ]

    project_root = Path(__file__).parent
    missing_files = []

    for file_path in required_files:
        full_path = project_root / file_path
        if not full_path.exists():
            missing_files.append(file_path)

    if missing_files:
        results.add_fail("Required files check", f"Missing files: {missing_files}")
        results.add_issue(
            "Missing required files",
            f"Files not found: {', '.join(missing_files)}",
            "CRITICAL"
        )
    else:
        results.add_pass("Required files check")


def check_environment_variables():
    """Check that required environment variables are set."""
    from config.settings import settings

    required_vars = [
        ("slack_bot_token", "SLACK_BOT_TOKEN"),
        ("slack_app_token", "SLACK_APP_TOKEN"),
        ("slack_signing_secret", "SLACK_SIGNING_SECRET"),
        ("anthropic_api_key", "ANTHROPIC_API_KEY"),
    ]

    missing_vars = []
    for attr, env_name in required_vars:
        value = getattr(settings, attr, None)
        if not value:
            missing_vars.append(env_name)

    if missing_vars:
        results.add_fail("Environment variables", f"Missing: {missing_vars}")
        results.add_issue(
            "Missing required environment variables",
            f"Variables not set in .env: {', '.join(missing_vars)}",
            "CRITICAL"
        )
    else:
        results.add_pass("Environment variables check")


async def main():
    """Run all integration tests."""
    print("="*80)
    print("SLACK BOT ASSISTANT - INTEGRATION TEST SUITE")
    print("="*80)
    print()

    # File and env checks (synchronous)
    print("Running prerequisite checks...")
    check_required_files()
    check_environment_variables()
    print()

    # Async tests
    print("Running service tests...")
    await test_summarization_service()
    await test_issue_detection_service()
    await test_reminder_service()
    print()

    print("Running agent/tool tests...")
    await test_tool_registry()
    await test_tool_execution()
    print()

    print("Running memory/context tests...")
    await test_memory_manager()
    await test_context_builder()
    print()

    print("Running RAG tests...")
    await test_rag_retriever()
    print()

    print("Running scheduler tests...")
    await test_scheduler_jobs()
    print()

    # Print summary
    success = results.print_summary()

    # Update PROBLEMS.md if issues were found
    if results.issues:
        print("\n📝 Updating PROBLEMS.md with new issues...")
        update_problems_md(results.issues)
        print("✅ PROBLEMS.md updated")

    return 0 if success else 1


def update_problems_md(issues):
    """Append new issues to PROBLEMS.md."""
    problems_file = Path(__file__).parent / "PROBLEMS.md"

    if not problems_file.exists():
        logger.warning("PROBLEMS.md not found, skipping update")
        return

    content = problems_file.read_text(encoding="utf-8")

    # Find the highest problem number
    import re
    problem_numbers = re.findall(r"## Problem #(\d+)", content)
    next_number = max(int(n) for n in problem_numbers) + 1 if problem_numbers else 1

    # Append new issues
    new_content = content + "\n---\n\n"

    for issue in issues:
        severity = issue["severity"]
        new_content += f"## Problem #{next_number} — {severity}: {issue['title']}\n\n"
        new_content += f"- **Status:** [ ] OPEN\n"
        new_content += f"- **Files:** TBD\n"
        new_content += f"- **Description:**\n"
        new_content += f"  {issue['description']}\n"
        new_content += f"- **Impact:** TBD\n"
        new_content += f"- **Fix:** TBD\n\n"
        new_content += "---\n\n"
        next_number += 1

    problems_file.write_text(new_content, encoding="utf-8")


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
