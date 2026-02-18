Systematically trace execution paths, identify root causes of bugs, and document all issues with severity levels.

## When to Use
- When features aren't working as expected
- After major refactors
- Before deployment to catch hidden issues
- When tests are failing

## Methodology

### Phase 1: Discovery — List All Functionalities
1. Read the entire codebase structure (use Explore agent)
2. List all claimed functionalities from docs/README
3. Create a comprehensive inventory of features to test

### Phase 2: Deep Inspection — Read Everything
Read:
- Service layer implementations
- Tool registry and tool methods
- MCP server integrations (if any)
- Agent orchestrator
- Memory management
- Scheduler configuration
- All dependencies and imports

### Phase 3: Trace Execution Paths
For each functionality:
1. Identify entry point (slash command, agent tool, API endpoint)
2. Trace through all called methods
3. Check for:
   - Missing implementations (stubs with `pass` or `...`)
   - Broken imports (especially MCP-decorated function imports)
   - Incorrect parameter names (caller uses `agent_response` but method expects `bot_response`)
   - Missing error handling
   - Circular dependencies

### Phase 4: Create PROBLEMS.md

Use this template for each issue found:

```markdown
## Problem #X — SEVERITY: Short Title

- **Status:** [ ] OPEN
- **Files:** `path/to/file.py:line`
- **Description:**
  Detailed explanation of what's broken
- **Impact:** What fails as a result
- **Fix:** How to resolve it
```

Severity levels:
- **CRITICAL**: System completely broken, no workaround
- **HIGH**: Major feature broken, impacts core functionality
- **MEDIUM**: Feature partially broken, workaround exists
- **LOW**: Minor issue, cosmetic, or nice-to-have

## Critical Bug Patterns to Look For

### Pattern 1: Importing MCP-Decorated Functions
**Symptom:** `'FunctionTool' object is not callable`

```python
# WRONG - Importing FastMCP-decorated function
from src.mcp_servers.slack_server import get_channel_messages
result = await get_channel_messages(channel_id, hours)  # Fails!

# RIGHT - Use Slack SDK directly
slack_client = AsyncWebClient(token=settings.slack_bot_token)
response = await slack_client.conversations_history(channel=channel_id, limit=200)
```

**Lesson:** Never import functions decorated by external frameworks. Use the underlying SDK directly.

---

### Pattern 2: Separate Instances of Stateful Components
**Symptom:** Data stored in one component doesn't appear in another

```python
# WRONG - Two separate MemoryManager instances
class Orchestrator:
    def __init__(self):
        self.memory = MemoryManager()  # Instance 1
        self.context = ContextBuilder()  # Creates Instance 2 internally!

# RIGHT - Share single instance
class Orchestrator:
    def __init__(self):
        self.memory = MemoryManager()
        self.context = ContextBuilder(memory_manager=self.memory)  # Shared!
```

**Lesson:** Stateful components must be shared as singletons or dependency-injected.

---

### Pattern 3: Missing Tool Registrations
**Symptom:** Agent says "I don't have a tool to do that"

```python
# Service exists and works
class SummarizationService:
    async def summarize_messages(self, messages, channel): ...

# But NO TOOL registered for the agent to call it!
# Fix: In ToolRegistry.__init__:
self.tools["summarize_channel"] = self._summarize_channel
self._definitions.append({"name": "summarize_channel", "description": "...", ...})
```

**Lesson:** Services alone aren't enough. Agent needs registered tools to invoke them.

---

### Pattern 4: Missing Periodic Jobs
**Symptom:** Code exists but never runs (reminders never delivered, RAG never indexed)

```python
# Method implemented
class ReminderService:
    async def execute_due_reminders(self): ...

# But NO SCHEDULER configured to call it!
# Fix: In app.py
scheduler = AsyncIOScheduler()
scheduler.add_job(_deliver_reminders, "interval", seconds=60)
scheduler.start()
```

**Lesson:** Periodic functionality needs explicit scheduler configuration.

---

### Pattern 5: Parameter Name Mismatches
**Symptom:** `TypeError: unexpected keyword argument 'X'. Did you mean 'Y'?`

```python
# Method signature
def store_interaction(self, user_id, channel_id, user_message, bot_response): ...

# Caller uses wrong name
store_interaction(user_id="U123", channel_id="C123", user_message="Hello",
                  agent_response="Hi")  # WRONG! Should be bot_response
```

**Lesson:** Read method signatures carefully. Python won't auto-map similar names.

## Investigation Checklists

### For "Feature Not Working" Issues
- [ ] Does the service/method exist?
- [ ] Is there a tool registered in ToolRegistry?
- [ ] Does the tool dispatch to the service correctly?
- [ ] Are all imports working (no MCP-decorated functions)?
- [ ] Are parameters named correctly?
- [ ] Is error handling present?

### For "Periodic Job Not Running" Issues
- [ ] Does the method exist?
- [ ] Is APScheduler installed?
- [ ] Is the scheduler created in app.py?
- [ ] Is the job added with correct interval?
- [ ] Is `scheduler.start()` called?
- [ ] Are there logs showing the job runs?

### For "Data Not Persisting" Issues
- [ ] Are multiple instances being created?
- [ ] Is the shared instance pattern used?
- [ ] Are file paths correct and writable?
- [ ] Is there error handling for file I/O?

## Output: PROBLEMS.md

End result: complete issue tracker with:
1. All issues numbered sequentially
2. Severity in title for quick scanning
3. Exact file locations (`src/path/file.py:123`)
4. Clear before/after explanations
5. Status tracking (OPEN/RESOLVED)

## Success Metrics
- All features tested end-to-end
- All broken features documented with root cause
- Fixes applied and verified
- Zero critical issues remaining
