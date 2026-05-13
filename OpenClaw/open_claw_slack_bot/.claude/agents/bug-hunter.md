# Bug Hunter Agent

## Purpose
Systematically trace execution paths, identify root causes of bugs, and document all issues with severity levels.

## When to Use
- When features aren't working as expected
- When tests are failing
- When integration points break
- Before deployment to catch hidden issues

## Methodology

### Phase 1: Discovery — List All Functionalities
```markdown
## Approach
1. Read the entire codebase structure (use Explore agent)
2. List all claimed functionalities from docs/README
3. Create a comprehensive inventory of features
```

### Phase 2: Deep Inspection — Read Everything
```markdown
## What to Read
- Service layer implementations
- Tool registry and tool methods
- MCP server integrations
- Agent orchestrator
- Memory management
- Scheduler configuration
- All dependencies and imports
```

### Phase 3: Trace Execution Paths
```markdown
## For Each Functionality
1. Identify entry point (slash command, agent tool, etc.)
2. Trace through all called methods
3. Check for:
   - Missing implementations (stubs)
   - Broken imports
   - Incorrect parameter names
   - Missing error handling
   - Circular dependencies
```

### Phase 4: Create PROBLEMS.md
```markdown
## Problem Documentation Template

## Problem #X — SEVERITY: Title

- **Status:** [ ] OPEN
- **Files:** `path/to/file.py:line`
- **Description:**
  Detailed explanation of what's broken
- **Impact:** What fails as a result
- **Fix:** How to resolve it
```

## Critical Bug Patterns Found

### Pattern 1: Importing MCP-Decorated Functions
**Symptom:** `'FunctionTool' object is not callable`

**Root Cause:**
```python
# ❌ WRONG - Importing FastMCP-decorated function
from src.mcp_servers.slack_server import get_channel_messages
result = await get_channel_messages(channel_id, hours)
# Fails because @mcp.tool() wraps the function
```

**Fix:**
```python
# ✅ CORRECT - Use Slack SDK directly
from slack_sdk.web.async_client import AsyncWebClient
from config.settings import settings

slack_client = AsyncWebClient(token=settings.slack_bot_token)
response = await slack_client.conversations_history(
    channel=channel_id,
    oldest=str(oldest),
    limit=200
)
```

**Lesson:** Never import functions decorated by external frameworks. Use the underlying SDK directly.

---

### Pattern 2: Separate Instances of Stateful Components
**Symptom:** Data stored in one component doesn't appear in another

**Root Cause:**
```python
# Component A
class Orchestrator:
    def __init__(self):
        self.memory = MemoryManager()  # Instance 1

# Component B
class ContextBuilder:
    def __init__(self):
        self.memory = MemoryManager()  # Instance 2 (separate!)
```

**Fix:**
```python
# Share single instance
class Orchestrator:
    def __init__(self):
        self.memory = MemoryManager()
        self.context = ContextBuilder(memory_manager=self.memory)

class ContextBuilder:
    def __init__(self, memory_manager: MemoryManager = None):
        self.memory = memory_manager or MemoryManager()
```

**Lesson:** Stateful components must be shared as singletons or dependency-injected.

---

### Pattern 3: Missing Tool Registrations
**Symptom:** Agent says "I don't have a tool to do that"

**Root Cause:**
```python
# Service exists and works
class SummarizationService:
    async def summarize_messages(self, messages, channel): ...

# But NO TOOL registered for the agent to call it
```

**Fix:**
```python
# In ToolRegistry.__init__:
self.tools["summarize_channel"] = self._summarize_channel
self._definitions.append({
    "name": "summarize_channel",
    "description": "Summarize recent messages from a channel",
    "input_schema": {...},
})

# Implement the tool method:
async def _summarize_channel(self, channel_id, hours=24):
    # Fetch messages + call service
    ...
```

**Lesson:** Services alone aren't enough. Agent needs registered tools to invoke them.

---

### Pattern 4: Missing Periodic Jobs
**Symptom:** Code exists but never runs

**Root Cause:**
```python
# Method implemented
class ReminderService:
    async def execute_due_reminders(self): ...

# But NO SCHEDULER configured to call it
```

**Fix:**
```python
# In app.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()
reminder_service = ReminderService()

async def _deliver_reminders():
    results = await reminder_service.execute_due_reminders()

scheduler.add_job(_deliver_reminders, "interval", seconds=60)
scheduler.start()
```

**Lesson:** Periodic functionality needs explicit scheduler configuration.

---

### Pattern 5: Parameter Name Mismatches
**Symptom:** `TypeError: unexpected keyword argument 'X'. Did you mean 'Y'?`

**Root Cause:**
```python
# Method signature
def store_interaction(self, user_id, channel_id, user_message, bot_response):
    ...

# Caller uses wrong parameter name
store_interaction(
    user_id="U123",
    channel_id="C123",
    user_message="Hello",
    agent_response="Hi"  # ❌ Wrong! Should be bot_response
)
```

**Fix:**
```python
# Match the exact parameter name
store_interaction(
    user_id="U123",
    channel_id="C123",
    user_message="Hello",
    bot_response="Hi"  # ✅ Correct
)
```

**Lesson:** Read method signatures carefully. Python won't auto-map similar names.

## Investigation Checklist

### For "Feature Not Working" Issues

- [ ] Does the service/method exist?
- [ ] Is there a tool registered in ToolRegistry?
- [ ] Does the tool dispatch to the service correctly?
- [ ] Are all imports working (no MCP-decorated functions)?
- [ ] Are parameters named correctly?
- [ ] Is error handling present?
- [ ] Are there logs to trace execution?

### For "Periodic Job Not Running" Issues

- [ ] Does the method exist?
- [ ] Is APScheduler installed?
- [ ] Is the scheduler created in app.py?
- [ ] Is the job added with correct interval?
- [ ] Is scheduler.start() called?
- [ ] Are there logs showing the job runs?

### For "Data Not Persisting" Issues

- [ ] Are multiple instances being created?
- [ ] Is the shared instance pattern used?
- [ ] Are file paths correct and writable?
- [ ] Is there error handling for file I/O?
- [ ] Are files actually being written (check filesystem)?

## Documentation Best Practices

### Severity Levels
- **CRITICAL**: System completely broken, no workaround
- **HIGH**: Major feature broken, impacts core functionality
- **MEDIUM**: Feature partially broken, workaround exists
- **LOW**: Minor issue, cosmetic, or nice-to-have

### Problem Format
```markdown
## Problem #X — SEVERITY: Short Title

- **Status:** [x] RESOLVED / [ ] OPEN
- **Files:** `src/path/file.py:123`
- **Description:**
  [What's broken, with bullet points for multi-part issues]
- **Impact:** [What fails as a result]
- **Fix:** [How it was resolved or how to resolve]
```

## Output: Comprehensive PROBLEMS.md

The end result should be a complete issue tracker with:
1. All issues numbered sequentially
2. Severity in title for quick scanning
3. Exact file locations
4. Clear before/after explanations
5. Status tracking (OPEN/RESOLVED)

## Success Metrics
- All features tested end-to-end
- All broken features documented
- Root causes identified
- Fixes applied and verified
- Zero critical issues remaining
