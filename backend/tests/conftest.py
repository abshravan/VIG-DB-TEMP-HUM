from collections.abc import AsyncGenerator

import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models import *  # noqa: F401,F403 — ensure every model is registered on Base.metadata


@pytest_asyncio.fixture
async def session_maker() -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """Fresh in-memory SQLite DB per test, full schema created from the ORM models (not a
    fixture file) so schema drift between models and tests is impossible. Yields a session
    *factory* bound to that one engine — needed by anything (like the ingestion pipeline)
    that opens more than one session against the same schema within a test.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_fk(dbapi_connection, connection_record) -> None:  # noqa: ANN001, ARG001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    await engine.dispose()


@pytest_asyncio.fixture
async def session(session_maker: async_sessionmaker[AsyncSession]) -> AsyncGenerator[AsyncSession, None]:
    """Single session for tests that only ever need one (the common case)."""
    async with session_maker() as s:
        yield s
