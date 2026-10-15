from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    """The process-wide engine, created once.

    Cached because an engine owns a connection pool. Building one per call —
    or per request — opens a new pool each time and exhausts Postgres's
    max_connections under very little load.
    """
    settings = get_settings()

    return create_async_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        # Costs one round trip per checkout, but a connection killed by a
        # restart or an idle timeout otherwise surfaces as a random
        # OperationalError on an unrelated request.
        pool_pre_ping=True,
        # Recycle below typical proxy/firewall idle timeouts.
        pool_recycle=1800,
        echo=settings.debug,
    )


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Session factory bound to the shared engine.

    Deliberately `def`, not `async def`: async_sessionmaker is a synchronous
    constructor. Marking it async returns a coroutine, and
    `async with get_sessionmaker()` then fails with "'coroutine' object does
    not support the asynchronous context manager protocol".
    """
    return async_sessionmaker(
        bind=get_engine(),
        class_=AsyncSession,
        autoflush=False,
        # With the default True, attribute access after commit triggers a
        # refresh SELECT. Under asyncio that lazy load raises MissingGreenlet
        # far from its cause.
        expire_on_commit=False,
    )


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a session scoped to one request.

    Rolls back explicitly on failure: `async with` alone closes the session
    but leaves the transaction in a failed state, and the pooled connection
    is then handed to the next request mid-abort.

    Commits are the caller's responsibility — a dependency that
    auto-commits turns a half-finished request into a persisted one.
    """
    session_factory = get_sessionmaker()

    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
