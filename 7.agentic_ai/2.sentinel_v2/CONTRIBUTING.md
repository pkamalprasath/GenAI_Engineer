# Contributing to SENTINEL

Thank you for your interest in contributing! SENTINEL is an open-source project focused on compliance automation. Here's how to get involved.

## Code of Conduct

- **Be respectful** to all contributors
- **Be constructive** in feedback and discussions
- **Focus on the problem,** not the person
- **Assume good intentions** but ask for clarification

---

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork:** `git clone https://github.com/your-username/sentinel.git`
3. **Follow SETUP.md** to get the project running locally
4. **Create a feature branch:** `git checkout -b feature/my-improvement`

---

## Development Standards

### Code Style

- **Python formatting:** Use `black` (auto-formatter)
- **Linting:** Pass `ruff check`
- **Type hints:** Required for all functions (checked with `mypy`)
- **Docstrings:** Required for all modules and public functions

```bash
# Before committing:
black sentinel/
ruff check sentinel/ --fix
mypy sentinel/ --ignore-missing-imports
```

### Inline Comments

Add comments explaining **why** code exists, not **what** it does:

```python
# GOOD ✓
# Use asyncio semaphore to prevent overwhelming local Ollama
# (8GB RAM limit, single-threaded model inference)
_OLLAMA_SEMAPHORE = asyncio.Semaphore(1)

# BAD ✗
# Create a semaphore
_OLLAMA_SEMAPHORE = asyncio.Semaphore(1)
```

### File Headers

All Python files should start with a module docstring explaining purpose:

```python
"""
Module Name — Brief description of what this module does.

Purpose:
  ✓ What problem does it solve?
  ✓ What components does it provide?

Usage:
  Example code snippet

Design decisions:
  - Why this approach instead of alternatives?
  - What tradeoffs were accepted?
"""
```

---

## Testing Requirements

**All changes must be tested.**

### Run Tests Before Committing

```bash
# Unit tests (fast, no external services)
pytest tests/unit -v

# Integration tests (requires running API + DB + Redis)
pytest tests/integration -v

# All tests:
pytest tests/ -v

# Specific test:
pytest tests/test_discovery_agent.py::test_bm25_filtering -v
```

### Writing New Tests

Create tests in `tests/` matching the source structure:

```
tests/
├── unit/
│   ├── test_guardrails.py
│   └── test_provenance_store.py
└── integration/
    ├── test_discovery_agent.py
    └── test_investigation_pipeline.py
```

Example test:
```python
import pytest
from sentinel.agents.discovery_agent import run as discovery_run

@pytest.mark.asyncio
async def test_discovery_agent_filters_cases(db_session):
    """
    Test that discovery agent correctly filters cases by relevance.
    
    Given: 100 random cases + 3 relevant cases in database
    When: Discovery agent runs with compliance-focused query
    Then: Returns only the 3 relevant case IDs
    """
    state = make_test_investigation_state(query="ECOA violations")
    result = await discovery_run(state, db_session)
    
    assert len(result["relevant_case_ids"]) == 3
    assert "relevant-case-1" in result["relevant_case_ids"]
```

---

## Types of Contributions

### 🐛 Bug Fixes

1. **Open an issue** describing the bug and steps to reproduce
2. **Create a branch:** `git checkout -b fix/issue-123`
3. **Write a failing test** that reproduces the bug
4. **Fix the code** to make the test pass
5. **Verify** all tests still pass
6. **Open a PR** linking to the issue

### ✨ New Features

1. **Discuss in an issue** before starting (check if others are working on it)
2. **Design document** for complex features (see ARCHITECTURE.md format)
3. **Create a branch:** `git checkout -b feature/my-feature`
4. **Implement with tests** (test-driven development)
5. **Update documentation** (README, architecture docs, inline comments)
6. **Open a PR** describing what it does and why

### 📖 Documentation

- **Fix typos:** Open a PR directly
- **Improve explanations:** Clarify confusing sections
- **Add examples:** Show how to use new features
- **Update architecture:** If code changes warrant docs updates

