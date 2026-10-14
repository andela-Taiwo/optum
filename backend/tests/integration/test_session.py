"""Integration tests for the database layer.

These need a real Postgres. Start it with:
    docker compose up -d postgres
"""

from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base
from app.db.session import get_engine, get_session, get_sessionmaker

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
async def _fresh_engine() -> AsyncIterator[None]:
    """Dispose the cached engine around every test.

    get_engine is lru_cached so one pool exists per process — correct in
    production, but pytest-asyncio runs each test in a new event loop, and
    connections pooled under a closed loop raise "Event loop is closed" when
    the next test checks them out.

    Both caches are cleared: the sessionmaker holds a reference to the
    engine, so clearing only the engine cache leaves a factory bound to a
    disposed pool.
    """
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()
    yield
    await get_engine().dispose()
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()


async def test_engine_connects_to_postgres() -> None:
    engine = get_engine()

    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        assert result.scalar_one() == 1


async def test_engine_is_async_and_uses_asyncpg() -> None:
    """A sync driver here would block the event loop under load."""
    engine = get_engine()

    assert engine.dialect.is_async is True
    assert "asyncpg" in engine.url.drivername


async def test_sessionmaker_yields_async_session() -> None:
    session_factory = get_sessionmaker()

    async with session_factory() as session:
        assert isinstance(session, AsyncSession)
        result = await session.execute(text("SELECT current_database()"))
        assert result.scalar_one() is not None


async def test_get_session_dependency_yields_and_closes() -> None:
    """get_session is a FastAPI dependency: it must yield, then clean up."""
    agen = get_session()
    session = await anext(agen)

    assert isinstance(session, AsyncSession)
    result = await session.execute(text("SELECT 1"))
    assert result.scalar_one() == 1

    # Exhausting the generator runs the teardown half.
    with pytest.raises(StopAsyncIteration):
        await anext(agen)

    # A closed session has handed its connection back to the pool.
    # `is_active` is the wrong probe here: it reports "not in a failed
    # transaction", which stays True on a cleanly closed session.
    assert session.get_transaction() is None


async def test_failed_request_leaves_pool_usable() -> None:
    """A request that raises mid-transaction must not poison the pool.

    This asserts the property that actually matters — the next request gets a
    working connection — rather than inspecting session internals. Note that
    SQLAlchemy's session context manager already rolls back inside close(),
    so this passes with or without get_session's explicit rollback; the
    explicit call is defensive clarity, not the mechanism under test.
    """
    agen = get_session()
    session = await anext(agen)
    await session.execute(text("CREATE TEMP TABLE rollback_probe (id int)"))
    await session.execute(text("INSERT INTO rollback_probe VALUES (1)"))

    with pytest.raises(RuntimeError):
        await agen.athrow(RuntimeError("boom"))

    assert session.get_transaction() is None

    # A fresh session must work, and must not see the aborted temp table.
    async with get_sessionmaker()() as next_session:
        result = await next_session.execute(text("SELECT 1"))
        assert result.scalar_one() == 1
        exists = await next_session.execute(
            text("SELECT to_regclass('rollback_probe') IS NOT NULL")
        )
        assert exists.scalar_one() is False


async def test_naming_convention_is_configured() -> None:
    """Without this, Alembic autogenerate emits unnamed constraints that
    cannot be dropped in a downgrade."""
    convention = Base.metadata.naming_convention

    for key in ("ix", "uq", "ck", "fk", "pk"):
        assert key in convention, f"missing naming convention for {key!r}"
    assert "%(table_name)s" in convention["pk"]


async def test_base_has_no_tables_yet() -> None:
    """Sanity check: models arrive in 1.4. If this fails, something imported
    a model and the metadata is no longer empty."""
    assert Base.metadata.tables == {}
