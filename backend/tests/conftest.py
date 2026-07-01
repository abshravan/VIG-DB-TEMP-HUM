from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import create_app
from app.models import *  # noqa: F401,F403 — ensure every model is registered on Base.metadata
from app.models.enums import UserRole
from app.models.user import User
from app.repositories import UserRepository


async def build_session_maker() -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Plain async helper (not a fixture) so both the `session_maker` pytest fixture *and*
    the WebSocket tests (which must run as plain sync functions — see test_ws_live.py's
    module docstring for why — and so drive this via `asyncio.run` instead of fixture
    injection) can build an identical fresh in-memory DB.
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

    return engine, async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def session_maker() -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """Fresh in-memory SQLite DB per test, full schema created from the ORM models (not a
    fixture file) so schema drift between models and tests is impossible. Yields a session
    *factory* bound to that one engine — needed by anything (like the ingestion pipeline)
    that opens more than one session against the same schema within a test.
    """
    engine, maker = await build_session_maker()
    yield maker
    await engine.dispose()


@pytest_asyncio.fixture
async def session(session_maker: async_sessionmaker[AsyncSession]) -> AsyncGenerator[AsyncSession, None]:
    """Single session for tests that only ever need one (the common case)."""
    async with session_maker() as s:
        yield s


@pytest_asyncio.fixture
async def api_client(
    session_maker: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncClient, None]:
    """An httpx client against the real FastAPI app with `get_db` overridden to the test's
    in-memory DB. Deliberately does *not* enter the app's lifespan (no `LifespanManager`) —
    that would try to build a real PLCClient and start polling a real (nonexistent, in tests)
    PLC, which is out of scope for testing REST endpoint behavior. `app.state.plc_connection`
    is simply absent, and every endpoint that reads it already falls back to "disconnected".
    """
    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db(session_maker)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        client.app = app  # lets tests reach app.state (e.g. to install a fake plc_connection)
        yield client


def _override_get_db(session_maker: async_sessionmaker[AsyncSession]):
    async def _get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    return _get_db


async def create_user(
    session_maker: async_sessionmaker[AsyncSession], username: str, password: str, role: UserRole
) -> User:
    async with session_maker() as session:
        user = await UserRepository(session).create(
            User(username=username, hashed_password=hash_password(password), role=role)
        )
        await session.commit()
        return user


async def login_headers(client: AsyncClient, username: str, password: str) -> dict[str, str]:
    response = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    response.raise_for_status()
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