### ⚡ Performance Improvements

1. **Benchmark the current implementation:** Show concrete numbers
2. **Implement improvement** with metrics
3. **Compare:** Before/after performance, no regressions in accuracy
4. **Document:** Why this optimization exists and its tradeoffs

---

## Git Workflow

### Commit Message Format

```
type: short description (under 70 characters)

- Detailed explanation of what and why
- Additional context as needed
- Fixes #123 (if closing an issue)
```

**Types:**
- `feat:` — New feature
- `fix:` — Bug fix
- `perf:` — Performance improvement
- `docs:` — Documentation only
- `refactor:` — Code restructuring (no behavior change)
- `test:` — Test additions/modifications
- `chore:` — Build, deps, maintenance

### Example
```
feat: add HNSW vector index for 10x faster regulation search

- Create migration 003_hnsw_indexes.sql
- Build HNSW with m=16, ef_construction=64
- Benchmark: 100ms cosine search → 10ms HNSW search
- Measure: No accuracy regression in top-10 results
- Fixes #456
```

### Before Pushing

```bash
# 1. Run all tests
pytest tests/ -v

# 2. Format code
black sentinel/
ruff check sentinel/ --fix

# 3. Type check
mypy sentinel/

# 4. Review your changes
git diff

# 5. Commit
git commit -m "feat: ..."

# 6. Push to your fork
git push origin feature/my-feature
```

---

## Pull Request Process

1. **Title:** Describe what your PR does
2. **Description:** Explain why this change is needed
3. **Linked issue:** Reference the GitHub issue this solves
4. **Tests:** Show that tests pass (`pytest tests/ -v`)
5. **Screenshots:** If UI changes, include before/after
6. **Checklist:**
   - [ ] Tests pass locally
   - [ ] Code is formatted (`black` + `ruff`)
   - [ ] Type hints are added (`mypy`)
   - [ ] Documentation is updated
   - [ ] Commit messages follow convention
   - [ ] No hardcoded secrets or credentials

### PR Review Process

- **Maintainers will review** within 2-3 days
- **Request changes** if needed; rebase and push updates
- **Approval:** Once approved, maintainers will merge

---

## Architecture Decisions

When making significant changes, document the decision:

**Decision Record Format (optional but appreciated):**

```markdown
## Decision: Switch from pgvector cosine search to HNSW

### Context
Vector similarity search was slow (100ms per query).

### Options Considered
1. Use Algolia (external service, $$)
2. Add pgvector HNSW indexes (built-in, cheap)
3. Switch to Qdrant (new infrastructure)

### Decision
Option 2 — pgvector HNSW indexes

### Rationale
- No external dependencies
- Built into PostgreSQL
- 10x speedup verified
- Minimal code changes

### Tradeoffs
- Index creation takes 5 minutes
- Adds ~20MB to database
- Limited to cosine distance (but we only use cosine)

### Consequences
- Future searches 10x faster
- Must remember to create indexes in new environments
```

---

## Areas Looking for Contributions

High-impact improvements:

- [ ] **Streaming dashboard** — Real-time investigation progress (WebSocket)
- [ ] **Custom regulation upload** — Let users upload PDFs, auto-extract sections
- [ ] **Workflow orchestration** — Schedule recurring investigations per domain
- [ ] **Performance:** Profile and optimize bottlenecks
- [ ] **Documentation:** Improve guides, add examples
- [ ] **Tests:** Increase coverage above 80%
- [ ] **Kubernetes:** Add Helm charts for production deployment

See [GitHub Issues](https://github.com/yourusername/sentinel/issues) for more.

---

## Questions?

- **Architecture:** See `ARCHITECTURE.md`
- **Setup:** See `SETUP.md`
- **Code:** Check inline comments in files
- **Discussions:** Use GitHub Discussions

---

## Thank You! 🙏

Thank you for making SENTINEL better. Your contributions help regulatory teams audit AI systems more effectively.

---

**Happy contributing!**
