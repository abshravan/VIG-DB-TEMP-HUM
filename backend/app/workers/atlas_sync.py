import asyncio
import logging
from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import UpdateOne
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.time import utcnow
from app.repositories import ReadingRepository

logger = logging.getLogger(__name__)

BATCH_SIZE = 500
DEFAULT_INTERVAL_SECONDS = 60.0


class AtlasSyncWorker:
    """Best-effort historical sync to MongoDB Atlas when internet is available
    (ARCHITECTURE.md §12) — an outbox pattern keyed on `SensorReading.synced_at`. Fully
    decoupled from the core write path: if this fails, is disabled (empty connection string),
    or the internet is down for a month, ingestion/alarms/dashboard are entirely unaffected —
    unsynced rows just queue up locally until connectivity returns.
    """

    def __init__(
        self,
        session_maker: async_sessionmaker[AsyncSession],
        connection_string: str,
        database_name: str = "server_room_monitor",
    ) -> None:
        self._session_maker = session_maker
        self._connection_string = connection_string
        self._database_name = database_name

    @property
    def enabled(self) -> bool:
        return bool(self._connection_string)

    async def run_once(self, now: datetime) -> int:
        """Returns how many rows were synced this cycle (0 if disabled, nothing pending, or
        the sync attempt failed — never raises, since a flaky/absent internet connection is
        an expected, routine condition here, not an error worth surfacing to the caller.
        """
        if not self.enabled:
            return 0

        async with self._session_maker() as session:
            reading_repo = ReadingRepository(session)
            unsynced = await reading_repo.list_unsynced(limit=BATCH_SIZE)
            if not unsynced:
                return 0

            client = AsyncIOMotorClient(self._connection_string, serverSelectionTimeoutMS=5000)
            try:
                collection = client[self._database_name]["sensor_readings"]
                operations = [
                    UpdateOne(
                        {"_id": reading.id},
                        {
                            "$set": {
                                "sensor_id": reading.sensor_id,
                                "value": reading.value,
                                "quality": reading.quality.value,
                                "timestamp": reading.timestamp,
                            }
                        },
                        upsert=True,
                    )
                    for reading in unsynced
                ]
                await collection.bulk_write(operations)
            except Exception:  # noqa: BLE001 — no internet / unreachable Atlas is routine, not fatal
                logger.warning("Atlas sync failed this cycle, will retry next time", exc_info=True)
                return 0
            finally:
                client.close()

            for reading in unsynced:
                reading.synced_at = now
            await session.commit()

        logger.info("Atlas sync: pushed %d readings", len(unsynced))
        return len(unsynced)


async def run_periodic_atlas_sync(worker: AtlasSyncWorker, interval_seconds: float = DEFAULT_INTERVAL_SECONDS) -> None:
    if not worker.enabled:
        logger.info("Atlas sync disabled (no connection string configured)")
        return
    while True:
        try:
            await worker.run_once(utcnow())
        except Exception:  # noqa: BLE001 — a scheduling hiccup must not kill the loop
            logger.exception("Atlas sync cycle raised unexpectedly")
        await asyncio.sleep(interval_seconds)
