# Engineering RAG — Complete Setup Guide

This guide covers every external service the system depends on.
Follow sections in order on a fresh machine.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Project Installation](#2-project-installation)
3. [Supabase — PostgreSQL + pgvector](#3-supabase--postgresql--pgvector)
4. [Anthropic / OpenAI API Keys](#4-anthropic--openai-api-keys)
5. [Langfuse Cloud — LLM & RAG Traces](#5-langfuse-cloud--llm--rag-traces)
6. [Grafana Cloud — Log Search & Dashboards](#6-grafana-cloud--log-search--dashboards)
7. [Final .env File](#7-final-env-file)
8. [First Run](#8-first-run)
9. [Verification Checklist](#9-verification-checklist)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.11+ | Runtime |
| pip | latest | Package manager |
| Git | any | Clone repo |
| Tesseract OCR | 5.x | OCR fallback for scanned PDFs |

**Install Tesseract (Windows):**
```
https://github.com/UB-Mannheim/tesseract/wiki
→ Download installer → Add to PATH during install
```

**Install Tesseract (macOS):**
```bash
brew install tesseract
```

---

## 2. Project Installation

```bash
# Clone and enter the project
git clone <your-repo-url>
cd projects/engineering-rag

# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (macOS / Linux)
source .venv/bin/activate

# Install all dependencies
pip install -r requirements.txt

# Download spaCy model (required for PII detection)
python -m spacy download en_core_web_sm

# Copy env template
cp .env.example .env
# Now edit .env and fill in your credentials (see sections below)
```

---

## 3. Supabase — PostgreSQL + pgvector

Supabase provides the managed PostgreSQL database with pgvector extension.
Free tier is sufficient for development.

### 3.1 Create account and project

1. Go to [supabase.com](https://supabase.com) → **Start your project**
2. Sign up with GitHub or email
3. Click **New Project**
   - Organisation: your name
   - Project name: `engineering-rag`
   - Database password: create a strong password — **save this**
   - Region: choose closest to you
4. Wait ~2 minutes for the project to provision

### 3.2 Enable pgvector extension

1. Inside your project → left sidebar → **SQL Editor**
2. Run the following:

```sql
-- Enable pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify it's active
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
-- Expected: one row showing "vector"
```

### 3.3 Get connection credentials

1. Left sidebar → **Settings** → **Database**
2. Scroll to **Connection string** → select **URI** tab
3. Copy the URI — it looks like:
   ```
   postgresql://postgres:[YOUR-PASSWORD]@db.xxxxxxxxxxxx.supabase.co:5432/postgres
   ```
4. Also note the individual parts for `.env`:

| .env key | Where to find it |
|----------|-----------------|
| `POSTGRES_HOST` | Settings → Database → Host (e.g. `db.abcdefgh.supabase.co`) |
| `POSTGRES_PORT` | Always `5432` |
| `POSTGRES_USER` | Always `postgres` |
| `POSTGRES_PASSWORD` | The password you set when creating the project |
| `POSTGRES_DB` | Always `postgres` |
| `POSTGRES_SSL` | Always `require` for Supabase |

### 3.4 Add to .env

```bash
POSTGRES_HOST=db.xxxxxxxxxxxx.supabase.co
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-strong-password-here
POSTGRES_DB=postgres
POSTGRES_SSL=require
```

### 3.5 Verify connection

```bash
python -c "
from configs.settings import DATABASE_URL
import psycopg2
conn = psycopg2.connect(DATABASE_URL + '?sslmode=require')
print('Supabase connection: OK')
conn.close()
"
```

---

## 4. Anthropic / OpenAI API Keys

The system uses **Anthropic Claude** by default (stronger models, better results).
OpenAI is the fallback. At least one is required.

### 4.1 Anthropic (recommended)

1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Sign up / log in
3. Left sidebar → **API Keys** → **Create Key**
4. Name it `engineering-rag` → copy the key (starts with `sk-ant-`)

Models used:
| Setting | Model | Used for |
|---------|-------|---------|
| `TEXT_LLM_STRONG` | `claude-sonnet-4-6` | Main answer generation |
| `TEXT_LLM_FAST` | `claude-haiku-4-5-20251001` | CRAG scoring, HyDE, Self-RAG, router |

### 4.2 OpenAI (optional fallback)

1. Go to [platform.openai.com](https://platform.openai.com)
2. Top-right → **API Keys** → **Create new secret key**
3. Name it `engineering-rag` → copy the key (starts with `sk-proj-`)

### 4.3 Add to .env

```bash
ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_API_KEY=sk-proj-xxxx          # optional, leave blank if not using

TEXT_LLM_STRONG=claude-sonnet-4-6
TEXT_LLM_FAST=claude-haiku-4-5-20251001
TEXT_LLM=gpt-4o-mini
VISION_LLM=gpt-4o
```

---

## 5. Langfuse Cloud — LLM & RAG Traces

Langfuse gives you a full trace of every query through the pipeline:
token counts, latency per step, CRAG scores, Self-RAG status, and cost.

Free tier: **unlimited traces**, 30-day retention.

### 5.1 Create account and project

1. Go to [cloud.langfuse.com](https://cloud.langfuse.com)
2. Sign up with Google or GitHub
3. Click **New Project** → name it `engineering-rag` → **Create**

### 5.2 Get API keys

1. Inside your project → left sidebar → **Settings**
2. Scroll to **API Keys** section → **Create new API key**
3. A dialog shows both keys:
   - **Public key** — starts with `pk-lf-`
   - **Secret key** — starts with `sk-lf-` — **copy now, shown only once**

### 5.3 Add to .env

```bash
LANGFUSE_PUBLIC_KEY=pk-lf-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
LANGFUSE_SECRET_KEY=sk-lf-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
LANGFUSE_HOST=https://cloud.langfuse.com
```

### 5.4 What you see in Langfuse

After asking any question in the app, go to **Traces** in Langfuse:

```
rag_query  (root trace — total latency + confidence)
├── retrieval     → chunks returned, sub-queries used
├── crag          → relevance labels per chunk, final confidence
├── generation    → model used, prompt, full answer
└── self_rag      → SUPPORTED / PARTIALLY_SUPPORTED / NOT_SUPPORTED
```

**Useful Langfuse views:**

| View | Path | What it shows |
|------|------|---------------|
| All traces | Traces | Every user query end-to-end |
| Cost by model | Dashboard → Cost | Token spend per model per day |
| Slow queries | Traces → sort by latency | Queries taking > 5s |
| Failed Self-RAG | Traces → filter `self_rag=not_supported` | Hallucination candidates |
| CRAG low confidence | Traces → filter `confidence=low` | Queries with poor retrieval |

---

## 6. Grafana Cloud — Log Search & Dashboards

Grafana Cloud ships your Python `logs/rag.log` and `logs/app.log` to
a hosted Loki instance for real-time search and dashboards.

Free tier: **50 GB logs/month**, unlimited dashboards.

### 6.1 Create account and stack

1. Go to [grafana.com](https://grafana.com) → **Create free account**
2. Fill in details → verify email
3. On the welcome screen → **Create stack**
   - Stack name: `engineering-rag` (or anything)
   - Region: choose closest to you
4. Click **Finish setup** — your Grafana Cloud portal opens

### 6.2 Get Loki credentials

1. In the Grafana Cloud portal → left sidebar → **Connections**
2. Click **Add new connection**
3. Search **Loki** → click the result
4. On the right panel click **"Python Logging"** tab
5. The page shows your ready-made config:
   - **Loki Push URL** — e.g. `https://logs-prod-012.grafana.net/loki/api/v1/push`
   - **User** — a 6–7 digit number e.g. `845123`
6. Click **Generate API token**:
   - Token name: `engineering-rag`
   - Role: **MetricsPublisher**
   - Click **Create token** → copy the token starting with `glc_`

> **Alternative path:** Grafana Cloud portal → your stack → **Loki** tile → **Send Logs** button

### 6.3 Add to .env

```bash
GRAFANA_LOKI_URL=https://logs-prod-012.grafana.net/loki/api/v1/push
GRAFANA_USER=845123
GRAFANA_API_KEY=glc_eyJoxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
APP_ENV=dev
```

> Replace `012` in the URL with your actual region number from step 6.2.

### 6.4 Verify logs are flowing

1. Start the app: `streamlit run app.py`
2. Ask any question
3. In Grafana Cloud portal → left sidebar → **Explore**
4. Data source dropdown → select **Loki**
5. Run this query:

```logql
{app="engineering-rag"}
```

You should see Python log lines appearing within ~10 seconds.

### 6.5 Useful LogQL queries

Paste these into Grafana → Explore → Loki:

```logql
# All log lines (live tail)
{app="engineering-rag"}

# Errors only
{app="engineering-rag"} |= "ERROR"

# Warnings and above
{app="engineering-rag"} | logfmt | level =~ "WARNING|ERROR|CRITICAL"

# CRAG low-confidence answers
{app="engineering-rag"} |= "confidence=low"

# Self-RAG NOT_SUPPORTED events (possible hallucinations)
{app="engineering-rag"} |= "NOT_SUPPORTED"

# Self-RAG retries triggered
{app="engineering-rag"} |= "retried=True"

# Slow queries (filter by answer length as proxy)
{app="engineering-rag"} |= "_run complete"

# API errors
{app="engineering-rag"} |= "Query pipeline failed"

# PII detected in user queries
{app="engineering-rag"} |= "PII detected in user query"

# From Streamlit app process only
{app="engineering-rag", env="dev"} |= "app.py"
```

### 6.6 Build a monitoring dashboard

1. Grafana → left sidebar → **Dashboards** → **New** → **New dashboard**
2. **Add visualization** → data source: **Loki**
3. Add these panels one by one:

**Panel 1 — Live error log**
- Type: `Logs`
- Query: `{app="engineering-rag"} |= "ERROR"`
- Title: `Recent Errors`

**Panel 2 — Error rate over time**
- Type: `Time series`
- Query: `sum(count_over_time({app="engineering-rag"} |= "ERROR" [5m]))`
- Title: `Error Rate (5-min buckets)`

**Panel 3 — Self-RAG NOT_SUPPORTED count**
- Type: `Stat`
- Query: `count_over_time({app="engineering-rag"} |= "NOT_SUPPORTED" [24h])`
- Title: `Self-RAG failures (24h)`

**Panel 4 — Low confidence answers**
- Type: `Stat`
- Query: `count_over_time({app="engineering-rag"} |= "confidence=low" [24h])`
- Title: `Low confidence answers (24h)`

4. **Save dashboard** → name it `Engineering RAG Monitoring`

---

## 7. Final .env File

Copy this template into your `.env` file and fill in all values:

```bash
# ── LLM API Keys ──────────────────────────────────────────────────────────
ANTHROPIC_API_KEY=sk-ant-api03-xxxx          # required (primary LLM)
OPENAI_API_KEY=sk-proj-xxxx                  # optional fallback

# ── LLM Model Selection ────────────────────────────────────────────────────
TEXT_LLM_STRONG=claude-sonnet-4-6
TEXT_LLM_FAST=claude-haiku-4-5-20251001
TEXT_LLM=gpt-4o-mini
VISION_LLM=gpt-4o

# ── Supabase PostgreSQL + pgvector ─────────────────────────────────────────
POSTGRES_HOST=db.xxxxxxxxxxxx.supabase.co
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-supabase-db-password
POSTGRES_DB=postgres
POSTGRES_SSL=require

# ── Langfuse Cloud (LLM traces) ────────────────────────────────────────────
LANGFUSE_PUBLIC_KEY=pk-lf-xxxx
LANGFUSE_SECRET_KEY=sk-lf-xxxx
LANGFUSE_HOST=https://cloud.langfuse.com

# ── Grafana Cloud Loki (log search) ────────────────────────────────────────
GRAFANA_LOKI_URL=https://logs-prod-012.grafana.net/loki/api/v1/push
GRAFANA_USER=123456
GRAFANA_API_KEY=glc_xxxx
APP_ENV=dev

# ── Feature Flags ──────────────────────────────────────────────────────────
USE_HYDE=true
USE_QUERY_DECOMPOSITION=true
USE_CRAG=true
USE_SELF_RAG=true
PII_REDACTION_ENABLED=false               # set true to enable Presidio redaction

# ── Logging ────────────────────────────────────────────────────────────────
LOG_LEVEL=INFO
```

---

## 8. First Run

### 8.1 Ingest your documents

```bash
# Place PDFs in the data/ folder first
python ingest_docs.py data/

# Expected output:
# NEW: pump_maintenance_manual.pdf → 342 text chunks, 15 tables, 28 images
# NEW: sds_chemical_xyz.pdf        → 89 text chunks, 8 tables, 3 images
```

### 8.2 Start the Streamlit UI

```bash
streamlit run app.py
# Opens at http://localhost:8501
```

### 8.3 Start the REST API (optional)

```bash
uvicorn api:app --reload --host 0.0.0.0 --port 8000
# Swagger docs at http://localhost:8000/docs
```

---

## 9. Verification Checklist

Run this script after completing all setup steps:

```bash
python -c "
import sys
sys.path.insert(0, '.')
from configs.settings import (
    HAS_ANTHROPIC, HAS_OPENAI,
    LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY,
    GRAFANA_LOKI_URL, GRAFANA_USER, GRAFANA_API_KEY,
    DATABASE_URL, POSTGRES_SSL,
    USE_CRAG, USE_SELF_RAG, USE_HYDE,
)

def check(name, condition):
    print(f'  [{ \"OK\" if condition else \"MISSING\" }] {name}')

print('=== Setup Verification ===')
print()
print('LLM:')
check('Anthropic API key',  HAS_ANTHROPIC)
check('OpenAI API key (optional)', HAS_OPENAI)

print()
print('Database:')
check('Supabase host configured', 'supabase.co' in DATABASE_URL)
check('SSL enabled', POSTGRES_SSL == 'require')

print()
print('Observability:')
check('Langfuse public key', bool(LANGFUSE_PUBLIC_KEY) and not LANGFUSE_PUBLIC_KEY.endswith('here'))
check('Langfuse secret key', bool(LANGFUSE_SECRET_KEY) and not LANGFUSE_SECRET_KEY.endswith('here'))
check('Grafana Loki URL',    bool(GRAFANA_LOKI_URL)    and 'YOUR' not in GRAFANA_LOKI_URL)
check('Grafana user',        bool(GRAFANA_USER)         and GRAFANA_USER != '123456')
check('Grafana API key',     bool(GRAFANA_API_KEY)      and not GRAFANA_API_KEY.endswith('here'))

print()
print('Feature flags:')
check('CRAG enabled',   USE_CRAG)
check('Self-RAG enabled', USE_SELF_RAG)
check('HyDE enabled',   USE_HYDE)
"
```

Then ask a test question in the app and verify all three dashboards show activity:

| Check | Where | What to look for |
|-------|-------|-----------------|
| Answer returned | Streamlit UI | Answer with source citations |
| RAG trace visible | cloud.langfuse.com → Traces | `rag_query` trace with 4 child spans |
| Logs flowing | Grafana → Explore → Loki | Lines from `{app="engineering-rag"}` |
| DB chunks exist | Supabase → Table Editor → chunks | Rows with embeddings |

---

## 10. Troubleshooting

### Supabase connection refused
```
psycopg2.OperationalError: could not connect to server
```
- Check `POSTGRES_SSL=require` is set
- Verify host is `db.xxxx.supabase.co` not `localhost`
- Check password has no special characters that need URL-encoding

### pgvector extension missing
```
UndefinedObject: type "vector" does not exist
```
- Run `CREATE EXTENSION IF NOT EXISTS vector;` in Supabase SQL Editor
- Supabase free tier supports pgvector — it just needs enabling

### Langfuse traces not appearing
- Wait 30–60 seconds — traces are batched
- Check keys are not the placeholder values from `.env.example`
- Verify `LANGFUSE_HOST=https://cloud.langfuse.com` (no trailing slash)

### Grafana logs not appearing
- Check `GRAFANA_USER` is the **numeric** user ID (6–7 digits), not your email
- Check the Loki URL ends in `/loki/api/v1/push`
- Check the API key has **MetricsPublisher** role, not Viewer
- `python-logging-loki` sends logs asynchronously — wait ~15 seconds

### No answer / "No relevant information found"
- Run `python ingest_docs.py data/` first
- Check chunks exist: Supabase → Table Editor → `chunks` table
- Check embedding model loaded: look for `Embedding model loaded` in `logs/rag.log`

### PII redaction not working
- Set `PII_REDACTION_ENABLED=true` in `.env`
- Run `python -m spacy download en_core_web_sm` if not done already
- Test: `python -c "from src.guardrails.pii_detector import redact_pii; print(redact_pii('Call John at 555-1234'))"`

---

*Last updated: April 2026*
