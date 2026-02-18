"""
Configuration Management System
================================

WHY THIS FILE IS REQUIRED:
    Every non-trivial application needs a single, authoritative source of truth
    for its runtime configuration.  Without this file the application would need
    to scatter `os.getenv(...)` calls across dozens of modules, leading to:
        - duplicated default values that can drift out of sync,
        - missing validation (a typo in a token goes unnoticed until a 3 AM crash),
        - no documentation of what environment variables the app actually needs.
    This module solves all three problems in one place.

PROGRAM LOGIC:
    1. Define a `Settings` class that inherits from pydantic-settings `BaseSettings`.
    2. Each class attribute maps to an environment variable (case-insensitive).
    3. Pydantic reads `.env` on instantiation, coerces types, and raises
       `ValidationError` immediately if anything is wrong ("fail fast").
    4. Custom `@field_validator` methods add domain-specific checks
       (e.g. Slack tokens must start with the correct prefix).
    5. A single module-level `settings` instance is created at import time
       so every other module can simply `from config.settings import settings`.

WHY THIS APPROACH (pydantic-settings):
    - **Type safety at startup**: An `int` field given the string "abc" crashes
      immediately -- not 30 minutes later when the value is first used.
    - **Immutable-like ergonomics**: Attribute access (`settings.port`) is cleaner
      and safer than raw dict/env lookups.
    - **Self-documenting**: Each `Field(description=...)` serves as live
      documentation for new contributors.
    - **Secrets stay out of code**: Values come from `.env` or the OS
      environment; the codebase never contains actual credentials.
    Alternative considered: plain `os.getenv` + dataclasses.  Rejected because
    pydantic-settings gives validation, `.env` loading, and JSON-schema export
    for free.

RELATIONSHIP TO OTHER FILES:
    - Almost every module imports `settings` from here (it is the root of the
      dependency tree for configuration).
    - `src/memory/long_term.py` reads `settings.memory_store_path` to know
      where to persist files on disk.
    - `src/memory/retriever.py` will use `settings.chroma_persist_directory`
      once vector-based RAG is enabled.
    - Slack handler modules read `slack_bot_token`, `slack_app_token`, and
      `slack_signing_secret` to authenticate with the Slack API.
    - The application entrypoint reads `settings.environment` to decide
      between Socket Mode (dev) and HTTP mode (production).

SECURITY CONSIDERATIONS:
    - Required secrets (`slack_bot_token`, `anthropic_api_key`, etc.) use
      `Field(...)` (Ellipsis = required) so the app refuses to start without them.
    - Token format validators (`xoxb-`, `xapp-`) catch copy-paste mistakes
      before they become silent auth failures.
    - `extra="ignore"` in `SettingsConfigDict` prevents accidental exposure of
      unexpected env vars through the settings object.
    - Rate-limit fields (`rate_limit_per_user`, `rate_limit_per_channel`) are
      validated to be strictly positive, blocking misconfiguration that could
      disable rate limiting entirely.
    - The `.env` file should NEVER be committed to version control.  A
      `.env.example` file with placeholder values is the safe pattern.
"""

