from datetime import datetime, timedelta

import pytest

from app.models.enums import ReadingQuality, SensorType
from app.models.sensor import Sensor
from app.models.sensor_reading import SensorReading
from app.repositories import ReadingRepository, SensorRepository

pytestmark = pytest.mark.asyncio


async def _make_sensor(session) -> Sensor:
    sensor = await SensorRepository(session).create(
        Sensor(tag_name="temp_a", display_name="Temp A", sensor_type=SensorType.TEMPERATURE)
    )
    await session.commit()
    return sensor


async def test_latest_for_sensor_returns_most_recent(session):
    sensor = await _make_sensor(session)
    repo = ReadingRepository(session)
    now = datetime.utcnow()
    await repo.create(
        SensorReading(sensor_id=sensor.id, value=20.0, quality=ReadingQuality.GOOD, timestamp=now - timedelta(minutes=5))
    )
    latest = await repo.create(
        SensorReading(sensor_id=sensor.id, value=22.5, quality=ReadingQuality.GOOD, timestamp=now)
    )
    await session.commit()

    result = await repo.latest_for_sensor(sensor.id)
    assert result is not None
    assert result.id == latest.id
    assert result.value == 22.5


async def test_list_in_range_filters_by_window(session):
    sensor = await _make_sensor(session)
    repo = ReadingRepository(session)
    base = datetime(2026, 1, 1, 12, 0, 0)
    for minutes_offset in (-120, -30, 0, 30, 120):
        await repo.create(
            SensorReading(
                sensor_id=sensor.id,
                value=float(minutes_offset),
                quality=ReadingQuality.GOOD,
                timestamp=base + timedelta(minutes=minutes_offset),
            )
        )
    await session.commit()

    in_range = await repo.list_in_range(
        sensor.id, base - timedelta(minutes=60), base + timedelta(minutes=60)
    )
    assert [r.value for r in in_range] == [-30.0, 0.0, 30.0]


async def test_delete_older_than_removes_only_stale_rows(session):
    sensor = await _make_sensor(session)
    repo = ReadingRepository(session)
    cutoff = datetime(2026, 1, 1)
    await repo.create(
        SensorReading(
            sensor_id=sensor.id, value=1.0, quality=ReadingQuality.GOOD, timestamp=cutoff - timedelta(days=1)
        )
    )
    await repo.create(
        SensorReading(
            sensor_id=sensor.id, value=2.0, quality=ReadingQuality.GOOD, timestamp=cutoff + timedelta(days=1)
        )
    )
    await session.commit()

    deleted_count = await repo.delete_older_than(cutoff)
    await session.commit()

    assert deleted_count == 1
    remaining = await repo.list()
    assert [r.value for r in remaining] == [2.0]


async def test_reading_deleted_when_sensor_deleted(session):
    sensor = await _make_sensor(session)
    repo = ReadingRepository(session)
    await repo.create(
        SensorReading(
            sensor_id=sensor.id, value=1.0, quality=ReadingQuality.GOOD, timestamp=datetime.utcnow()
        )
    )
    await session.commit()

    await SensorRepository(session).delete(sensor)
    await session.commit()

    assert await repo.list() == []
