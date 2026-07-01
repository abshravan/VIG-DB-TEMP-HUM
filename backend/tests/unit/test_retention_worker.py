from datetime import datetime, timedelta

import pytest

from app.models.enums import ReadingQuality, SensorType
from app.models.sensor import Sensor
from app.models.sensor_reading import SensorReading, SensorReadingHourly
from app.repositories import ReadingDailyRepository, ReadingHourlyRepository, ReadingRepository, SensorRepository
from app.workers.retention import RetentionWorker, day_bucket, hour_bucket

NOW = datetime(2026, 1, 10, 15, 30, 0)  # mid-hour, mid-day, deliberately not on a bucket boundary


async def _make_sensor(session_maker) -> int:
    async with session_maker() as session:
        sensor = await SensorRepository(session).create(
            Sensor(tag_name="temp_a", display_name="Temp A", sensor_type=SensorType.TEMPERATURE)
        )
        await session.commit()
        return sensor.id


async def _add_reading(session_maker, sensor_id: int, value: float, timestamp: datetime, quality=ReadingQuality.GOOD):
    async with session_maker() as session:
        await ReadingRepository(session).create(
            SensorReading(sensor_id=sensor_id, value=value, quality=quality, timestamp=timestamp)
        )
        await session.commit()


def test_hour_bucket_truncates_to_the_hour():
    assert hour_bucket(datetime(2026, 1, 10, 15, 47, 12)) == datetime(2026, 1, 10, 15, 0, 0)


def test_day_bucket_truncates_to_midnight():
    assert day_bucket(datetime(2026, 1, 10, 15, 47, 12)) == datetime(2026, 1, 10, 0, 0, 0)


async def test_rollup_creates_hourly_bucket_for_completed_hour(session_maker):
    sensor_id = await _make_sensor(session_maker)
    completed_hour = hour_bucket(NOW) - timedelta(hours=1)
    for i, value in enumerate([10.0, 20.0, 30.0]):
        await _add_reading(session_maker, sensor_id, value, completed_hour + timedelta(minutes=10 * i))

    worker = RetentionWorker(session_maker)
    await worker.run_once(NOW)

    async with session_maker() as session:
        rows = await ReadingHourlyRepository(session).list_in_range(
            sensor_id, completed_hour, completed_hour
        )
    assert len(rows) == 1
    assert rows[0].min_value == 10.0
    assert rows[0].max_value == 30.0
    assert rows[0].avg_value == pytest.approx(20.0)
    assert rows[0].sample_count == 3


async def test_rollup_never_touches_the_in_progress_hour(session_maker):
    sensor_id = await _make_sensor(session_maker)
    await _add_reading(session_maker, sensor_id, 25.0, hour_bucket(NOW) + timedelta(minutes=5))

    worker = RetentionWorker(session_maker)
    await worker.run_once(NOW)

    async with session_maker() as session:
        rows = await ReadingHourlyRepository(session).list_in_range(
            sensor_id, hour_bucket(NOW), hour_bucket(NOW)
        )
    assert rows == []


async def test_rollup_excludes_bad_quality_readings(session_maker):
    sensor_id = await _make_sensor(session_maker)
    completed_hour = hour_bucket(NOW) - timedelta(hours=1)
    await _add_reading(session_maker, sensor_id, 20.0, completed_hour, ReadingQuality.GOOD)
    await _add_reading(session_maker, sensor_id, 999.0, completed_hour + timedelta(minutes=1), ReadingQuality.BAD)

    worker = RetentionWorker(session_maker)
    await worker.run_once(NOW)

    async with session_maker() as session:
        rows = await ReadingHourlyRepository(session).list_in_range(sensor_id, completed_hour, completed_hour)
    assert len(rows) == 1
    assert rows[0].max_value == 20.0  # the BAD 999.0 must not pull the aggregate up
    assert rows[0].sample_count == 1


async def test_rollup_is_idempotent_across_runs(session_maker):
    sensor_id = await _make_sensor(session_maker)
    completed_hour = hour_bucket(NOW) - timedelta(hours=1)
    await _add_reading(session_maker, sensor_id, 20.0, completed_hour)

    worker = RetentionWorker(session_maker)
    await worker.run_once(NOW)
    await worker.run_once(NOW)  # second run must not create a duplicate bucket

    async with session_maker() as session:
        rows = await ReadingHourlyRepository(session).list_in_range(sensor_id, completed_hour, completed_hour)
    assert len(rows) == 1


async def test_daily_rollup_aggregates_hourly_buckets_weighted_by_sample_count(session_maker):
    sensor_id = await _make_sensor(session_maker)
    completed_day = day_bucket(NOW) - timedelta(days=1)
    async with session_maker() as session:
        hourly_repo = ReadingHourlyRepository(session)
        await hourly_repo.create(
            SensorReadingHourly(
                sensor_id=sensor_id, bucket_start=completed_day, min_value=10.0, max_value=10.0,
                avg_value=10.0, sample_count=1,
            )
        )
        await hourly_repo.create(
            SensorReadingHourly(
                sensor_id=sensor_id, bucket_start=completed_day + timedelta(hours=1), min_value=30.0,
                max_value=30.0, avg_value=30.0, sample_count=3,
            )
        )
        await session.commit()

    worker = RetentionWorker(session_maker)
    await worker.run_once(NOW)

    async with session_maker() as session:
        rows = await ReadingDailyRepository(session).list_in_range(sensor_id, completed_day, completed_day)
    assert len(rows) == 1
    # weighted avg: (10*1 + 30*3) / 4 = 25.0
    assert rows[0].avg_value == pytest.approx(25.0)
    assert rows[0].min_value == 10.0
    assert rows[0].max_value == 30.0
    assert rows[0].sample_count == 4


async def test_daily_rollup_never_touches_in_progress_day(session_maker):
    sensor_id = await _make_sensor(session_maker)
    async with session_maker() as session:
        await ReadingHourlyRepository(session).create(
            SensorReadingHourly(
                sensor_id=sensor_id, bucket_start=hour_bucket(NOW), min_value=1.0, max_value=1.0,
                avg_value=1.0, sample_count=1,
            )
        )
        await session.commit()

    worker = RetentionWorker(session_maker)
    await worker.run_once(NOW)

    async with session_maker() as session:
        rows = await ReadingDailyRepository(session).list_in_range(sensor_id, day_bucket(NOW), day_bucket(NOW))
    assert rows == []


async def test_prunes_raw_readings_older_than_retention_window(session_maker):
    sensor_id = await _make_sensor(session_maker)
    old_timestamp = NOW - timedelta(days=100)
    recent_timestamp = NOW - timedelta(days=1)
    await _add_reading(session_maker, sensor_id, 1.0, old_timestamp)
    await _add_reading(session_maker, sensor_id, 2.0, recent_timestamp)

    worker = RetentionWorker(session_maker, raw_retention_days=90)
    await worker.run_once(NOW)

    async with session_maker() as session:
        remaining = await ReadingRepository(session).list()
    assert [r.value for r in remaining] == [2.0]
