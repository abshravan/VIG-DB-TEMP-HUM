from app.core.config import Settings
from app.plc.base import PLCClient
from app.plc.modbus_client import ModbusPLCClient
from app.plc.s7_client import S7PLCClient
from app.plc.simulator import SimulatedPLCClient


def build_plc_client(settings: Settings) -> PLCClient:
    """The PLC team's protocol choice (`settings.plc_protocol`) is the only thing that
    changes here — everything above this layer talks to the `PLCClient` interface only.
    See ARCHITECTURE.md §3.1.
    """
    if settings.plc_protocol == "s7":
        return S7PLCClient(
            address=settings.plc_address,
            rack=settings.plc_rack,
            slot=settings.plc_slot,
            tcp_port=settings.plc_s7_port,
        )
    if settings.plc_protocol == "modbus":
        return ModbusPLCClient(address=settings.plc_address, port=settings.plc_modbus_port)
    if settings.plc_protocol == "simulated":
        return SimulatedPLCClient(seed=settings.plc_sim_seed)
    raise ValueError(f"unsupported PLC_PROTOCOL: {settings.plc_protocol}")
