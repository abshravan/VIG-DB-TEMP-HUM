import asyncio
import logging

import snap7
from snap7.util import get_bool, get_int, get_real

from app.plc.base import PLCClient, TagReadResult
from app.plc.tags import TagDefinition

logger = logging.getLogger(__name__)


class S7PLCClient(PLCClient):
    """S7 protocol client for Siemens S7-1200/1500, via python-snap7.

    PLC-side prerequisites (see ARCHITECTURE.md §3.1, §4.1):
    - The target DB must have "Optimized block access" UNCHECKED (Properties > Attributes),
      otherwise byte offsets are not stable and this client cannot address the data.
    - "Permit access with PUT/GET communication" must be enabled (Protection & Security).
    - rack=0, slot=1 for an S7-1200 (S7-300 uses slot=2).

    snap7's `Client` is a synchronous, blocking-socket library — every call is wrapped in
    `asyncio.to_thread` so a slow/hung PLC never blocks the event loop (and therefore never
    blocks the API/WebSocket from serving already-known data).
    """

    def __init__(self, address: str, rack: int = 0, slot: int = 1, tcp_port: int = 102) -> None:
        self._address = address
        self._rack = rack
        self._slot = slot
        self._tcp_port = tcp_port
        self._client = snap7.client.Client()

    async def connect(self) -> None:
        await asyncio.to_thread(
            self._client.connect, self._address, self._rack, self._slot, self._tcp_port
        )

    async def disconnect(self) -> None:
        await asyncio.to_thread(self._client.disconnect)

    def is_connected(self) -> bool:
        try:
            return self._client.get_connected()
        except Exception:  # noqa: BLE001 — treat any snap7 internal error as "not connected"
            return False

    async def read_tags(self, tags: list[TagDefinition]) -> dict[str, TagReadResult]:
        results: dict[str, TagReadResult] = {}
        for tag in tags:
            if tag.s7 is None:
                results[tag.name] = TagReadResult(value=None, ok=False, error="no S7 address configured")
                continue
            try:
                results[tag.name] = await asyncio.to_thread(self._read_one, tag)
            except Exception as exc:  # noqa: BLE001 — isolate one bad tag from the rest of the scan
                logger.warning("S7 read failed for tag %s: %s", tag.name, exc)
                results[tag.name] = TagReadResult(value=None, ok=False, error=str(exc))
        return results

    def _read_one(self, tag: TagDefinition) -> TagReadResult:
        addr = tag.s7
        assert addr is not None
        size = 1 if addr.type == "BOOL" else 4
        data = self._client.db_read(addr.db, addr.offset, size)
        if addr.type == "REAL":
            value: float | bool = get_real(data, 0)
        elif addr.type == "INT":
            value = float(get_int(data, 0))
        elif addr.type == "BOOL":
            value = get_bool(data, 0, addr.bit or 0)
        else:
            raise ValueError(f"unsupported S7 tag type: {addr.type}")
        return TagReadResult(value=value, ok=True)
