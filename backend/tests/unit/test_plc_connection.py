import pytest

from app.plc.base import ConnectionState
from app.plc.connection import ResilientPLCConnection
from app.plc.simulator import SimulatedPLCClient

pytestmark = pytest.mark.asyncio


async def test_ensure_connected_succeeds_and_reports_state():
    client = SimulatedPLCClient()
    states: list[ConnectionState] = []

    async def on_state_change(state: ConnectionState) -> None:
        states.append(state)

    conn = ResilientPLCConnection(client, on_state_change=on_state_change)
    assert await conn.ensure_connected() is True
    assert conn.state == ConnectionState.CONNECTED
    assert states == [ConnectionState.CONNECTING, ConnectionState.CONNECTED]


async def test_ensure_connected_is_a_noop_once_already_connected():
    client = SimulatedPLCClient()
    conn = ResilientPLCConnection(client)
    await conn.ensure_connected()
    # second call shouldn't re-trigger a connect() (is_connected() short-circuits)
    assert await conn.ensure_connected() is True
    assert conn.state == ConnectionState.CONNECTED


async def test_ensure_connected_backs_off_on_failure():
    client = SimulatedPLCClient()
    client.set_force_disconnected(True)
    states: list[ConnectionState] = []

    async def on_state_change(state: ConnectionState) -> None:
        states.append(state)

    conn = ResilientPLCConnection(client, backoff_schedule=(0.01, 0.02), on_state_change=on_state_change)
    assert await conn.ensure_connected() is False
    assert conn.state == ConnectionState.ERROR
    assert states == [ConnectionState.CONNECTING, ConnectionState.ERROR]


async def test_recovers_after_plc_comes_back_online():
    client = SimulatedPLCClient()
    client.set_force_disconnected(True)
    conn = ResilientPLCConnection(client, backoff_schedule=(0.01,))

    assert await conn.ensure_connected() is False
    client.set_force_disconnected(False)
    assert await conn.ensure_connected() is True
    assert conn.state == ConnectionState.CONNECTED
