from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pymodbus.client.mixin import ModbusClientMixin

from app.plc.modbus_client import ModbusPLCClient
from app.plc.tags import TagDefinition

pytestmark = pytest.mark.asyncio

FLOAT_TAG = TagDefinition(
    name="temp_a",
    kind="analog",
    sensor_type="TEMPERATURE",
    poll_tier="normal",
    modbus={"register_address": 0, "type": "FLOAT32"},
    scale={"raw_min": 0, "raw_max": 100, "eng_min": 0, "eng_max": 50, "unit": "°C"},
)
COIL_TAG = TagDefinition(
    name="door_a",
    kind="digital",
    sensor_type="DOOR",
    poll_tier="fast",
    modbus={"register_address": 2, "type": "COIL"},
)


@pytest.fixture
def mock_modbus_client():
    with patch("app.plc.modbus_client.AsyncModbusTcpClient") as mock_cls:
        instance = MagicMock()
        instance.connect = AsyncMock(return_value=True)
        instance.close = MagicMock()
        instance.connected = True
        mock_cls.return_value = instance
        yield instance


async def test_connect_disconnect_and_is_connected(mock_modbus_client):
    client = ModbusPLCClient(address="10.0.0.6")
    await client.connect()
    mock_modbus_client.connect.assert_called_once()

    assert client.is_connected() is True

    await client.disconnect()
    mock_modbus_client.close.assert_called_once()


async def test_read_tags_decodes_float32_and_coil(mock_modbus_client):
    registers = ModbusClientMixin.convert_to_registers(23.5, ModbusClientMixin.DATATYPE.FLOAT32)

    hr_response = MagicMock()
    hr_response.isError.return_value = False
    hr_response.registers = registers

    coil_response = MagicMock()
    coil_response.isError.return_value = False
    coil_response.bits = [True]

    mock_modbus_client.read_holding_registers = AsyncMock(return_value=hr_response)
    mock_modbus_client.read_coils = AsyncMock(return_value=coil_response)

    client = ModbusPLCClient(address="10.0.0.6")
    results = await client.read_tags([FLOAT_TAG, COIL_TAG])

    assert results["temp_a"].ok is True
    assert results["temp_a"].value == pytest.approx(23.5)
    mock_modbus_client.read_holding_registers.assert_called_once_with(0, count=2)

    assert results["door_a"].ok is True
    assert results["door_a"].value is True
    mock_modbus_client.read_coils.assert_called_once_with(2, count=1)


async def test_read_tags_reports_modbus_error_response(mock_modbus_client):
    error_response = MagicMock()
    error_response.isError.return_value = True
    error_response.__str__.return_value = "IllegalAddress"
    mock_modbus_client.read_holding_registers = AsyncMock(return_value=error_response)

    client = ModbusPLCClient(address="10.0.0.6")
    results = await client.read_tags([FLOAT_TAG])

    assert results["temp_a"].ok is False
    assert "IllegalAddress" in (results["temp_a"].error or "")


async def test_missing_modbus_address_reports_error(mock_modbus_client):
    unconfigured = TagDefinition(
        name="s7_only",
        kind="digital",
        sensor_type="DOOR",
        poll_tier="fast",
        s7={"db": 1, "offset": 0, "type": "BOOL", "bit": 0},
    )
    client = ModbusPLCClient(address="10.0.0.6")
    results = await client.read_tags([unconfigured])
    assert results["s7_only"].ok is False
