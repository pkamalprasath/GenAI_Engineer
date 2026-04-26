# Contributing to GenAI Engineer Portfolio

This is a **professional portfolio**, not an open-source project. However, we follow best practices for code quality and professionalism.

## Code of Conduct

- **Be respectful** to all contributors
- **Be constructive** in feedback
- **Focus on the problem,** not the person
- **Assume good intentions** but ask for clarification

---

## Development Setup

```bash
# Clone and set up virtual environment
git clone https://github.com/pkamalprasath/GenAI_Engineer.git
cd GenAI_Engineer

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate       # Windows

# Install dependencies for a project
cd 04.open_claw_slack_bot
pip install -r requirements.txt
```

---

## Code Standards

### Python Style

```bash
# Format with black
black . --exclude=".venv,notebooks,.git,__pycache__"

# Lint with ruff
ruff check .

# Type check with mypy (optional)
mypy . --ignore-missing-imports
```

### Commit Message Format

```
type: short description (under 70 characters)

- Detailed explanation of what changed
- Additional context as needed
- Fixes #123 (if closing an issue)
```

**Types:**
- `feat:` — New feature
- `fix:` — Bug fix
- `docs:` — Documentation only
- `refactor:` — Code restructuring (no behavior change)
- `test:` — Test additions/modifications
- `chore:` — Build, deps, maintenance
- `security:` — Security improvements

### Example

```
feat: add pinned versions to requirements.txt

- Pin all dependencies to exact versions (reproducibility)
- Add comments explaining version choices for security
- Verify all tests pass with pinned versions
- Update CI/CD to validate pinned versions
```

### Type Hints

All functions require type hints:

```python
# GOOD ✓
async def search_documents(
    query: str,
    top_k: int = 5,
    filters: dict[str, Any] | None = None
) -> list[Document]:
    """Search documents by semantic similarity."""
    ...

# BAD ✗
async def search_documents(query, top_k=5, filters=None):
    ...
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

### Module Docstrings

Every Python file should start with a module docstring:

```python
"""
Module Name — Brief description of what this module does.

Purpose:
  ✓ What problem does it solve?
  ✓ What components does it provide?

Usage:
  >>> from module import function
  >>> function(arg1, arg2)

Design decisions:
  - Why this approach instead of alternatives?
  - What tradeoffs were accepted?
"""
```

---

## Testing

### Run Tests

```bash
# Project-specific tests
cd 04.open_claw_slack_bot
pytest tests/ -v

# With coverage
pytest tests/ --cov=sentinel

# Specific test
pytest tests/test_agent.py::test_memory_persistence -v
```

### Writing Tests

Create tests in the project's `tests/` folder:

```
tests/
├── unit/
│   ├── test_memory_manager.py
│   └── test_scheduler.py
└── integration/
    ├── test_slack_integration.py
    └── test_database.py
```

Example test:

```python
import pytest
from pathlib import Path
from module import function

@pytest.mark.asyncio
async def test_function_basic():
    """
    Test that function returns expected output.
    
    Given: valid input parameters
    When: function is called
    Then: returns correct result
    """
    result = await function(arg1="test", arg2=42)
    assert result["status"] == "success"
    assert result["count"] == 42
```

---

## Before Committing

```bash
# 1. Format code
black . --exclude=".venv,notebooks"
ruff check . --fix

# 2. Run tests
pytest tests/ -v

# 3. Type check
mypy . --ignore-missing-imports

# 4. Review changes
git diff

# 5. Commit
git commit -m "type: description"

# 6. Push to your fork
git push origin feature/branch-name
```

---

## Pull Request Process

1. **Title:** Describe what your PR does (under 70 characters)
2. **Description:** Explain why this change is needed
3. **Linked issue:** Reference the GitHub issue this solves
4. **Tests:** Show that tests pass
5. **Checklist:**
   - [ ] Tests pass locally
   - [ ] Code is formatted (`black` + `ruff`)
   - [ ] Type hints added (`mypy`)
   - [ ] Comments explain WHY (not WHAT)
   - [ ] No hardcoded secrets
   - [ ] CHANGELOG.md updated (if new feature)

---

## Project Structure

Each project should follow this structure:

```
project/
├── README.md              (what/why/how)
├── requirements.txt       (pinned versions)
├── .gitignore            (clean repo)
├── source/               (implementation)
├── tests/                (unit + integration)
└── docs/                 (if applicable)
```

---

## Reporting Issues

- **Bugs:** [GitHub Issues](https://github.com/pkamalprasath/GenAI_Engineer/issues)
- **Security:** [SECURITY.md](SECURITY.md)
- **Discussions:** [GitHub Discussions](https://github.com/pkamalprasath/GenAI_Engineer/discussions)

---

## Questions?

- **Architecture:** See project-specific ARCHITECTURE.md
- **Setup:** See project-specific SETUP.md
- **Code:** Check inline comments in files

---

**Thank you for maintaining code quality!**
