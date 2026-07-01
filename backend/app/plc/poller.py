import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime

from app.core.time import utcnow
from app.plc.base import TagReadResult
from app.plc.connection import ResilientPLCConnection
from app.plc.tags import TagDefinition, TagMap

logger = logging.getLogger(__name__)

ReadingsCallback = Callable[[dict[str, TagReadResult], datetime], Awaitable[None]]


class PLCPoller:
    """Runs the fast and normal poll tiers as independent asyncio loops (ARCHITECTURE.md §4.3)
    so a slow analog scan never delays a smoke/water-leak/door read. Emits raw `TagReadResult`s
    via `on_readings` — raw-to-engineering scaling and quality/alarm evaluation happen in later
    layers (Validation Layer, Alarm Engine), not here.
    """

    def __init__(
        self,
        connection: ResilientPLCConnection,
        tag_map: TagMap,
        on_readings: ReadingsCallback,
    ) -> None:
        self._connection = connection
        self._tag_map = tag_map
        self._on_readings = on_readings
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        for tier, interval in (
            ("fast", self._tag_map.poll_intervals.fast),
            ("normal", self._tag_map.poll_intervals.normal),
        ):
            tags = self._tag_map.tags_for_tier(tier)
            if not tags:
                continue
            self._tasks.append(asyncio.create_task(self._run_tier(tier, tags, interval)))

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks.clear()

    async def _run_tier(self, tier: str, tags: list[TagDefinition], interval: float) -> None:
        while True:
            if not await self._connection.ensure_connected():
                continue  # ensure_connected() already slept its backoff step
            try:
                results = await self._connection.client.read_tags(tags)
                await self._on_readings(results, utcnow())
            except Exception as exc:  # noqa: BLE001 — a scan failure must not kill the poll loop
                logger.warning("[%s tier] poll cycle failed: %s", tier, exc)
            await asyncio.sleep(interval)
