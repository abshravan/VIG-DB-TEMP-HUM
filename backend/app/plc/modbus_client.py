import logging

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.client.mixin import ModbusClientMixin

from app.plc.base import PLCClient, TagReadResult
from app.plc.tags import TagDefinition

logger = logging.getLogger(__name__)


class ModbusPLCClient(PLCClient):
    """Modbus TCP client via pymodbus, for PLCs exposing an MB_SERVER instruction instead
    of native S7 (see ARCHITECTURE.md §3.1). pymodbus's async client is natively asyncio —
    no thread offload needed here, unlike the S7 client.
    """

    def __init__(self, address: str, port: int = 502) -> None:
        self._client = AsyncModbusTcpClient(address, port=port)

    async def connect(self) -> None:
        await self._client.connect()

    async def disconnect(self) -> None:
        self._client.close()

    def is_connected(self) -> bool:
        return bool(self._client.connected)

    async def read_tags(self, tags: list[TagDefinition]) -> dict[str, TagReadResult]:
        results: dict[str, TagReadResult] = {}
        for tag in tags:
            if tag.modbus is None:
                results[tag.name] = TagReadResult(
                    value=None, ok=False, error="no Modbus address configured"
                )
                continue
            try:
                results[tag.name] = await self._read_one(tag)
            except Exception as exc:  # noqa: BLE001 — isolate one bad tag from the rest of the scan
                logger.warning("Modbus read failed for tag %s: %s", tag.name, exc)
                results[tag.name] = TagReadResult(value=None, ok=False, error=str(exc))
        return results

    async def _read_one(self, tag: TagDefinition) -> TagReadResult:
        addr = tag.modbus
        assert addr is not None

        if addr.type == "COIL":
            response = await self._client.read_coils(addr.register_address, count=1)
            if response.isError():
                return TagReadResult(value=None, ok=False, error=str(response))
            return TagReadResult(value=bool(response.bits[0]), ok=True)

        if addr.type == "FLOAT32":
            response = await self._client.read_holding_registers(addr.register_address, count=2)
            if response.isError():
                return TagReadResult(value=None, ok=False, error=str(response))
            value = ModbusClientMixin.convert_from_registers(
                response.registers, ModbusClientMixin.DATATYPE.FLOAT32
            )
            return TagReadResult(value=value, ok=True)

        if addr.type == "INT16":
            response = await self._client.read_holding_registers(addr.register_address, count=1)
            if response.isError():
                return TagReadResult(value=None, ok=False, error=str(response))
            return TagReadResult(value=float(response.registers[0]), ok=True)

        raise ValueError(f"unsupported Modbus tag type: {addr.type}")
