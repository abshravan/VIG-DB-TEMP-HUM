from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.enums import ReadingQuality, SensorType
from app.models.sensor import Sensor
from app.models.sensor_reading import SensorReading
from app.repositories import ReadingRepository, SensorRepository
from app.workers.atlas_sync import AtlasSyncWorker

pytestmark = pytest.mark.asyncio

NOW = datetime(2026, 1, 1, 12, 0, 0)


async def _seed_reading(session_maker) -> None:
    async with session_maker() as session:
        sensor = await SensorRepository(session).create(
            Sensor(tag_name="temp_a", display_name="Temp A", sensor_type=SensorType.TEMPERATURE)
        )
        await ReadingRepository(session).create(
            SensorReading(sensor_id=sensor.id, value=22.5, quality=ReadingQuality.GOOD, timestamp=NOW)
        )
        await session.commit()


def _mock_motor_client():
    mock_collection = MagicMock()
    mock_collection.bulk_write = AsyncMock(return_value=None)
    mock_client = MagicMock()
    mock_client.__getitem__.return_value.__getitem__.return_value = mock_collection
    mock_client.close = MagicMock()
    return mock_client, mock_collection


async def test_disabled_worker_does_nothing(session_maker):
    worker = AtlasSyncWorker(session_maker, connection_string="")
    assert worker.enabled is False
    assert await worker.run_once(NOW) == 0


async def test_enabled_with_nothing_to_sync_returns_zero(session_maker):
    worker = AtlasSyncWorker(session_maker, connection_string="mongodb://fake")
    assert worker.enabled is True
    assert await worker.run_once(NOW) == 0


async def test_successful_sync_marks_rows_synced_and_returns_count(session_maker):
    await _seed_reading(session_maker)
    mock_client, mock_collection = _mock_motor_client()

    with patch("app.workers.atlas_sync.AsyncIOMotorClient", return_value=mock_client):
        worker = AtlasSyncWorker(session_maker, connection_string="mongodb://fake")
        synced_count = await worker.run_once(NOW)

    assert synced_count == 1
    mock_collection.bulk_write.assert_called_once()
    mock_client.close.assert_called_once()

    async with session_maker() as session:
        rows = await ReadingRepository(session).list()
    assert rows[0].synced_at == NOW


async def test_failed_sync_leaves_rows_unsynced_and_does_not_raise(session_maker):
    await _seed_reading(session_maker)
    mock_client, mock_collection = _mock_motor_client()
    mock_collection.bulk_write = AsyncMock(side_effect=RuntimeError("no route to host"))

    with patch("app.workers.atlas_sync.AsyncIOMotorClient", return_value=mock_client):
        worker = AtlasSyncWorker(session_maker, connection_string="mongodb://fake")
        synced_count = await worker.run_once(NOW)

    assert synced_count == 0
    mock_client.close.assert_called_once()  # client is still cleaned up on failure

    async with session_maker() as session:
        rows = await ReadingRepository(session).list()
    assert rows[0].synced_at is None


async def test_already_synced_rows_are_not_resent(session_maker):
    await _seed_reading(session_maker)
    mock_client, mock_collection = _mock_motor_client()

    with patch("app.workers.atlas_sync.AsyncIOMotorClient", return_value=mock_client):
        worker = AtlasSyncWorker(session_maker, connection_string="mongodb://fake")
        await worker.run_once(NOW)  # first sync
        second_count = await worker.run_once(NOW)  # nothing left to sync

    assert second_count == 0
    assert mock_collection.bulk_write.call_count == 1
