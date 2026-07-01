from datetime import datetime

from sqlalchemy import select

from app.models.sensor_reading import SensorReadingDaily, SensorReadingHourly
from app.repositories.base import BaseRepository


class ReadingHourlyRepository(BaseRepository[SensorReadingHourly]):
    model = SensorReadingHourly

    async def list_in_range(
        self, sensor_id: int, start: datetime, end: datetime
    ) -> list[SensorReadingHourly]:
        result = await self.session.execute(
            select(SensorReadingHourly)
            .where(SensorReadingHourly.sensor_id == sensor_id)
            .where(SensorReadingHourly.bucket_start >= start)
            .where(SensorReadingHourly.bucket_start <= end)
            .order_by(SensorReadingHourly.bucket_start)
        )
        return list(result.scalars().all())


class ReadingDailyRepository(BaseRepository[SensorReadingDaily]):
    model = SensorReadingDaily

    async def list_in_range(
        self, sensor_id: int, start: datetime, end: datetime
    ) -> list[SensorReadingDaily]:
        result = await self.session.execute(
            select(SensorReadingDaily)
            .where(SensorReadingDaily.sensor_id == sensor_id)
            .where(SensorReadingDaily.bucket_start >= start)
            .where(SensorReadingDaily.bucket_start <= end)
            .order_by(SensorReadingDaily.bucket_start)
        )
        return list(result.scalars().all())
