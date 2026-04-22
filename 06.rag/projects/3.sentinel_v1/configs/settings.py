"""
Central configuration loader.
All config values come from .env or YAML files — nothing is hardcoded.
YAML files are resolved relative to this file's directory.
"""
from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

_CONFIG_DIR = Path(__file__).parent


def _load_yaml(filename: str) -> dict:
    """Load a YAML config file and interpolate ${ENV_VAR} placeholders."""
    path = _CONFIG_DIR / filename
    raw = path.read_text(encoding="utf-8")
    # Replace ${VAR} with actual env values so YAML can reference .env vars
    interpolated = re.sub(
        r"\$\{(\w+)\}",
        lambda m: os.environ.get(m.group(1), m.group(0)),
        raw,
    )
    return yaml.safe_load(interpolated)


class Settings(BaseSettings):
    # ── Ollama ────────────────────────────────────────────────────────────────
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_models: str = Field(default=r"D:\ollama\models")

    # ── LLM APIs ──────────────────────────────────────────────────────────────
    anthropic_api_key: str = Field(default="")
    openai_api_key: str = Field(default="")

    # ── Database ──────────────────────────────────────────────────────────────
    # Set DATABASE_URL directly (Supabase/Neon/cloud) OR use individual fields (local)
    database_url_override: str = Field(default="", alias="DATABASE_URL")
    postgres_host: str = Field(default="localhost")
    postgres_port: int = Field(default=5432)
    postgres_user: str = Field(default="sentinel_user")
    postgres_password: str = Field(default="")
    postgres_db: str = Field(default="sentinel_db")

    # ── Observability ─────────────────────────────────────────────────────────
    langchain_tracing_v2: str = Field(default="false")
    langchain_api_key: str = Field(default="")
    langchain_project: str = Field(default="sentinel-dev")
    langfuse_public_key: str = Field(default="")
    langfuse_secret_key: str = Field(default="")
    langfuse_host: str = Field(default="https://cloud.langfuse.com")

    # ── Security ──────────────────────────────────────────────────────────────
    sentinel_api_key: str = Field(default="")
    pii_redaction_enabled: bool = Field(default=True)
    rate_limit_per_minute: int = Field(default=20)

    # ── Domain & Feature Flags ────────────────────────────────────────────────
    active_domain: str = Field(default="finance")
    enable_bias_detection: bool = Field(default=True)
    enable_parallel_agents: bool = Field(default=True)
    hitl_confidence_threshold: float = Field(default=0.85)
    max_investigation_iterations: int = Field(default=5)

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @field_validator("active_domain")
    @classmethod
    def validate_domain(cls, v: str) -> str:
        allowed = {"finance", "pharma", "generic"}
        if v not in allowed:
            raise ValueError(f"ACTIVE_DOMAIN must be one of {allowed}, got '{v}'")
        return v

    @property
    def database_url(self) -> str:
        # Cloud providers (Supabase, Neon): set DATABASE_URL in .env — takes priority
        if self.database_url_override:
            import re
            url = self.database_url_override
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1).replace(
                "postgres://", "postgresql+asyncpg://", 1
            )
            # Strip sslmode from URL — SQLAlchemy asyncpg dialect rejects it;
            # SSL is enabled via connect_args in the engine (see db/session.py)
            url = re.sub(r"[?&]sslmode=[^&]*", "", url)
            url = re.sub(r"\?$", "", url)
            return url
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        if self.database_url_override:
            url = self.database_url_override
            return url.replace("postgresql+asyncpg://", "postgresql://", 1)
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings singleton — reads .env once at startup."""
    return Settings()


@lru_cache(maxsize=1)
def get_models_config() -> dict[str, Any]:
    return _load_yaml("models.yaml")


@lru_cache(maxsize=1)
def get_agents_config() -> dict[str, Any]:
    return _load_yaml("agents.yaml")


@lru_cache(maxsize=1)
def get_security_config() -> dict[str, Any]:
    return _load_yaml("security.yaml")


@lru_cache(maxsize=1)
def get_domain_config() -> dict[str, Any]:
    domain = get_settings().active_domain
    return _load_yaml(f"domains/{domain}.yaml")


# Module-level singletons for convenient import
settings = get_settings()
models_cfg = get_models_config()
agents_cfg = get_agents_config()
security_cfg = get_security_config()
