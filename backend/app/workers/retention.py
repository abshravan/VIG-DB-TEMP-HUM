import logging
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.enums import ReadingQuality
from app.models.sensor_reading import SensorReadingDaily, SensorReadingHourly
from app.repositories import ReadingDailyRepository, ReadingHourlyRepository, ReadingRepository, SensorRepository

logger = logging.getLogger(__name__)

#: How long raw SensorReading rows are kept before pruning (ARCHITECTURE.md §9).
DEFAULT_RAW_RETENTION_DAYS = 90

#: Each run re-examines this recent window for hourly rollups; buckets that already exist
#: (checked via ReadingHourlyRepository.get_bucket) are skipped, so re-running is harmless.
HOURLY_LOOKBACK_HOURS = 48
DAILY_LOOKBACK_DAYS = 14


def hour_bucket(ts: datetime) -> datetime:
    return ts.replace(minute=0, second=0, microsecond=0)


def day_bucket(ts: datetime) -> datetime:
    return ts.replace(hour=0, minute=0, second=0, microsecond=0)


def aggregate(values: list[float]) -> tuple[float, float, float, int]:
    return min(values), max(values), sum(values) / len(values), len(values)


class RetentionWorker:
    """Nightly rollup + pruning (ARCHITECTURE.md §9): raw SensorReading rows are aggregated
    into hourly, then daily, buckets; raw rows older than the retention window are then
    deleted so History's long-range charts stay fast and the SD card doesn't fill up.

    Bucketing is done in Python (fetch the window, group by hour/day) rather than a
    dialect-specific SQL date-trunc, so the same code runs unchanged against SQLite or
    PostgreSQL — acceptable at this data volume (a handful of sensors, a few points/minute).
    """

    def __init__(
        self,
        session_maker: async_sessionmaker[AsyncSession],
        raw_retention_days: int = DEFAULT_RAW_RETENTION_DAYS,
    ) -> None:
        self._session_maker = session_maker
        self._raw_retention_days = raw_retention_days

    async def run_once(self, now: datetime) -> None:
        async with self._session_maker() as session:
            sensor_repo = SensorRepository(session)
            reading_repo = ReadingRepository(session)
            hourly_repo = ReadingHourlyRepository(session)
            daily_repo = ReadingDailyRepository(session)

            for sensor in await sensor_repo.list():
                await self._rollup_hourly(reading_repo, hourly_repo, sensor.id, now)
                await self._rollup_daily(hourly_repo, daily_repo, sensor.id, now)

            cutoff = now - timedelta(days=self._raw_retention_days)
            deleted = await reading_repo.delete_older_than(cutoff)
            if deleted:
                logger.info("retention: pruned %d raw readings older than %s", deleted, cutoff)

            await session.commit()

    async def _rollup_hourly(
        self,
        reading_repo: ReadingRepository,
        hourly_repo: ReadingHourlyRepository,
        sensor_id: int,
        now: datetime,
    ) -> None:
        current_hour = hour_bucket(now)
        window_start = current_hour - timedelta(hours=HOURLY_LOOKBACK_HOURS)
        readings = await reading_repo.list_in_range(sensor_id, window_start, current_hour)

        buckets: dict[datetime, list[float]] = defaultdict(list)
        for reading in readings:
            if reading.quality == ReadingQuality.GOOD:
                buckets[hour_bucket(reading.timestamp)].append(reading.value)

        for bucket_start, values in buckets.items():
            if bucket_start >= current_hour:
                continue  # never roll up the still-in-progress hour
            if await hourly_repo.get_bucket(sensor_id, bucket_start) is not None:
                continue
            min_v, max_v, avg_v, count = aggregate(values)
            await hourly_repo.create(
                SensorReadingHourly(
                    sensor_id=sensor_id,
                    bucket_start=bucket_start,
                    min_value=min_v,
                    max_value=max_v,
                    avg_value=avg_v,
                    sample_count=count,
                )
            )

    async def _rollup_daily(
        self,
        hourly_repo: ReadingHourlyRepository,
        daily_repo: ReadingDailyRepository,
        sensor_id: int,
        now: datetime,
    ) -> None:
        current_day = day_bucket(now)
        window_start = current_day - timedelta(days=DAILY_LOOKBACK_DAYS)
        hourly_rows = await hourly_repo.list_in_range(sensor_id, window_start, current_day)

        buckets: dict[datetime, list[SensorReadingHourly]] = defaultdict(list)
        for row in hourly_rows:
            buckets[day_bucket(row.bucket_start)].append(row)

        for bucket_start, rows in buckets.items():
            if bucket_start >= current_day:
                continue
            if await daily_repo.get_bucket(sensor_id, bucket_start) is not None:
                continue
            total_count = sum(row.sample_count for row in rows)
            if total_count == 0:
                continue
            avg_v = sum(row.avg_value * row.sample_count for row in rows) / total_count
            min_v = min(row.min_value for row in rows)
            max_v = max(row.max_value for row in rows)
            await daily_repo.create(
                SensorReadingDaily(
                    sensor_id=sensor_id,
                    bucket_start=bucket_start,
                    min_value=min_v,
                    max_value=max_v,
                    avg_value=avg_v,
                    sample_count=total_count,
                )
            )
