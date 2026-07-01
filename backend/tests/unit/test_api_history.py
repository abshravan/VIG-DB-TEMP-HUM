from datetime import datetime, timedelta

import pytest

from app.models.enums import ReadingQuality, SensorType, UserRole
from app.models.sensor import Sensor
from app.models.sensor_reading import SensorReading
from app.repositories import ReadingRepository, SensorRepository
from tests.conftest import create_user, login_headers

pytestmark = pytest.mark.asyncio

T0 = datetime(2026, 1, 1, 12, 0, 0)


async def _seed_readings(session_maker) -> int:
    async with session_maker() as session:
        sensor = await SensorRepository(session).create(
            Sensor(tag_name="temp_a", display_name="Temp A", sensor_type=SensorType.TEMPERATURE)
        )
        reading_repo = ReadingRepository(session)
        for i in range(5):
            await reading_repo.create(
                SensorReading(
                    sensor_id=sensor.id,
                    value=20.0 + i,
                    quality=ReadingQuality.GOOD,
                    timestamp=T0 + timedelta(minutes=i),
                )
            )
        await session.commit()
        return sensor.id


async def test_history_requires_auth(api_client):
    response = await api_client.get(
        "/api/v1/history",
        params={"sensor_id": 1, "start": T0.isoformat(), "end": T0.isoformat()},
    )
    assert response.status_code == 401


async def test_history_returns_points_in_range(api_client, session_maker):
    sensor_id = await _seed_readings(session_maker)
    await create_user(session_maker, "viewer", "pw12345678", UserRole.VIEWER)
    headers = await login_headers(api_client, "viewer", "pw12345678")

    response = await api_client.get(
        "/api/v1/history",
        params={
            "sensor_id": sensor_id,
            "start": T0.isoformat(),
            "end": (T0 + timedelta(minutes=10)).isoformat(),
        },
        headers=headers,
    )
    assert response.status_code == 200
    points = response.json()
    assert len(points) == 5
    assert points[0]["value"] == 20.0


async def test_history_404s_for_unknown_sensor(api_client, session_maker):
    await create_user(session_maker, "viewer", "pw12345678", UserRole.VIEWER)
    headers = await login_headers(api_client, "viewer", "pw12345678")

    response = await api_client.get(
        "/api/v1/history",
        params={"sensor_id": 9999, "start": T0.isoformat(), "end": T0.isoformat()},
        headers=headers,
    )
    assert response.status_code == 404


async def test_history_export_returns_csv(api_client, session_maker):
    sensor_id = await _seed_readings(session_maker)
    await create_user(session_maker, "viewer", "pw12345678", UserRole.VIEWER)
    headers = await login_headers(api_client, "viewer", "pw12345678")

    response = await api_client.get(
        "/api/v1/history/export",
        params={
            "sensor_id": sensor_id,
            "start": T0.isoformat(),
            "end": (T0 + timedelta(minutes=10)).isoformat(),
        },
        headers=headers,
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    lines = response.text.strip().splitlines()
    assert lines[0] == "timestamp,value,quality"
    assert len(lines) == 6  # header + 5 rows
