from datetime import datetime

from sqlalchemy import select

from app.models.sensor_reading import SensorReading
from app.repositories.base import BaseRepository


class ReadingRepository(BaseRepository[SensorReading]):
    model = SensorReading

    async def latest_for_sensor(self, sensor_id: int) -> SensorReading | None:
        result = await self.session.execute(
            select(SensorReading)
            .where(SensorReading.sensor_id == sensor_id)
            .order_by(SensorReading.timestamp.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_in_range(
        self, sensor_id: int, start: datetime, end: datetime
    ) -> list[SensorReading]:
        result = await self.session.execute(
            select(SensorReading)
            .where(SensorReading.sensor_id == sensor_id)
            .where(SensorReading.timestamp >= start)
            .where(SensorReading.timestamp <= end)
            .order_by(SensorReading.timestamp)
        )
        return list(result.scalars().all())

    async def delete_older_than(self, cutoff: datetime) -> int:
        """Used by the retention worker after raw rows have been rolled up (ARCHITECTURE.md §9)."""
        result = await self.session.execute(
            select(SensorReading).where(SensorReading.timestamp < cutoff)
        )
        rows = list(result.scalars().all())
        for row in rows:
            await self.session.delete(row)
        await self.session.flush()
        return len(rows)

    async def list_unsynced(self, limit: int) -> list[SensorReading]:
        """Outbox pattern for the optional Atlas sync worker (ARCHITECTURE.md §12)."""
        result = await self.session.execute(
            select(SensorReading)
            .where(SensorReading.synced_at.is_(None))
            .order_by(SensorReading.timestamp)
            .limit(limit)
        )
        return list(result.scalars().all())
