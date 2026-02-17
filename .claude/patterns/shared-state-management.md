# Pattern: Shared State Management

## Problem: Separate Instances Break State Synchronization

### The Discovery: Problem #5

**Symptom:** Bot had ZERO conversation memory
**Root Cause:** Orchestrator and ContextBuilder created separate MemoryManager instances
**Impact:** Users had to repeat themselves every message

---

## Anti-Pattern: Multiple Instances of Stateful Components

### What Was Wrong

```python
# src/agent/orchestrator.py
class Orchestrator:
    def __init__(self):
        self.semantic_retriever = SemanticRetriever()
        self.tool_registry = ToolRegistry()

        # WRONG: ContextBuilder creates its own MemoryManager
        self.context_builder = ContextBuilder()

        # WRONG: Orchestrator creates another MemoryManager
        self.memory_manager = MemoryManager()
```

```python
# src/agent/context_builder.py
class ContextBuilder:
    def __init__(self):
        # WRONG: Creates its own instance
        self.memory_manager = MemoryManager()
```

**The Problem:**
```
Orchestrator.memory_manager (Instance A)
   └─ store_interaction("user", "hello")
   └─ store_interaction("bot", "hi there")

ContextBuilder.memory_manager (Instance B)
   └─ get_conversation_history() → [] (empty!)
```

**Result:** Two separate in-memory stores that don't talk to each other.

---

## The Pattern: Dependency Injection for Shared State

### Step 1: Identify Stateful Components

**Stateful = Has mutable data that must be shared:**
- MemoryManager (conversation history)
- Database connections (SQLAlchemy sessions)
- Redis clients (cache, rate limiting)
- Vector store clients (ChromaDB, Pinecone)
- Background job schedulers (APScheduler)

**Stateless = Can have multiple instances:**
- Services (SummarizationService, IssueDetectionService)
- Pure functions
- Utilities

---

### Step 2: Create Once, Share Everywhere

```python
# src/agent/orchestrator.py
class Orchestrator:
    def __init__(self):
        # Create stateful components FIRST
        self.memory_manager = MemoryManager()  # Single instance

        # Pass to dependencies via constructor
        self.context_builder = ContextBuilder(
            memory_manager=self.memory_manager  # Share it!
        )

        # Stateless components can be created normally
        self.semantic_retriever = SemanticRetriever()
        self.tool_registry = ToolRegistry()
```

```python
# src/agent/context_builder.py
class ContextBuilder:
    def __init__(self, memory_manager: MemoryManager = None):
        # Accept shared instance, or create default
        self.memory_manager = memory_manager or MemoryManager()

    async def build_context(self, conversation_id: str, user_message: str) -> dict:
        # Now uses THE SAME MemoryManager as Orchestrator
        history = self.memory_manager.get_conversation_history(conversation_id)

        return {
            "conversation_history": history,
            "user_message": user_message,
            # ...
        }
```

---

### Step 3: Verify Shared State Works

```python
# In orchestrator.py
async def chat(self, conversation_id: str, user_message: str) -> str:
    # Store user message
    self.memory_manager.store_interaction(
        conversation_id=conversation_id,
        role="user",
        content=user_message
    )

    # Build context (uses SAME MemoryManager)
    context = await self.context_builder.build_context(
        conversation_id=conversation_id,
        user_message=user_message
    )

    # context["conversation_history"] now includes user_message! ✅
```

---

## Complete Before/After Example

### Before (Broken)

```python
# orchestrator.py
class Orchestrator:
    def __init__(self):
        self.context_builder = ContextBuilder()  # Instance B
        self.memory_manager = MemoryManager()     # Instance A

    async def chat(self, conv_id: str, message: str) -> str:
        # Store in Instance A
        self.memory_manager.store_interaction(conv_id, "user", message)

        # Retrieve from Instance B (empty!)
        context = await self.context_builder.build_context(conv_id, message)
        # context["conversation_history"] = [] ❌
```

```python
# context_builder.py
class ContextBuilder:
    def __init__(self):
        self.memory_manager = MemoryManager()  # Instance B

    async def build_context(self, conv_id: str, message: str):
        # Retrieves from Instance B (never written to!)
        history = self.memory_manager.get_conversation_history(conv_id)
        return {"conversation_history": history}  # Always empty ❌
```

**Flow:**
```
User: "What's the weather?"
  → Stored in Instance A
  → ContextBuilder retrieves from Instance B (empty)
  → Agent has no memory ❌

User: "And tomorrow?"
  → Stored in Instance A
  → ContextBuilder retrieves from Instance B (empty)
  → Agent doesn't know "what" refers to ❌
```

---

### After (Fixed)

