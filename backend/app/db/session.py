# app/db/session.py
"""
Async SQLAlchemy engine and session factory.

Uses asyncpg. `get_db` is the FastAPI dependency that yields a session
per request and guarantees it's closed even on error.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


engine = create_async_engine(
    str(settings.DATABASE_URL).replace("postgresql://", "postgresql+asyncpg://"),
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,  # drop dead connections rather than erroring mid-request
    # Supabase's pooler runs in transaction mode, which does not support
    # prepared statements. Disabling asyncpg's statement cache (and giving
    # each statement a unique name) is required when connecting through it.
    connect_args={
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    },
    echo=settings.DEBUG,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # keeps objects usable after commit
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
