# Claude Code Learning Materials

## Overview

This directory contains distilled knowledge, patterns, and best practices learned from building the Slack Bot Assistant project. Use these materials as reference for future projects.

**Project Context:** Slack Bot with AI agent (Claude), background jobs (APScheduler), and multiple integrations (GitHub, Notion, RAG).

**Key Achievement:** Fixed 13 critical issues found during integration testing, all tests now passing (11/11).

---

## Directory Structure

```
.claude/
├── agents/           # Reusable agent workflows
├── skills/           # Step-by-step task guides
├── patterns/         # Design patterns and architectures
├── rules/            # Critical development rules
└── README.md         # This file
```

---

## Agents

Reusable workflows for complex, multi-step tasks.

### [integration-tester.md](agents/integration-tester.md)
**Purpose:** Create comprehensive integration test suites for async Python services

**When to use:**
- After implementing core functionality
- Before production deployment
- When adding new services/tools

**What it does:**
- Generates realistic sample data
- Tests all services with real API calls
- Auto-documents issues in PROBLEMS.md
- Verifies integration points work correctly

**Key learning:** Found Problem #13 (MCP function imports) during integration testing

---

### [bug-hunter.md](agents/bug-hunter.md)
**Purpose:** Systematically discover and document bugs in complex systems

**When to use:**
- User reports "not working properly"
- After major refactors
- Before release

**What it does:**
- Traces execution paths
- Identifies integration issues
- Documents in standardized format
- Prioritizes by severity

**Key patterns discovered:**
1. MCP function import anti-pattern
2. Separate instance anti-pattern
3. Missing scheduler jobs
4. Bypassed service layers
5. Missing tool registrations

---

## Skills

Step-by-step guides for specific tasks.

### [add-agent-tool.md](skills/add-agent-tool.md)
**Purpose:** Add a new tool to the agent's ToolRegistry

**Steps covered:**
1. Implement tool method
2. Register in ToolRegistry
3. Define JSON schema
4. Handle errors correctly
5. Test execution