```python
# orchestrator.py
class Orchestrator:
    def __init__(self):
        # Create shared instance FIRST
        self.memory_manager = MemoryManager()  # Single instance

        # Pass to ContextBuilder
        self.context_builder = ContextBuilder(
            memory_manager=self.memory_manager  # Share it
        )

    async def chat(self, conv_id: str, message: str) -> str:
        # Store in shared instance
        self.memory_manager.store_interaction(conv_id, "user", message)

        # Retrieve from SAME instance
        context = await self.context_builder.build_context(conv_id, message)
        # context["conversation_history"] = [{user: "What's the weather?"}] ✅
```

```python
# context_builder.py
class ContextBuilder:
    def __init__(self, memory_manager: MemoryManager = None):
        # Use shared instance if provided
        self.memory_manager = memory_manager or MemoryManager()

    async def build_context(self, conv_id: str, message: str):
        # Retrieves from shared instance
        history = self.memory_manager.get_conversation_history(conv_id)
        return {"conversation_history": history}  # Has data! ✅
```

**Flow:**
```
User: "What's the weather?"
  → Stored in shared instance
  → ContextBuilder retrieves from shared instance
  → Agent sees: [{user: "What's the weather?"}] ✅

User: "And tomorrow?"
  → Stored in shared instance
  → ContextBuilder retrieves from shared instance
  → Agent sees: [
      {user: "What's the weather?"},
      {bot: "It's sunny"},
      {user: "And tomorrow?"}
    ] ✅
  → Agent understands context!
```

---

## Pattern Variations

### Variation 1: Factory Function

```python
# src/factories.py
_memory_manager = None

def get_memory_manager() -> MemoryManager:
    """Singleton factory for MemoryManager."""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager
```

```python
# In orchestrator.py
from src.factories import get_memory_manager

class Orchestrator:
    def __init__(self):
        self.memory_manager = get_memory_manager()  # Singleton
```

```python
# In context_builder.py
from src.factories import get_memory_manager

class ContextBuilder:
    def __init__(self):
        self.memory_manager = get_memory_manager()  # Same instance
```

**Pros:**
- No need to pass parameters
- Guaranteed single instance

**Cons:**
- Global state (harder to test)
- Less explicit dependencies

---

### Variation 2: Dependency Injection Container

```python
# src/container.py
from dependency_injector import containers, providers
from src.agent.memory import MemoryManager

class Container(containers.DeclarativeContainer):
    memory_manager = providers.Singleton(MemoryManager)
```

```python
# In orchestrator.py
from src.container import Container

class Orchestrator:
    def __init__(self):
        container = Container()
        self.memory_manager = container.memory_manager()
```

**Pros:**
- Professional dependency management
- Easy to swap implementations (testing)

**Cons:**
- Requires extra library
- More complex setup

---

### Variation 3: Explicit Parameter Passing (Our Choice)

```python
class Orchestrator:
    def __init__(self, memory_manager: MemoryManager = None):
        self.memory_manager = memory_manager or MemoryManager()
        self.context_builder = ContextBuilder(
            memory_manager=self.memory_manager
        )
```

**Pros:**
- Explicit dependencies (easy to understand)
- Testable (can inject mocks)
- No global state

**Cons:**
- More boilerplate

---

## Testing Shared State

### Test That State Is Actually Shared

```python
# test_shared_state.py
import pytest
from src.agent.orchestrator import Orchestrator

@pytest.mark.asyncio
async def test_memory_manager_is_shared():
    """Verify MemoryManager is shared between components."""
    orchestrator = Orchestrator()

    # Store via orchestrator
    orchestrator.memory_manager.store_interaction(
        conversation_id="test-123",
        role="user",
        content="Hello"
    )

    # Retrieve via context_builder
    context = await orchestrator.context_builder.build_context(
        conversation_id="test-123",
        user_message="How are you?"
    )

    # Should see the stored interaction
    history = context["conversation_history"]
    assert len(history) > 0
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "Hello"
```

**If this test fails:** You have separate instances!

---

## When to Use This Pattern

### ✅ Use for:
- Conversation memory (MemoryManager)
- Database sessions (SQLAlchemy)
- Redis clients (caching, rate limiting)
- Vector stores (ChromaDB, Pinecone)
- Background schedulers (APScheduler)
- WebSocket connections
- Any component with mutable state

### ❌ Don't use for:
- Stateless services (SummarizationService, etc.)
- Pure utility functions
- Constants/configuration
- Request-scoped data (create fresh each time)

---

## Checklist: Implementing Shared State

- [ ] Identify stateful components (has mutable data?)
- [ ] Create shared instance in parent/container
- [ ] Pass instance to all dependencies via constructor
- [ ] Add default fallback: `= None` with `or ClassName()`
- [ ] Verify with integration test (store in one place, retrieve in another)
- [ ] Document which instances are shared in code comments

---

## Summary

### The Problem
Creating separate instances of stateful components breaks state synchronization.

### The Solution
1. Create shared instance once
2. Pass to all dependencies via dependency injection
3. Verify state is actually shared with tests

### The Result
- Conversation history works ✅
- Memory persists across components ✅
- No duplicate state ✅

**This pattern solved Problem #5 and restored full conversation memory.**
