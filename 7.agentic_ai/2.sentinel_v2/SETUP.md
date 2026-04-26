# Setup Guide — Getting SENTINEL Running Locally

## Prerequisites

- **Python 3.11+** (check with `python --version`)
- **PostgreSQL 14+** (with pgvector extension)
- **Redis 6.0+** (for background job queue)
- **Ollama** (optional, for local LLM inference)
- **Git** (for version control)

---

## Step 1: Clone & Create Virtual Environment

```bash
git clone https://github.com/yourusername/sentinel.git
cd sentinel_v2

# Create isolated Python environment
python -m venv .venv

# Activate it
# On macOS/Linux:
source .venv/bin/activate

# On Windows:
.venv\Scripts\activate

# Upgrade pip
pip install --upgrade pip
```

---

## Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

Key packages:
- **fastapi** — API framework
- **sqlalchemy[asyncio]** — Async database ORM
- **langgraph** — State machine orchestration
- **langchain** — LLM abstractions
- **streamlit** — Dashboard UI
- **pydantic** — Data validation

---

## Step 3: Set Up PostgreSQL

### Option A: Local PostgreSQL

**macOS:**
```bash
brew install postgresql
brew services start postgresql
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib
sudo service postgresql start
```

**Windows:**
Download from https://www.postgresql.org/download/windows/

### Option B: Supabase (Cloud, Recommended for Production)

1. Sign up at https://app.supabase.com
2. Create a new project
3. Copy the connection string (Mode: "Transaction")
4. Paste into `.env` as `DATABASE_URL`

### Create Database & Enable Extensions

```bash
# Connect to PostgreSQL
psql postgresql://localhost/postgres

# Create database
CREATE DATABASE sentinel_db;

# Connect to new database
\c sentinel_db

# Enable required extensions
CREATE EXTENSION IF NOT EXISTS pg_trgm;      -- for BM25 text search
CREATE EXTENSION IF NOT EXISTS vector;       -- for pgvector embeddings
CREATE EXTENSION IF NOT EXISTS uuid-ossp;    -- for UUID generation

# Verify
\dx  -- should show: pg_trgm, vector, uuid-ossp
```

---

## Step 4: Configure Environment

```bash
# Copy example configuration
cp .env.example .env

# Edit .env with your values
# Critical fields to fill:
#   - OPENAI_API_KEY or ANTHROPIC_API_KEY
#   - DATABASE_URL (your PostgreSQL connection string)
#   - REDIS_URL (usually redis://localhost:6379 for local)
#   - SENTINEL_API_KEY (any random string)

# Verify DATABASE_URL format:
# postgresql://[user]:[password]@[host]:[port]/[database]
# Example: postgresql://postgres:password@localhost:5432/sentinel_db
```

---

## Step 5: Run Database Migrations

Alembic automatically creates all necessary tables, indexes, and schemas:

```bash
# Run all pending migrations
alembic upgrade head

# Check migration status
alembic current

# To see migration history:
alembic history
```

**What migrations create:**
- `investigations` table (investigation metadata)
- `decisions` table (individual decision records)
- `provenance_nodes` table (W3C PROV-O graph)
- `provenance_edges` table (relationship edges)
- `regulation_documents` table (compliance text)
- `audit_log` table (compliance audit trail)
- `pattern_memory` table (learned patterns)
- HNSW vector indexes for semantic search

---

## Step 6: Start Required Services

### Terminal 1: PostgreSQL (if local)
```bash
# Usually runs automatically on port 5432
psql -U postgres  # verify connection
```

### Terminal 2: Redis (required for background jobs)
```bash
# Start Redis server
redis-server

# Verify running:
redis-cli ping  # should return "PONG"
```

### Terminal 3: Ollama (optional, for local LLM)
```bash
# Start Ollama service
ollama serve

# In another tab, pull model:
ollama pull llama3.2:3b
ollama pull nomic-embed-text
```

---

## Step 7: Start API Server

From project root (with `.venv` activated):

```bash
python -m uvicorn sentinel.api.main:app --port 8003 --reload
```

**Output should show:**
```
INFO:     Uvicorn running on http://127.0.0.1:8003
INFO:     Application startup complete
```

### Verify API is working:
```bash
curl http://localhost:8003/health
# Should return: {"status":"alive","service":"sentinel-api"}

curl http://localhost:8003/ready
# Should return: {"status":"ready",...} if DB + Redis are healthy
```

---

## Step 8: Start Worker (Background Job Processor)

From project root (with `.venv` activated, in a separate terminal):

```bash
python -m sentinel.worker.main

# Or with more verbose output:
python -m sentinel.worker.main --verbose
```

**Output should show:**
```
arq running on high, low redis queues
Waiting for work... (Ctrl+C to quit)
```

---

## Step 9: Start Dashboard

From project root (with `.venv` activated, in another terminal):

```bash
streamlit run sentinel/dashboard/app.py --server.port 8501
```

**Output should show:**
```
You can now view your Streamlit app in your browser.
Local URL: http://localhost:8501
```

---

## Step 10: Verify Everything Works

