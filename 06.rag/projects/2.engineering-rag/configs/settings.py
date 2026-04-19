"""
settings.py — Centralised configuration for the Engineering RAG system.

All env vars are read here once. Every other module imports from this file.
Never call os.getenv() scattered through the codebase.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (two levels up from configs/)
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)


# ── LLM Config ────────────────────────────────────────────────────────────
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Strong model for generation (reasoning, multihop)
# Fast/cheap model for judgment tasks (CRAG scoring, HyDE, Self-RAG, judge)
TEXT_LLM        = os.getenv("TEXT_LLM",        "gpt-4o-mini")        # OpenAI fallback
VISION_LLM      = os.getenv("VISION_LLM",      "gpt-4o")             # OpenAI vision fallback
TEXT_LLM_STRONG = os.getenv("TEXT_LLM_STRONG", "claude-sonnet-4-6")  # generation
TEXT_LLM_FAST   = os.getenv("TEXT_LLM_FAST",   "claude-haiku-4-5-20251001")  # CRAG/HyDE/Self-RAG/judge

HAS_OPENAI    = bool(OPENAI_API_KEY)
HAS_ANTHROPIC = bool(ANTHROPIC_API_KEY)


# ── Embedding Config ──────────────────────────────────────────────────────
# all-MiniLM-L6-v2: winner from experiments (score 5.0, fastest)
# Used for ALL chunk types: text, tables, image captions
EMBED_MODEL = os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")
EMBED_DIM   = 384   # dimension of all-MiniLM-L6-v2 output


# ── PostgreSQL + pgvector Config ──────────────────────────────────────────
# Supports both local Docker and cloud providers (Neon, Supabase, Railway).
# Cloud providers require sslmode=require — set POSTGRES_SSL=require in .env.
POSTGRES_HOST     = os.getenv("POSTGRES_HOST",     "localhost")
POSTGRES_PORT     = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_USER     = os.getenv("POSTGRES_USER",     "raguser")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "ragpass")
POSTGRES_DB       = os.getenv("POSTGRES_DB",       "ragdb")
POSTGRES_SSL      = os.getenv("POSTGRES_SSL",      "")   # set to "require" for cloud

_ssl_suffix = f"?sslmode={POSTGRES_SSL}" if POSTGRES_SSL else ""
DATABASE_URL = (
    f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}{_ssl_suffix}"
)


# ── Retrieval Config ──────────────────────────────────────────────────────
# Top-k per chunk type: from experiments, k=5 best quality/latency tradeoff
TOP_K_PER_TYPE = int(os.getenv("TOP_K_PER_TYPE", "8"))   # search N per type
FINAL_TOP_K    = int(os.getenv("FINAL_TOP_K",    "10"))  # after RRF merge

# RRF constant: standard value, makes rank 1 >> rank 10
RRF_K = int(os.getenv("RRF_K", "60"))


# ── Chunking Config ───────────────────────────────────────────────────────
# Semantic chunker: winner from experiments (C4, score 5.0)
SEMANTIC_BREAKPOINT_TYPE      = os.getenv("SEMANTIC_BREAKPOINT_TYPE",      "percentile")
SEMANTIC_BREAKPOINT_THRESHOLD = int(os.getenv("SEMANTIC_BREAKPOINT_THRESHOLD", "95"))

# Max image size to send to GPT-4o vision (resize larger images)
MAX_IMAGE_PIXELS = int(os.getenv("MAX_IMAGE_PIXELS", str(1024 * 1024)))


# ── Generation Config ─────────────────────────────────────────────────────
MAX_ANSWER_TOKENS     = int(os.getenv("MAX_ANSWER_TOKENS",     "1024"))
MAX_HYDE_TOKENS       = int(os.getenv("MAX_HYDE_TOKENS",       "256"))
MAX_CRAG_JUDGE_TOKENS = int(os.getenv("MAX_CRAG_JUDGE_TOKENS", "64"))
MAX_SELF_RAG_TOKENS   = int(os.getenv("MAX_SELF_RAG_TOKENS",   "128"))
SELF_RAG_MAX_RETRIES  = int(os.getenv("SELF_RAG_MAX_RETRIES",  "1"))


# ── CRAG Config ───────────────────────────────────────────────────────────
CRAG_IMAGE_PASSAGE_TOKENS  = int(os.getenv("CRAG_IMAGE_PASSAGE_TOKENS",  "600"))
CRAG_TEXT_PASSAGE_TOKENS   = int(os.getenv("CRAG_TEXT_PASSAGE_TOKENS",   "400"))
CRAG_SCORE_RELEVANT        = float(os.getenv("CRAG_SCORE_RELEVANT",   "1.0"))
CRAG_SCORE_AMBIGUOUS       = float(os.getenv("CRAG_SCORE_AMBIGUOUS",  "0.5"))
CRAG_SCORE_IRRELEVANT      = float(os.getenv("CRAG_SCORE_IRRELEVANT", "0.0"))


# ── HyDE Config ───────────────────────────────────────────────────────────
HYDE_TEMPERATURE = float(os.getenv("HYDE_TEMPERATURE", "0.3"))


# ── Query Decomposer Config ───────────────────────────────────────────────
DECOMP_MAX_SUBQUERIES     = int(os.getenv("DECOMP_MAX_SUBQUERIES",    "4"))
DECOMP_MIN_QUERY_LENGTH   = int(os.getenv("DECOMP_MIN_QUERY_LENGTH",  "10"))


# ── Adaptive Router Config ────────────────────────────────────────────────
ROUTER_CLASSIFY_MAX_TOKENS = int(os.getenv("ROUTER_CLASSIFY_MAX_TOKENS", "5"))
ROUTER_ANSWER_MAX_TOKENS   = int(os.getenv("ROUTER_ANSWER_MAX_TOKENS",   "512"))


# ── Observability (Langfuse Cloud) ────────────────────────────────────────
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
LANGFUSE_HOST       = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")


# ── Feature Flags ─────────────────────────────────────────────────────────
# Set to "false" / "0" in .env to disable the module
def _bool(key: str, default: bool) -> bool:
    val = os.getenv(key, "").lower()
    if val in ("false", "0", "no", "off"):
        return False
    if val in ("true", "1", "yes", "on"):
        return True
    return default

USE_HYDE               = _bool("USE_HYDE",               True)
USE_QUERY_DECOMPOSITION = _bool("USE_QUERY_DECOMPOSITION", True)
USE_CRAG               = _bool("USE_CRAG",               True)
USE_SELF_RAG           = _bool("USE_SELF_RAG",           True)
PII_REDACTION_ENABLED  = _bool("PII_REDACTION_ENABLED",  False)  # off until Task 3


# ── Paths ─────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR     = PROJECT_ROOT / "data"


# ── Validation ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=== Settings Check ===")
    print(f"OpenAI key   : {'SET' if HAS_OPENAI else 'MISSING'}")
    print(f"Anthropic key: {'SET' if HAS_ANTHROPIC else 'not set (optional)'}")
    print(f"Text LLM     : {TEXT_LLM}")
    print(f"Vision LLM   : {VISION_LLM}")
    print(f"Embed model  : {EMBED_MODEL} (dim={EMBED_DIM})")
    print(f"Database URL : {DATABASE_URL.replace(POSTGRES_PASSWORD, '****')}")
    print(f"Top-k/type   : {TOP_K_PER_TYPE}  Final top-k: {FINAL_TOP_K}")
    print(f"Feature flags: HYDE={USE_HYDE} DECOMP={USE_QUERY_DECOMPOSITION} CRAG={USE_CRAG} SELF_RAG={USE_SELF_RAG}")
