import pytest

from app.core.config import Settings
from app.plc.factory import build_plc_client
from app.plc.modbus_client import ModbusPLCClient
from app.plc.s7_client import S7PLCClient
from app.plc.simulator import SimulatedPLCClient


def test_builds_s7_client_by_default():
    settings = Settings(database_url="sqlite+aiosqlite:///:memory:")
    client = build_plc_client(settings)
    assert isinstance(client, S7PLCClient)


async def test_builds_modbus_client_when_configured():
    # AsyncModbusTcpClient needs a running event loop even at construction time.
    settings = Settings(database_url="sqlite+aiosqlite:///:memory:", plc_protocol="modbus")
    client = build_plc_client(settings)
    assert isinstance(client, ModbusPLCClient)


def test_builds_simulated_client_when_configured():
    settings = Settings(database_url="sqlite+aiosqlite:///:memory:", plc_protocol="simulated", plc_sim_seed=42)
    client = build_plc_client(settings)
    assert isinstance(client, SimulatedPLCClient)


def test_rejects_unknown_protocol():
    settings = Settings(database_url="sqlite+aiosqlite:///:memory:")
    settings.plc_protocol = "bogus"
    with pytest.raises(ValueError, match="unsupported PLC_PROTOCOL"):
        build_plc_client(settings)
