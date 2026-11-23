"""
arq job queue settings for SENTINEL worker (Phase 4).

Worker runs background investigations via Redis task queue.
Configuration loaded from REDIS_URL environment variable.
"""
import os

from arq.connections import RedisSettings


def get_redis_settings() -> RedisSettings:
    """
    Load Redis connection settings from REDIS_URL env var.

    Expected format: redis://[password@]host:port/[db]
    Examples:
      redis://localhost:6379
      redis://user:password@redis.example.com:6379
      redis://:password@redis.example.com:6379

    Returns: arq.connections.RedisSettings for worker initialization.
    """
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

    # Parse URL components (simple parser, assumes standard Redis URL format)
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(redis_url)

    host = parsed.hostname or "localhost"
    port = parsed.port or 6379
    db = int(parsed.path.lstrip("/") or 0)
    password = parsed.password

    return RedisSettings(
        host=host,
        port=port,
        database=db,
        password=password,
        conn_timeout=5,
        conn_retries=3,
    )
