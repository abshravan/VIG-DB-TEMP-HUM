import pytest

from app.realtime.connection_manager import ConnectionManager

pytestmark = pytest.mark.asyncio


class FakeWebSocket:
    """Duck-typed stand-in for `fastapi.WebSocket` — enough surface for ConnectionManager,
    without any real ASGI/ASGI-transport/threading involved (see test_ws_live.py's module
    docstring for why real WebSocket connections are tested separately, as plain sync tests).
    """

    def __init__(self, *, fail_on_send: bool = False) -> None:
        self.accepted = False
        self.sent: list[dict] = []
        self._fail_on_send = fail_on_send

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, message: dict) -> None:
        if self._fail_on_send:
            raise RuntimeError("connection is gone")
        self.sent.append(message)


async def test_connect_registers_an_already_accepted_connection():
    # accept() is the caller's responsibility (it must happen before the auth handshake in
    # /ws/live), not ConnectionManager's — see connection_manager.py's connect() docstring.
    manager = ConnectionManager()
    ws = FakeWebSocket()
    await ws.accept()

    await manager.connect(ws)

    assert manager.connection_count == 1


async def test_disconnect_removes_connection():
    manager = ConnectionManager()
    ws = FakeWebSocket()
    await manager.connect(ws)

    await manager.disconnect(ws)

    assert manager.connection_count == 0


async def test_disconnect_of_unknown_connection_is_a_noop():
    manager = ConnectionManager()
    await manager.disconnect(FakeWebSocket())  # never connected
    assert manager.connection_count == 0


async def test_broadcast_sends_to_every_connected_client():
    manager = ConnectionManager()
    ws1, ws2 = FakeWebSocket(), FakeWebSocket()
    await manager.connect(ws1)
    await manager.connect(ws2)

    await manager.broadcast({"type": "reading", "data": {"value": 1}})

    assert ws1.sent == [{"type": "reading", "data": {"value": 1}}]
    assert ws2.sent == [{"type": "reading", "data": {"value": 1}}]


async def test_broadcast_drops_dead_connections_without_affecting_others():
    manager = ConnectionManager()
    dead = FakeWebSocket(fail_on_send=True)
    alive = FakeWebSocket()
    await manager.connect(dead)
    await manager.connect(alive)

    await manager.broadcast({"type": "plc_status", "data": {"connected": False}})

    assert alive.sent == [{"type": "plc_status", "data": {"connected": False}}]
    assert manager.connection_count == 1  # the dead one was pruned


async def test_broadcast_with_no_connections_does_not_raise():
    manager = ConnectionManager()
    await manager.broadcast({"type": "alarm", "data": {}})
