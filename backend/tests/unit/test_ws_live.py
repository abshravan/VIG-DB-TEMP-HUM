"""WebSocket tests for /ws/live.

These are deliberately plain sync `def test_...()` functions, not `async def` — Starlette's
`TestClient.websocket_connect()` runs the ASGI app in a background thread with its own event
loop (an anyio "blocking portal"). Driving it from inside a pytest-asyncio `async def` test
(which already has a running event loop on the main thread) deadlocks the moment the server
side of the connection stays open (confirmed empirically: even a bare connect-then-exit hangs
indefinitely). Plain sync tests avoid the nested-loop hazard entirely; async setup/broadcast
calls use `asyncio.run(...)`, each a self-contained event loop that starts and fully tears
down before the next line runs.
"""

import asyncio

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import get_db
from app.core.security import create_access_token, create_refresh_token
from app.main import create_app
from app.models.enums import UserRole
from app.repositories import UserRepository
from tests.conftest import build_session_maker, create_user


def _new_app_with_db() -> tuple:
    """Fresh in-memory DB + FastAPI app (get_db overridden) for one test."""
    engine, session_maker = asyncio.run(build_session_maker())
    app = create_app()

    async def override_get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    return app, session_maker, engine


def _dispose(engine) -> None:
    asyncio.run(engine.dispose())


def test_ws_rejects_connection_without_token():
    app, _session_maker, engine = _new_app_with_db()
    client = TestClient(app)
    try:
        raised = False
        try:
            with client.websocket_connect("/ws/live"):
                pass
        except Exception:
            raised = True
        assert raised
    finally:
        _dispose(engine)


def test_ws_rejects_invalid_token():
    app, _session_maker, engine = _new_app_with_db()
    client = TestClient(app)
    try:
        raised = False
        try:
            with client.websocket_connect("/ws/live?token=not-a-real-token"):
                pass
        except Exception:
            raised = True
        assert raised
    finally:
        _dispose(engine)


def test_ws_rejects_refresh_token_used_as_access_token():
    app, session_maker, engine = _new_app_with_db()
    try:
        asyncio.run(create_user(session_maker, "viewer", "pw12345678", UserRole.VIEWER))
        refresh_token = create_refresh_token("viewer", "VIEWER")
        client = TestClient(app)
        raised = False
        try:
            with client.websocket_connect(f"/ws/live?token={refresh_token}"):
                pass
        except Exception:
            raised = True
        assert raised
    finally:
        _dispose(engine)


def test_ws_rejects_unknown_user():
    app, _session_maker, engine = _new_app_with_db()
    try:
        token = create_access_token("nobody", "VIEWER")
        client = TestClient(app)
        raised = False
        try:
            with client.websocket_connect(f"/ws/live?token={token}"):
                pass
        except Exception:
            raised = True
        assert raised
    finally:
        _dispose(engine)


def test_ws_rejects_inactive_user():
    app, session_maker, engine = _new_app_with_db()
    try:
        user = asyncio.run(create_user(session_maker, "disabled", "pw12345678", UserRole.VIEWER))

        async def deactivate():
            async with session_maker() as session:
                db_user = await UserRepository(session).get(user.id)
                db_user.is_active = False
                await session.commit()

        asyncio.run(deactivate())

        token = create_access_token("disabled", "VIEWER")
        client = TestClient(app)
        raised = False
        try:
            with client.websocket_connect(f"/ws/live?token={token}"):
                pass
        except Exception:
            raised = True
        assert raised
    finally:
        _dispose(engine)


def test_ws_accepts_valid_token_and_receives_broadcast():
    app, session_maker, engine = _new_app_with_db()
    try:
        asyncio.run(create_user(session_maker, "viewer", "pw12345678", UserRole.VIEWER))
        token = create_access_token("viewer", "VIEWER")
        client = TestClient(app)

        with client.websocket_connect(f"/ws/live?token={token}") as websocket:
            manager = app.state.connection_manager
            assert manager.connection_count == 1
            asyncio.run(manager.broadcast({"type": "reading", "data": {"sensor_id": 1, "value": 22.5}}))
            message = websocket.receive_json()
            assert message == {"type": "reading", "data": {"sensor_id": 1, "value": 22.5}}
    finally:
        _dispose(engine)


def test_ws_disconnect_removes_connection_from_manager():
    app, session_maker, engine = _new_app_with_db()
    try:
        asyncio.run(create_user(session_maker, "viewer", "pw12345678", UserRole.VIEWER))
        token = create_access_token("viewer", "VIEWER")
        client = TestClient(app)
        manager = app.state.connection_manager

        with client.websocket_connect(f"/ws/live?token={token}"):
            assert manager.connection_count == 1

        assert manager.connection_count == 0
    finally:
        _dispose(engine)


## Broadcasting to *multiple* real WS clients isn't tested here: each real client's DB
## session runs against the shared StaticPool in-memory connection, but through a *separate*
## portal thread per `websocket_connect()` call — two portal threads driving the one aiosqlite
## connection concurrently is a test-infrastructure hazard (not a ConnectionManager bug). That
## behavior is covered directly, without any of this, in test_connection_manager.py.
