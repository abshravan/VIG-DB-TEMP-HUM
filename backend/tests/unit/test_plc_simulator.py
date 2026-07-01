import pytest

from app.plc.simulator import SimulatedPLCClient
from app.plc.tags import TagDefinition

pytestmark = pytest.mark.asyncio

ANALOG_TAG = TagDefinition(
    name="temp_a",
    kind="analog",
    sensor_type="TEMPERATURE",
    poll_tier="normal",
    s7={"db": 1, "offset": 0, "type": "REAL"},
    scale={"raw_min": 0, "raw_max": 100, "eng_min": 0, "eng_max": 50, "unit": "°C"},
)
DIGITAL_TAG = TagDefinition(
    name="door_a",
    kind="digital",
    sensor_type="DOOR",
    poll_tier="fast",
    s7={"db": 1, "offset": 8, "type": "BOOL", "bit": 0},
)


async def test_read_tags_requires_connection():
    client = SimulatedPLCClient()
    with pytest.raises(ConnectionError):
        await client.read_tags([ANALOG_TAG])


async def test_connect_and_read_returns_ok_results():
    client = SimulatedPLCClient(seed=1)
    await client.connect()
    assert client.is_connected()

    results = await client.read_tags([ANALOG_TAG, DIGITAL_TAG])
    assert results[ANALOG_TAG.name].ok is True
    assert results[DIGITAL_TAG.name].ok is True
    assert results[DIGITAL_TAG.name].value is False


async def test_set_value_pins_reading():
    client = SimulatedPLCClient()
    await client.connect()
    client.set_value(ANALOG_TAG.name, 42.0)

    results = await client.read_tags([ANALOG_TAG])
    # a single drift step keeps it close to the pinned value, not identical
    assert results[ANALOG_TAG.name].value == pytest.approx(42.0, abs=0.5)


async def test_force_disconnected_blocks_reconnect():
    client = SimulatedPLCClient()
    client.set_force_disconnected(True)
    with pytest.raises(ConnectionError):
        await client.connect()
    assert not client.is_connected()

    client.set_force_disconnected(False)
    await client.connect()
    assert client.is_connected()


async def test_failing_tag_reports_error_without_affecting_others():
    client = SimulatedPLCClient()
    await client.connect()
    client.set_tag_failing(ANALOG_TAG.name, True)

    results = await client.read_tags([ANALOG_TAG, DIGITAL_TAG])
    assert results[ANALOG_TAG.name].ok is False
    assert results[ANALOG_TAG.name].error is not None
    assert results[DIGITAL_TAG.name].ok is True


async def test_get_value_reflects_pinned_and_unset_tags():
    client = SimulatedPLCClient()
    assert client.get_value(ANALOG_TAG.name) is None

    client.set_value(ANALOG_TAG.name, 42.0)
    assert client.get_value(ANALOG_TAG.name) == 42.0


async def test_is_tag_failing_reflects_set_tag_failing():
    client = SimulatedPLCClient()
    assert client.is_tag_failing(ANALOG_TAG.name) is False

    client.set_tag_failing(ANALOG_TAG.name, True)
    assert client.is_tag_failing(ANALOG_TAG.name) is True

    client.set_tag_failing(ANALOG_TAG.name, False)
    assert client.is_tag_failing(ANALOG_TAG.name) is False