from typing import Literal, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Main configuration class for the Slack bot assistant.

    All settings are loaded from environment variables (.env file or system env).
    Pydantic automatically validates types and required fields at application startup.

    Design decision -- single class vs. nested sub-models:
        A flat class is used here for simplicity.  As the project grows, you may
        want to break this into nested models (e.g. `SlackConfig`, `MemoryConfig`)
        to keep the namespace clean while still benefiting from one `.env` file.
    """

    # =========================================================================
    # Application Settings
    # =========================================================================
    # WHY: The environment flag lets us toggle behaviour (e.g. verbose logging
    # in dev, HTTP mode in prod) without code changes.  Using a `Literal` type
    # limits the value to exactly two valid strings -- any typo triggers a
    # validation error at startup rather than silently falling through.
    environment: Literal["development", "production"] = Field(
        default="development",
        description="Runtime environment (development or production)"
    )
    # WHY: Centralising the log level here means every logger created by
    # `src/utils/logger.py` can read a single, validated value instead of
    # each module choosing its own default.
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="Logging level for the application"
    )
    # WHY: The HTTP port only matters in production (Socket Mode ignores it).
    # Defaulting to 3000 avoids conflicts with common services on 8080/8000.
    port: int = Field(
        default=3000,
        description="Port for HTTP server (production mode)"
    )

    # =========================================================================
    # Slack Configuration
    # =========================================================================
    # WHY these three tokens are REQUIRED (`...` = no default = must be set):
    #   - `slack_bot_token`: authenticates every Slack Web API call the bot makes.
    #   - `slack_app_token`: opens the persistent WebSocket in Socket Mode.
    #   - `slack_signing_secret`: verifies that incoming HTTP requests genuinely
    #     come from Slack (prevents spoofed events in production HTTP mode).
    # Marking them required ensures the app will not start half-configured.
    slack_bot_token: str = Field(
        ...,  # Required field -- no default, must come from environment
        description="Slack Bot User OAuth Token (xoxb-...)"
    )
    slack_app_token: str = Field(
        ...,  # Required field
        description="Slack App-Level Token for Socket Mode (xapp-...)"
    )
    slack_signing_secret: str = Field(
        ...,  # Required field
        description="Slack Signing Secret for request verification"
    )

    # =========================================================================
    # Anthropic Configuration
    # =========================================================================
    # WHY required: The entire bot revolves around calling Claude.  Without
    # this key nothing works, so we fail immediately if it is missing.
    anthropic_api_key: str = Field(
        ...,  # Required field
        description="Anthropic API key for Claude access"
    )

    # =========================================================================
    # OpenAI Configuration (for embeddings)
    # =========================================================================
    # WHY optional: Embeddings power the semantic-search / RAG pipeline, but
    # the bot can still function (with reduced recall quality) using the
    # keyword-based retriever when no OpenAI key is provided.
    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API key for generating embeddings (optional)"
    )

    # =========================================================================
    # MCP Server Configurations
    # =========================================================================
    # WHY optional: MCP (Model Context Protocol) servers for GitHub and Notion
    # are add-on capabilities.  Making them optional lets operators enable
    # only the integrations they need.
    github_token: Optional[str] = Field(
        default=None,
        description="GitHub Personal Access Token for MCP server (optional)"
    )
    notion_token: Optional[str] = Field(
        default=None,
        description="Notion Integration Token for MCP server (optional)"
    )

    # =========================================================================
    # Database Configuration
    # =========================================================================
    # WHY SQLite as default: Zero-dependency local storage that "just works"
    # on a single machine.  In production, swap this URL for PostgreSQL/MySQL.
    # The connection string format follows SQLAlchemy conventions so the rest
    # of the code does not need to change.
    database_url: str = Field(
        default="sqlite:///./memory_store/agent_state.db",
        description="Database URL for agent state persistence"
    )

    # =========================================================================
    # Redis Configuration (Production)
    # =========================================================================
    # WHY optional: Redis is only needed when multiple bot instances share
    # rate-limit counters in a distributed deployment.  In single-process
    # development mode, in-memory counters are sufficient.
    redis_url: str | None = Field(
        default=None,
        description="Redis URL for distributed rate limiting (production)"
    )

    # =========================================================================
    # RAG Configuration
    # =========================================================================
    # WHY ChromaDB: A lightweight, embeddable vector database that runs
    # in-process.  Good for prototyping; can be replaced with Pinecone /
    # Weaviate / pgvector for production scale.
    chroma_persist_directory: str = Field(
        default="./memory_store/chroma_db",
        description="Directory for ChromaDB persistence"
    )
    # WHY 7200 seconds (2 hours): Balances freshness of indexed messages
    # against CPU/embedding cost.  A shorter interval wastes tokens; a longer
    # one makes recent messages invisible to semantic search.
    rag_indexing_frequency: int = Field(
        default=7200,  # 2 hours in seconds
        description="Frequency of RAG indexing in seconds"
    )
    # WHY 200: Caps the number of Slack messages fetched per channel during
    # each indexing pass, keeping API usage and embedding costs predictable.
    rag_message_limit: int = Field(
        default=200,
        description="Number of messages per channel to index"
    )

    # =========================================================================
    # Security Settings
    # =========================================================================
    # WHY rate limiting: Without it, a single user or channel could exhaust
    # the Anthropic API quota (and budget) in minutes.  Per-user and
    # per-channel limits provide two layers of defence.
    rate_limit_per_user: int = Field(
        default=10,
        description="Maximum requests per minute per user"
    )
    rate_limit_per_channel: int = Field(
        default=30,
        description="Maximum requests per minute per channel"
    )
    # WHY token rotation: Long-lived tokens are a security risk.  This field
    # drives a periodic reminder (not automatic rotation) so operators can
    # manually rotate tokens before they become stale.
    token_rotation_days: int = Field(
        default=7,
        description="Days before token rotation reminder"
    )

    # =========================================================================
    # Memory Configuration
    # =========================================================================
    # WHY a configurable path: Different environments (CI, Docker, bare-metal)
    # may need different storage locations.  A default of `./memory_store`
    # keeps development simple while allowing production overrides.
    memory_store_path: str = Field(
        default="./memory_store",
        description="Base path for file-backed memory storage"
    )
    # WHY cron-based distillation: Over time, daily logs accumulate raw
    # conversation data.  A weekly distillation job summarises and compresses
    # them into MEMORY.md, preventing unbounded growth of the retrieval corpus.
    # The cron expression "0 0 * * 0" means "every Sunday at midnight UTC".
    memory_distillation_cron: str = Field(
        default="0 0 * * 0",  # Weekly on Sunday at midnight
        description="Cron expression for memory distillation schedule"
    )

    # =========================================================================
    # Model Configuration (Pydantic Settings)
    # =========================================================================
    # WHY `SettingsConfigDict`:
    #   - `env_file=".env"` -- loads a local dotenv file so developers don't
    #     need to export variables manually.
    #   - `case_sensitive=False` -- `SLACK_BOT_TOKEN` and `slack_bot_token`
    #     both work, reducing frustration from case mismatches.
    #   - `extra="ignore"` -- any env var NOT declared above is silently
    #     skipped instead of causing a validation error.  This is important
    #     because the OS environment always contains unrelated variables
    #     (PATH, HOME, etc.).
    model_config = SettingsConfigDict(
        env_file=".env",  # Load from .env file
        env_file_encoding="utf-8",
        case_sensitive=False,  # Allow case-insensitive env var names
        extra="ignore",  # Ignore extra environment variables
    )

    # =========================================================================
    # Validators
    # =========================================================================

    @field_validator("slack_bot_token")
    @classmethod
    def validate_bot_token(cls, v: str) -> str:
        """
        Validate Slack bot token format.

        WHY: Slack bot tokens always start with 'xoxb-'.  Catching a wrong
        prefix here gives the operator a clear error message at startup instead
        of a cryptic 401 from the Slack API minutes later.

        SECURITY: This is NOT a substitute for verifying the token against
        Slack's servers -- it only checks the prefix format.
        """
        if not v.startswith("xoxb-"):
            raise ValueError("Slack bot token must start with 'xoxb-'")
        return v

    @field_validator("slack_app_token")
    @classmethod
    def validate_app_token(cls, v: str) -> str:
        """
        Validate Slack app token format.

        WHY: App-level tokens start with 'xapp-'.  Same rationale as above --
        fast feedback on misconfiguration.
        """
        if not v.startswith("xapp-"):
            raise ValueError("Slack app token must start with 'xapp-'")
        return v

    @field_validator("github_token")
    @classmethod
    def validate_github_token(cls, v: Optional[str]) -> Optional[str]:
        """
        Validate GitHub token format when provided.

        WHY: GitHub supports several token formats:
          - ghp_  : classic Personal Access Token
          - github_pat_ : fine-grained Personal Access Token
          - gho_  : OAuth access token
          - ghu_  : user-to-server token
          - ghs_  : server-to-server token
        Catching an unrecognised prefix at startup prevents silent 401 failures.
        """
        if v is None:
            return v
        valid_prefixes = ("ghp_", "github_pat_", "gho_", "ghu_", "ghs_")
        if not v.startswith(valid_prefixes):
            import warnings
            warnings.warn(
                f"GitHub token does not start with a known prefix {valid_prefixes}. "
                "It may be expired or invalid. Verify at https://github.com/settings/tokens"
            )
        return v

    @field_validator("rate_limit_per_user", "rate_limit_per_channel")
    @classmethod
    def validate_positive(cls, v: int) -> int:
        """
        Ensure rate limits are positive.

        WHY: A rate limit of 0 or negative would either block all requests or
        disable limiting entirely, both of which are dangerous.  Catching this
        at startup prevents accidental denial-of-service or budget overrun.
        """
        if v <= 0:
            raise ValueError("Rate limits must be positive integers")
        return v

    # =========================================================================
    # Computed Properties
    # =========================================================================
    # WHY properties instead of additional fields:
    # These values are *derived* from `environment`.  Storing them as regular
    # fields would create two sources of truth that could disagree.  Properties
    # guarantee consistency because they always re-compute from the canonical
    # `environment` value.

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment == "development"

    @property
    def use_socket_mode(self) -> bool:
        """
        Use Socket Mode in development, HTTP in production.

        WHY: Socket Mode opens an outbound WebSocket so the bot works behind
        NAT / firewalls without a public URL -- perfect for local dev.
        Production deployments expose an HTTP endpoint behind a load balancer,
        which is more scalable and observable.
        """
        return self.is_development


# ============================================================================
# Global Settings Instance (Singleton Pattern)
# ============================================================================
# WHY a module-level singleton:
#   Python modules are imported once and cached in `sys.modules`.  By creating
#   `settings` here, every module that does `from config.settings import settings`
#   shares the exact same object -- no duplicate validation, no inconsistent
#   values.  This is effectively the "Borg" singleton pattern without the
#   boilerplate.
#
# WHY the try/except:
#   If `.env` is missing required variables, Pydantic raises a `ValidationError`
#   with a list of every missing or invalid field.  Wrapping the instantiation
#   in try/except lets us print a human-friendly message (with a pointer to
#   `.env.example`) before the traceback kills the process.
#
# SECURITY NOTE:
#   The `settings` object holds all secrets in memory for the lifetime of the
#   process.  Avoid logging or serialising this object.  If you need to expose
#   configuration (e.g. in a health endpoint), create a sanitised view that
#   excludes secrets.
# ============================================================================

try:
    settings = Settings()
except Exception as e:
    print(f"❌ Configuration Error: {e}")
    print("Please check your .env file and ensure all required variables are set.")
    print("See .env.example for reference.")
    raise
