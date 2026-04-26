.PHONY: dev api dashboard setup seed test-unit test-integration test-security test-performance test-all lint

# Detect OS for venv activation path
ifeq ($(OS),Windows_NT)
    PYTHON   := .venv/Scripts/python
    PIP      := .venv/Scripts/pip
else
    PYTHON   := .venv/bin/python
    PIP      := .venv/bin/pip
endif

# ── Start services ──────────────────────────────────────────────────────────
dev:
	$(PYTHON) -m streamlit run sentinel/dashboard/app.py

api:
	$(PYTHON) -m uvicorn sentinel.api.main:app --reload --port 8003

dashboard:
	$(PYTHON) -m streamlit run sentinel/dashboard/app.py

# Note: PostgreSQL is hosted on Supabase/Neon (cloud) or start locally with:
#   docker compose up -d
db-local:
	docker compose up -d

# ── Project setup ────────────────────────────────────────────────────────────
setup:
	python -m venv .venv
	$(PIP) install -r requirements.txt
	$(PYTHON) scripts/setup_ollama.py

# ── Data seeding ─────────────────────────────────────────────────────────────
seed:
	$(PYTHON) scripts/generate_synthetic_data.py
	$(PYTHON) scripts/seed_database.py
	$(PYTHON) scripts/ingest_regulations.py

# ── Tests ────────────────────────────────────────────────────────────────────
test-unit:
	$(PYTHON) -m pytest tests/unit -v --tb=short

test-integration:
	$(PYTHON) -m pytest tests/integration -v --tb=short

test-security:
	$(PYTHON) -m pytest tests/security -v --tb=short

test-performance:
	$(PYTHON) -m pytest tests/performance -v --tb=short

test-all:
	$(PYTHON) -m pytest tests/ -v --tb=short --cov=sentinel --cov-report=html

# ── Code quality ─────────────────────────────────────────────────────────────
lint:
	$(PYTHON) -m ruff check sentinel/ tests/
	$(PYTHON) -m mypy sentinel/ --ignore-missing-imports
