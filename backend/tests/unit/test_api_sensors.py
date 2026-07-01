import pytest

from app.models.enums import SensorType, UserRole
from app.models.sensor import Sensor
from app.repositories import SensorRepository
from tests.conftest import create_user, login_headers

pytestmark = pytest.mark.asyncio


async def _seed_sensor(session_maker) -> None:
    async with session_maker() as session:
        await SensorRepository(session).create(
            Sensor(tag_name="temp_a", display_name="Temp A", sensor_type=SensorType.TEMPERATURE)
        )
        await session.commit()


async def test_list_sensors_requires_auth(api_client):
    response = await api_client.get("/api/v1/sensors")
    assert response.status_code == 401


async def test_list_sensors_returns_seeded_sensor(api_client, session_maker):
    await _seed_sensor(session_maker)
    await create_user(session_maker, "viewer", "pw12345678", UserRole.VIEWER)
    headers = await login_headers(api_client, "viewer", "pw12345678")

    response = await api_client.get("/api/v1/sensors", headers=headers)
    assert response.status_code == 200
    tags = {s["tag_name"] for s in response.json()}
    assert tags == {"temp_a"}


async def test_create_sensor_requires_admin_role(api_client, session_maker):
    await create_user(session_maker, "viewer", "pw12345678", UserRole.VIEWER)
    headers = await login_headers(api_client, "viewer", "pw12345678")

    response = await api_client.post(
        "/api/v1/sensors",
        json={"tag_name": "x", "display_name": "X", "sensor_type": "TEMPERATURE"},
        headers=headers,
    )
    assert response.status_code == 403


async def test_create_sensor_succeeds_as_admin(api_client, session_maker):
    await create_user(session_maker, "admin", "pw12345678", UserRole.ADMIN)
    headers = await login_headers(api_client, "admin", "pw12345678")

    response = await api_client.post(
        "/api/v1/sensors",
        json={"tag_name": "new_sensor", "display_name": "New", "sensor_type": "HUMIDITY"},
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["tag_name"] == "new_sensor"


async def test_create_sensor_rejects_duplicate_tag_name(api_client, session_maker):
    await _seed_sensor(session_maker)
    await create_user(session_maker, "admin", "pw12345678", UserRole.ADMIN)
    headers = await login_headers(api_client, "admin", "pw12345678")

    response = await api_client.post(
        "/api/v1/sensors",
        json={"tag_name": "temp_a", "display_name": "Dup", "sensor_type": "TEMPERATURE"},
        headers=headers,
    )
    assert response.status_code == 409


async def test_operator_can_update_sensor_display_name(api_client, session_maker):
    await _seed_sensor(session_maker)
    await create_user(session_maker, "op", "pw12345678", UserRole.OPERATOR)
    headers = await login_headers(api_client, "op", "pw12345678")

    async with session_maker() as session:
        sensor = await SensorRepository(session).get_by_tag_name("temp_a")
        sensor_id = sensor.id

    response = await api_client.patch(
        f"/api/v1/sensors/{sensor_id}", json={"display_name": "Renamed"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["display_name"] == "Renamed"


async def test_viewer_cannot_update_sensor(api_client, session_maker):
    await _seed_sensor(session_maker)
    await create_user(session_maker, "viewer", "pw12345678", UserRole.VIEWER)
    headers = await login_headers(api_client, "viewer", "pw12345678")

    async with session_maker() as session:
        sensor = await SensorRepository(session).get_by_tag_name("temp_a")
        sensor_id = sensor.id

    response = await api_client.patch(
        f"/api/v1/sensors/{sensor_id}", json={"display_name": "Renamed"}, headers=headers
    )
    assert response.status_code == 403


async def test_update_missing_sensor_returns_404(api_client, session_maker):
    await create_user(session_maker, "admin", "pw12345678", UserRole.ADMIN)
    headers = await login_headers(api_client, "admin", "pw12345678")

    response = await api_client.patch(
        "/api/v1/sensors/9999", json={"display_name": "X"}, headers=headers
    )
    assert response.status_code == 404
