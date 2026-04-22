"""Async SQLAlchemy session factory — shared across API and agents."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from configs.settings import settings

_engine = create_async_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,     # Detect stale connections before use
    echo=False,             # Set True for SQL debug logging
)

AsyncSessionFactory = async_sessionmaker(
    bind=_engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Prevent lazy-load errors after commit
    autoflush=False,
)


async def get_db_session() -> AsyncSession:
    """FastAPI dependency — yields a session, commits on success, rolls back on error."""
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