1. **Open dashboard:** http://localhost:8501
2. **Go to page:** "1. Investigate"
3. **Enter query:** "Review credit decisions from Jan 2024 for ECOA compliance"
4. **Click:** "Start Investigation"
5. **Watch:**
   - API processes request
   - Worker picks up background job
   - Agents run in sequence
   - Dashboard updates with progress
6. **View results:**
   - Results page shows compliance verdict
   - Provenance page shows decision chain
   - Audit page shows investigation history

---

## Troubleshooting

### "Cannot connect to database"
```bash
# Verify PostgreSQL is running:
psql -U postgres -c "SELECT 1"

# Check DATABASE_URL format in .env:
postgresql://[user]:[password]@[host]:[port]/[database]
```

### "Redis connection refused"
```bash
# Start Redis:
redis-server  # or: brew services start redis

# Verify:
redis-cli ping  # should return PONG
```

### "ModuleNotFoundError: No module named 'sentinel'"
```bash
# Ensure .venv is activated:
source .venv/bin/activate

# Reinstall dependencies:
pip install -r requirements.txt
```

### "psycopg error: Connection pool is exhausted"
```bash
# Too many concurrent connections. Reduce pool size in .env:
# Or restart API service:
pkill -f "uvicorn sentinel"
python -m uvicorn sentinel.api.main:app --port 8003
```

### "HNSW index creation failed"
```bash
# Ensure pgvector extension installed:
psql sentinel_db -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Re-run migrations:
alembic downgrade -1
alembic upgrade head
```

---

## Development Workflow

### Run Tests
```bash
# Unit tests (fast)
pytest tests/unit -v

# Integration tests (requires running services)
pytest tests/integration -v

# Specific test file:
pytest tests/integration/test_discovery_agent.py -v
```

### Format Code
```bash
# Auto-format Python:
black sentinel/

# Check linting:
ruff check sentinel/
```

### Check Type Hints
```bash
mypy sentinel/ --ignore-missing-imports
```

### View Logs
```bash
# API logs:
tail -f logs/api.log

# Worker logs:
tail -f logs/worker.log

# Dashboard logs:
tail -f logs/dashboard.log
```

---

## Production Deployment

### Using Docker Compose (Recommended)

```bash
# All services in one command
docker-compose up -d

# Check services:
docker-compose ps

# View logs:
docker-compose logs -f api

# Shut down:
docker-compose down
```

**docker-compose.yml includes:**
- PostgreSQL (persistent volume)
- Redis (in-memory queue)
- Ollama (local LLM service)
- API (FastAPI server)
- Worker (background job processor)
- Scheduler (recurring investigations)
- Streamlit (dashboard)

### Health Monitoring

```bash
# Check API liveness:
curl -s http://localhost:8003/health | jq

# Check readiness (includes DB + Redis):
curl -s http://localhost:8003/ready | jq

# Monitor worker queue depth:
redis-cli ZCARD arq:queue

# View running jobs:
redis-cli KEYS "arq:*"
```

---

## Configuration Reference

Key config files:

### configs/models.yaml
```yaml
models:
  classification:    # Discovery agent: bm25, bert, llm tiers
  reasoning:         # Investigation/legal agents
  synthesis:         # Report agent

context:
  case_batch_size_openai: 100    # Cases per batch for OpenAI
  case_batch_size_ollama: 25     # Cases per batch for Ollama
```

### configs/agents.yaml
```yaml
agents:
  discovery:
    classifier_backend: hybrid  # llm | bert | hybrid
    bm25_top_k: 50
    bert_auto_relevant_threshold: 0.80
  
  investigation:
    max_graph_depth: 5          # Provenance trace depth
    max_retries: 2
    token_budget: 8000
```

### configs/scheduler.yaml
```yaml
schedules:
  daily_compliance:
    cron: "0 8 * * *"           # 8 AM daily
    query: "Review all decisions from yesterday"
    domain: finance
```

---

## Next Steps

1. **Explore the code:**
   - Read `ARCHITECTURE.md` for system design
   - Check `sentinel/agents/` for agent implementations
   - Review `sentinel/graph/builder.py` for LangGraph state machine

2. **Run example investigations:**
   - "Review loan denials from Jan 2024 for ECOA violations"
   - "Analyze credit decisions for age-based discrimination"
   - "Check pharma trial enrollments against FDA 21 CFR 312"

3. **Integrate your data:**
   - Populate `decisions` table with your decision records
   - Update `regulation_documents` with your compliance rules
   - Configure domain-specific rules in `configs/domains/`

4. **Customize for your domain:**
   - Add domain-specific classifiers in `sentinel/agents/classifiers/`
   - Write domain-specific guardrails in `sentinel/guardrails/`
   - Configure domain rules in `configs/domains/your_domain.yaml`

---

## Getting Help

- **Architecture questions:** See `ARCHITECTURE.md`
- **Code questions:** Check inline comments in files
- **API reference:** Run `python -m sentinel.api.main` with `--help`
- **LLM debugging:** Check LangFuse traces at https://app.langfuse.com
- **Database debugging:** Use `psql sentinel_db` to inspect tables

---

**Happy investigating! 🔍**
