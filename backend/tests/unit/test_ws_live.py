"""WebSocket tests for /ws/live.

These are deliberately plain sync `def test_...()` functions, not `async def` — Starlette's
`TestClient.websocket_connect()` runs the ASGI app in a background thread with its own event
loop (an anyio "blocking portal"). Driving it from inside a pytest-asyncio `async def` test
(which already has a running event loop on the main thread) deadlocks the moment the server
side of the connection stays open (confirmed empirically: even a bare connect-then-exit hangs
indefinitely). Plain sync tests avoid the nested-loop hazard entirely; async setup/broadcast
calls use `asyncio.run(...)`, each a self-contained event loop that starts and fully tears
down before the next line runs.

Auth is a first-message handshake (send `{"token": "..."}` right after connecting), not a
`?token=` query param — see app/realtime/router.py's docstring for why. The transport-level
`websocket_connect()` call itself always succeeds now (the server always accepts before
authenticating); rejection shows up as a `WebSocketDisconnect` on the next send/receive.
"""

import asyncio

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

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


def _wait_for_connection_count(manager, expected: int) -> None:
    """Auth happens asynchronously on the server (in the TestClient's own portal thread), so
    `manager.connection_count` doesn't update the instant `send_json` returns — poll briefly
    rather than assuming synchrony.
    """
    for _ in range(50):
        if manager.connection_count == expected:
            return
        asyncio.run(asyncio.sleep(0.02))
    raise AssertionError(f"connection_count never reached {expected}, was {manager.connection_count}")


def _assert_rejected(client: TestClient, send: callable) -> None:
    """Connects, lets `send` push whatever first message the test wants, then confirms the
    server closed the connection (surfaced as WebSocketDisconnect) rather than accepting it.
    """
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/live") as websocket:
            send(websocket)
            websocket.receive_text()


def test_ws_rejects_first_message_with_no_token_field():
    app, _session_maker, engine = _new_app_with_db()
    client = TestClient(app)
    try:
        _assert_rejected(client, lambda ws: ws.send_json({}))
    finally:
        _dispose(engine)


def test_ws_rejects_invalid_token():
    app, _session_maker, engine = _new_app_with_db()
    client = TestClient(app)
    try:
        _assert_rejected(client, lambda ws: ws.send_json({"token": "not-a-real-token"}))
    finally:
        _dispose(engine)


def test_ws_rejects_refresh_token_used_as_access_token():
    app, session_maker, engine = _new_app_with_db()
    try:
        asyncio.run(create_user(session_maker, "viewer", "pw12345678", UserRole.VIEWER))
        refresh_token = create_refresh_token("viewer", "VIEWER")
        client = TestClient(app)
        _assert_rejected(client, lambda ws: ws.send_json({"token": refresh_token}))
    finally:
        _dispose(engine)


def test_ws_rejects_unknown_user():
    app, _session_maker, engine = _new_app_with_db()
    try:
        token = create_access_token("nobody", "VIEWER")
        client = TestClient(app)
        _assert_rejected(client, lambda ws: ws.send_json({"token": token}))
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
        _assert_rejected(client, lambda ws: ws.send_json({"token": token}))
    finally:
        _dispose(engine)


def test_ws_accepts_valid_token_and_receives_broadcast():
    app, session_maker, engine = _new_app_with_db()
    try:
        asyncio.run(create_user(session_maker, "viewer", "pw12345678", UserRole.VIEWER))
        token = create_access_token("viewer", "VIEWER")
        client = TestClient(app)

        with client.websocket_connect("/ws/live") as websocket:
            websocket.send_json({"token": token})
            manager = app.state.connection_manager
            _wait_for_connection_count(manager, 1)
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

        with client.websocket_connect("/ws/live") as websocket:
            websocket.send_json({"token": token})
            _wait_for_connection_count(manager, 1)

        assert manager.connection_count == 0
    finally:
        _dispose(engine)


## Broadcasting to *multiple* real WS clients isn't tested here: each real client's DB
## session runs against the shared StaticPool in-memory connection, but through a *separate*
## portal thread per `websocket_connect()` call — two portal threads driving the one aiosqlite
## connection concurrently is a test-infrastructure hazard (not a ConnectionManager bug). That
## behavior is covered directly, without any of this, in test_connection_manager.py.