**Example:** Adding `summarize_channel` tool (Problem #9 fix)

---

### [add-scheduler-job.md](skills/add-scheduler-job.md)
**Purpose:** Add periodic background jobs with APScheduler

**Steps covered:**
1. Import APScheduler
2. Create scheduler instance
3. Define job function (with error handling)
4. Schedule job (interval or cron)
5. Start scheduler
6. Verify in logs

**Examples:**
- Reminder delivery (60s interval)
- RAG indexing (2h interval)
- Cleanup (weekly cron)
- Heartbeat (5min interval)

**Key rules:**
- Wrap all job logic in try/except
- Never let exceptions crash scheduler
- Log job completion/failure
- Make scheduler start non-fatal

---

### [debug-agent-tools.md](skills/debug-agent-tools.md)
**Purpose:** Systematically debug agent tools when they don't work

**7-step debugging process:**
1. Verify tool registration
2. Verify tool schema
3. Test direct tool execution
4. Check function implementation
5. Verify return format (dict, not exception)
6. Test in agent context
7. Check API tokens and permissions

**Real example:** Debugging Problem #13 (MCP function imports)

---

## Patterns

Architectural patterns and design solutions.

### [shared-state-management.md](patterns/shared-state-management.md)
**Purpose:** Properly share stateful components across system

**Problem solved:** Problem #5 - Separate MemoryManager instances broke conversation history

**Pattern:**
- Create shared instance in parent
- Pass to dependencies via dependency injection
- Avoid multiple instances of stateful components

**Before/After code examples included**

**Applies to:**
- MemoryManager
- Database connections
- Redis clients
- Vector stores
- Background schedulers

---

### [error-handling-strategy.md](patterns/error-handling-strategy.md)
**Purpose:** Layered error handling for robust agent systems

**4 Layers:**
1. **Tools** - Return error dicts, never raise
2. **Services** - Can raise exceptions, caller handles
3. **Listeners** - Always ack(), always respond to user
4. **Scheduled Jobs** - Catch all exceptions, log, don't crash

**Key rule:** Tools return `{"success": False, "error": "..."}`, never raise exceptions

**Complete flow examples included**

---

### [testing-async-services.md](patterns/testing-async-services.md)
**Purpose:** Comprehensive testing strategy for async Python services

**10 Patterns:**
1. Sample data generation
2. Async test functions
3. Real API calls in integration tests
4. Test error handling
5. Test tool execution
6. Test stateful components
7. Test background jobs
8. Test conditional registration
9. Defensive assertions
10. Auto-update documentation

**Real example:** test_integration.py that found Problem #13

---

## Rules

Critical rules learned the hard way.

### [slack-bot-development.md](rules/slack-bot-development.md)
**Purpose:** 10 critical rules for Slack bot development

**Rules:**
1. Never import FastMCP-decorated functions directly
2. Share stateful instances via dependency injection
3. Always configure scheduler jobs for periodic tasks
4. Slash commands should use services, not duplicate logic
5. Tools must return dicts, never raise exceptions
6. Register all tools in ToolRegistry
7. Validate environment variables at startup
8. Log scheduler job status on startup
9. Use conditional tool registration for optional integrations
10. Implement cleanup jobs for growing data stores

**Each rule includes:**
- Wrong way (with code)
- Right way (with code)
- Why it matters
- What happens if you break it

---

### [fastmcp-integration.md](rules/fastmcp-integration.md)
**Purpose:** Understand FastMCP decorator behavior and avoid Problem #13

**Critical discovery:** `@mcp.tool()` wraps functions in FunctionTool objects (not callable)

**5 Rules:**
1. Never import MCP-decorated functions for internal use
2. Use underlying SDK directly in agent tools
3. MCP servers are for external MCP clients only
4. Share logic via utility modules
5. Understand decorator transformations

**Includes:**
- How @mcp.tool() transforms functions
- Why direct imports fail
- Complete before/after fix for Problem #13
- Decision tree for when to use MCP

---

## How to Use This Knowledge Base

### For New Features

1. Check [skills/](skills/) for step-by-step guides
   - Adding a tool? → [add-agent-tool.md](skills/add-agent-tool.md)
   - Adding a job? → [add-scheduler-job.md](skills/add-scheduler-job.md)

2. Follow [rules/](rules/) to avoid common mistakes
   - Review [slack-bot-development.md](rules/slack-bot-development.md)
   - If using MCP → [fastmcp-integration.md](rules/fastmcp-integration.md)

3. Apply [patterns/](patterns/) for architecture decisions
   - Need shared state? → [shared-state-management.md](patterns/shared-state-management.md)
   - Error handling? → [error-handling-strategy.md](patterns/error-handling-strategy.md)

### For Testing

1. Use [agents/integration-tester.md](agents/integration-tester.md) to create test suite
2. Follow [patterns/testing-async-services.md](patterns/testing-async-services.md)
3. If tests fail, use [skills/debug-agent-tools.md](skills/debug-agent-tools.md)

### For Debugging

1. Use [agents/bug-hunter.md](agents/bug-hunter.md) for systematic investigation
2. Check [rules/](rules/) for known anti-patterns
3. Use [skills/debug-agent-tools.md](skills/debug-agent-tools.md) for tool issues

---

## Key Learnings from This Project

### Most Critical Issues Fixed

**Problem #13: MCP Function Imports**
- **Impact:** ALL agent Slack tools completely broken
- **Root cause:** Importing @mcp.tool() decorated functions
- **Fix:** Rewrote 8 tools to use Slack SDK directly
- **Learning:** [rules/fastmcp-integration.md](rules/fastmcp-integration.md)

**Problem #5: Separate MemoryManager Instances**
- **Impact:** Bot had ZERO conversation memory
- **Root cause:** Orchestrator and ContextBuilder created separate instances
- **Fix:** Shared single instance via dependency injection
- **Learning:** [patterns/shared-state-management.md](patterns/shared-state-management.md)

**Problem #7: No Reminder Scheduler**
- **Impact:** Agent-created reminders never delivered
- **Root cause:** ReminderService.execute_due_reminders() never called
- **Fix:** Added APScheduler with 60-second interval job
- **Learning:** [skills/add-scheduler-job.md](skills/add-scheduler-job.md)

### Most Valuable Patterns

1. **Error Handling Strategy** - Layered approach (tools → services → listeners → jobs)
2. **Shared State Management** - Dependency injection for stateful components
3. **Integration Testing** - Test with real APIs, realistic data, flexible assertions

### Most Important Rules

1. **Never import MCP-decorated functions** (Problem #13)
2. **Share stateful instances** (Problem #5)
3. **Always configure schedulers** (Problems #7, #10)
4. **Tools return dicts, never raise** (All tools)
5. **Services use service layer** (Problem #1)

---

## Statistics

**Problems Found:** 13
**Problems Resolved:** 13 ✅
**Test Coverage:** 11/11 passing ✅
**Documentation Files:** 10
**Code Files Modified:** 7

**Time Saved Next Time:** Significant - all patterns documented and reusable

---

## Next Steps for Future Projects

When starting a new Slack bot or AI agent project:

1. **Planning Phase:**
   - Review [rules/slack-bot-development.md](rules/slack-bot-development.md)
   - Plan architecture using [patterns/](patterns/)
   - Decide on error handling strategy early

2. **Implementation Phase:**
   - Follow [skills/](skills/) for each task
   - Use [rules/fastmcp-integration.md](rules/fastmcp-integration.md) if using MCP
   - Implement error handling per [patterns/error-handling-strategy.md](patterns/error-handling-strategy.md)

3. **Testing Phase:**
   - Use [agents/integration-tester.md](agents/integration-tester.md)
   - Follow [patterns/testing-async-services.md](patterns/testing-async-services.md)
   - Test early and often

4. **Debugging Phase:**
   - Use [agents/bug-hunter.md](agents/bug-hunter.md)
   - Check [skills/debug-agent-tools.md](skills/debug-agent-tools.md)
   - Document new issues in PROBLEMS.md

---

## Contributing to This Knowledge Base

When you discover new patterns or encounter new issues:

1. **For new workflows:** Add to [agents/](agents/)
2. **For step-by-step tasks:** Add to [skills/](skills/)
3. **For architectural patterns:** Add to [patterns/](patterns/)
4. **For critical rules:** Add to [rules/](rules/)

Keep the same format:
- Clear purpose statement
- When to use
- Step-by-step instructions or examples
- Before/After code examples
- Real-world examples from this project

---

**Last Updated:** 2026-02-17
**Project:** Slack Bot Assistant
**Status:** All 13 problems resolved, all tests passing ✅
