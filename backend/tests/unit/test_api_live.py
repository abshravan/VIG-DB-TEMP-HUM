from datetime import timedelta

import pytest

from app.core.time import utcnow
from app.models.enums import ReadingQuality, SensorType, UserRole
from app.models.sensor import Sensor
from app.models.sensor_reading import SensorReading
from app.repositories import ReadingRepository, SensorRepository
from tests.conftest import create_user, login_headers

pytestmark = pytest.mark.asyncio


async def test_live_status_reports_disconnected_plc_without_lifespan(api_client, session_maker):
    await create_user(session_maker, "viewer", "pw12345678", UserRole.VIEWER)
    headers = await login_headers(api_client, "viewer", "pw12345678")

    response = await api_client.get("/api/v1/live", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["plc_connected"] is False
    assert body["sensors"] == []
    assert body["active_alarm_count"] == 0


async def test_live_status_includes_fresh_and_stale_sensors(api_client, session_maker):
    now = utcnow()
    async with session_maker() as session:
        sensor_repo = SensorRepository(session)
        fresh = await sensor_repo.create(
            Sensor(tag_name="fresh", display_name="Fresh", sensor_type=SensorType.TEMPERATURE)
        )
        stale = await sensor_repo.create(
            Sensor(tag_name="stale", display_name="Stale", sensor_type=SensorType.TEMPERATURE)
        )
        reading_repo = ReadingRepository(session)
        await reading_repo.create(
            SensorReading(sensor_id=fresh.id, value=20.0, quality=ReadingQuality.GOOD, timestamp=now)
        )
        await reading_repo.create(
            SensorReading(
                sensor_id=stale.id,
                value=20.0,
                quality=ReadingQuality.GOOD,
                timestamp=now - timedelta(minutes=10),
            )
        )
        await session.commit()

    await create_user(session_maker, "viewer", "pw12345678", UserRole.VIEWER)
    headers = await login_headers(api_client, "viewer", "pw12345678")

    response = await api_client.get("/api/v1/live", headers=headers)
    sensors_by_tag = {s["tag_name"]: s for s in response.json()["sensors"]}
    assert sensors_by_tag["fresh"]["is_stale"] is False
    assert sensors_by_tag["stale"]["is_stale"] is True


async def test_live_status_sensor_never_read_is_stale_with_null_value(api_client, session_maker):
    async with session_maker() as session:
        await SensorRepository(session).create(
            Sensor(tag_name="never_read", display_name="Never Read", sensor_type=SensorType.DOOR)
        )
        await session.commit()

    await create_user(session_maker, "viewer", "pw12345678", UserRole.VIEWER)
    headers = await login_headers(api_client, "viewer", "pw12345678")

    response = await api_client.get("/api/v1/live", headers=headers)
    sensor = response.json()["sensors"][0]
    assert sensor["value"] is None
    assert sensor["is_stale"] is True


async def test_live_single_sensor_returns_404_for_unknown_id(api_client, session_maker):
    await create_user(session_maker, "viewer", "pw12345678", UserRole.VIEWER)
    headers = await login_headers(api_client, "viewer", "pw12345678")

    response = await api_client.get("/api/v1/live/9999", headers=headers)
    assert response.status_code == 404
