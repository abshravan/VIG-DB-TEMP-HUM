import asyncio
from datetime import datetime

import pytest

from app.plc.connection import ResilientPLCConnection
from app.plc.poller import PLCPoller
from app.plc.simulator import SimulatedPLCClient
from app.plc.tags import TagMap

pytestmark = pytest.mark.asyncio

TAG_MAP = TagMap.model_validate(
    {
        "poll_intervals": {"fast": 0.02, "normal": 0.08},
        "tags": [
            {
                "name": "temp_a",
                "kind": "analog",
                "sensor_type": "TEMPERATURE",
                "poll_tier": "normal",
                "s7": {"db": 1, "offset": 0, "type": "REAL"},
                "scale": {"raw_min": 0, "raw_max": 100, "eng_min": 0, "eng_max": 50, "unit": "°C"},
            },
            {
                "name": "door_a",
                "kind": "digital",
                "sensor_type": "DOOR",
                "poll_tier": "fast",
                "s7": {"db": 1, "offset": 8, "type": "BOOL", "bit": 0},
            },
        ],
    }
)


async def test_poller_invokes_callback_for_both_tiers():
    client = SimulatedPLCClient()
    connection = ResilientPLCConnection(client)
    calls: list[tuple[set[str], datetime]] = []

    async def on_readings(results, timestamp) -> None:
        calls.append((set(results.keys()), timestamp))

    poller = PLCPoller(connection, TAG_MAP, on_readings)
    await poller.start()
    try:
        await asyncio.sleep(0.15)
    finally:
        await poller.stop()

    tag_names_seen = {name for names, _ in calls for name in names}
    assert tag_names_seen == {"temp_a", "door_a"}
    # fast tier (0.02s) should have produced noticeably more calls than normal tier alone
    assert len(calls) >= 2


async def test_poller_keeps_running_across_disconnects():
    client = SimulatedPLCClient()
    connection = ResilientPLCConnection(client, backoff_schedule=(0.01,))
    call_count = 0

    async def on_readings(results, timestamp) -> None:
        nonlocal call_count
        call_count += 1

    poller = PLCPoller(connection, TAG_MAP, on_readings)
    await poller.start()
    await asyncio.sleep(0.05)
    client.set_force_disconnected(True)
    await asyncio.sleep(0.05)
    count_while_down = call_count
    client.set_force_disconnected(False)
    await asyncio.sleep(0.08)

    await poller.stop()
    assert call_count > count_while_down
