# Pattern: Shared State Management

## The Problem

**Symptom:** Bot has ZERO conversation memory
**Root Cause:** Orchestrator and ContextBuilder create separate MemoryManager instances
**Impact:** Users repeat themselves every message — bot has no context

---

## Anti-Pattern: Multiple Instances

```python
# WRONG — Two separate in-memory stores
class Orchestrator:
    def __init__(self):
        self.context_builder = ContextBuilder()  # Creates its own MemoryManager (Instance B)
        self.memory_manager = MemoryManager()    # Instance A

# Orchestrator stores in Instance A → ContextBuilder reads from Instance B (empty!)
```

---

## The Fix: Dependency Injection

```python
# RIGHT — Single shared instance

# orchestrator.py
class Orchestrator:
    def __init__(self):
        self.memory_manager = MemoryManager()  # Create ONCE
        self.context_builder = ContextBuilder(
            memory_manager=self.memory_manager  # Pass it in!
        )

# context_builder.py
class ContextBuilder:
    def __init__(self, memory_manager: MemoryManager = None):
        self.memory_manager = memory_manager or MemoryManager()  # Use shared or create default
```

Now when Orchestrator stores, ContextBuilder retrieves from the same instance.

---

## What Needs to Be Shared (Stateful)

| Component | Why Share |
|---|---|
| MemoryManager | Conversation history |
| Database sessions | SQLAlchemy connections |
| Redis clients | Cache, rate limiting |
| Vector store clients | ChromaDB, Pinecone |
| Background schedulers | APScheduler |
| WebSocket connections | Real-time state |

## What Can Have Multiple Instances (Stateless)

- Services (SummarizationService, IssueDetectionService)
- Pure utility functions
- Constants/configuration
- Request-scoped data

---

## Pattern Variations

### Variation 1: Constructor Injection (Recommended)
```python
class Orchestrator:
    def __init__(self):
        self.memory_manager = MemoryManager()
        self.context_builder = ContextBuilder(memory_manager=self.memory_manager)
```
Pros: Explicit dependencies, testable (inject mocks), no global state

### Variation 2: Singleton Factory
```python
_memory_manager = None

def get_memory_manager() -> MemoryManager:
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager
```
Pros: No parameter passing needed
Cons: Global state, harder to test

### Variation 3: Dependency Injection Container
```python
from dependency_injector import containers, providers

class Container(containers.DeclarativeContainer):
    memory_manager = providers.Singleton(MemoryManager)
```
Pros: Professional DI, easy to swap implementations
Cons: Extra library, complex setup

---

## Verification Test

```python
@pytest.mark.asyncio
async def test_memory_manager_is_shared():
    orchestrator = Orchestrator()

    # Store via orchestrator
    orchestrator.memory_manager.store_interaction(
        conversation_id="test-123", role="user", content="Hello"
    )

    # Retrieve via context_builder
    context = await orchestrator.context_builder.build_context("test-123", "Follow-up")

    history = context["conversation_history"]
    assert len(history) > 0  # If empty → separate instances!
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "Hello"
```

---

## Checklist
- [ ] Identify all stateful components (has mutable data?)
- [ ] Create shared instance in parent/container first
- [ ] Pass to all dependencies via constructor
- [ ] Add default fallback: `memory_manager = None` → `or MemoryManager()`
- [ ] Verify with integration test (store in one place, retrieve in another)
- [ ] Document which instances are shared in code comments
