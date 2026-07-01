import pytest

from app.models.enums import UserRole
from tests.conftest import create_user, login_headers

pytestmark = pytest.mark.asyncio


async def test_system_health_requires_auth(api_client):
    response = await api_client.get("/api/v1/system/health")
    assert response.status_code == 401


async def test_system_health_returns_expected_fields(api_client, session_maker):
    await create_user(session_maker, "viewer", "pw12345678", UserRole.VIEWER)
    headers = await login_headers(api_client, "viewer", "pw12345678")

    response = await api_client.get("/api/v1/system/health", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert 0.0 <= body["cpu_percent"] <= 100.0
    assert 0.0 <= body["memory_percent"] <= 100.0
    assert body["uptime_seconds"] >= 0.0
    assert body["plc_connected"] is False  # no lifespan/PLC connection in the test client
