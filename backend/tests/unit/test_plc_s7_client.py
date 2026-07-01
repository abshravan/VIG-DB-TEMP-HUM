import struct
from unittest.mock import MagicMock, patch

import pytest

from app.plc.s7_client import S7PLCClient
from app.plc.tags import TagDefinition

pytestmark = pytest.mark.asyncio

REAL_TAG = TagDefinition(
    name="temp_a",
    kind="analog",
    sensor_type="TEMPERATURE",
    poll_tier="normal",
    s7={"db": 10, "offset": 0, "type": "REAL"},
    scale={"raw_min": 0, "raw_max": 100, "eng_min": 0, "eng_max": 50, "unit": "°C"},
)
BOOL_TAG = TagDefinition(
    name="door_a",
    kind="digital",
    sensor_type="DOOR",
    poll_tier="fast",
    s7={"db": 10, "offset": 8, "type": "BOOL", "bit": 2},
)


@pytest.fixture
def mock_snap7_client():
    with patch("app.plc.s7_client.snap7.client.Client") as mock_cls:
        instance = MagicMock()
        mock_cls.return_value = instance
        yield instance


async def test_connect_and_disconnect_delegate_to_snap7(mock_snap7_client):
    client = S7PLCClient(address="10.0.0.5")
    await client.connect()
    mock_snap7_client.connect.assert_called_once_with("10.0.0.5", 0, 1, 102)

    await client.disconnect()
    mock_snap7_client.disconnect.assert_called_once()


async def test_is_connected_reflects_snap7_state(mock_snap7_client):
    client = S7PLCClient(address="10.0.0.5")

    mock_snap7_client.get_connected.return_value = True
    assert client.is_connected() is True

    mock_snap7_client.get_connected.side_effect = Exception("boom")
    assert client.is_connected() is False


async def test_read_tags_decodes_real_and_bool(mock_snap7_client):
    real_bytes = bytearray(struct.pack(">f", 23.5))
    bool_byte = bytearray([0b00000100])  # bit 2 set

    def fake_db_read(db_number, start, size):
        if db_number == 10 and start == 0:
            return real_bytes
        if db_number == 10 and start == 8:
            return bool_byte
        raise AssertionError(f"unexpected db_read({db_number}, {start}, {size})")

    mock_snap7_client.db_read.side_effect = fake_db_read

    client = S7PLCClient(address="10.0.0.5")
    results = await client.read_tags([REAL_TAG, BOOL_TAG])

    assert results["temp_a"].ok is True
    assert results["temp_a"].value == pytest.approx(23.5)
    assert results["door_a"].ok is True
    assert results["door_a"].value is True


async def test_read_tags_isolates_failure_per_tag(mock_snap7_client):
    def fake_db_read(db_number, start, size):
        if start == 0:
            raise RuntimeError("comm error")
        return bytearray([0])

    mock_snap7_client.db_read.side_effect = fake_db_read

    client = S7PLCClient(address="10.0.0.5")
    results = await client.read_tags([REAL_TAG, BOOL_TAG])

    assert results["temp_a"].ok is False
    assert "comm error" in (results["temp_a"].error or "")
    assert results["door_a"].ok is True


async def test_missing_s7_address_reports_error_without_touching_client(mock_snap7_client):
    unconfigured = TagDefinition(
        name="modbus_only",
        kind="digital",
        sensor_type="DOOR",
        poll_tier="fast",
        modbus={"register_address": 5, "type": "COIL"},
    )
    client = S7PLCClient(address="10.0.0.5")
    results = await client.read_tags([unconfigured])
    assert results["modbus_only"].ok is False
    mock_snap7_client.db_read.assert_not_called()
