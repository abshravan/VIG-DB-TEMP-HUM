import pytest

from app.models.enums import UserRole
from app.plc.connection import ResilientPLCConnection
from app.plc.simulator import SimulatedPLCClient
from app.plc.tags import TagMap
from tests.conftest import create_user, login_headers

pytestmark = pytest.mark.asyncio

TAG_MAP = TagMap.model_validate(
    {
        "tags": [
            {
                "name": "temp_rack_a",
                "kind": "analog",
                "sensor_type": "TEMPERATURE",
                "poll_tier": "normal",
                "s7": {"db": 10, "offset": 0, "type": "REAL"},
                "scale": {"raw_min": 0, "raw_max": 27648, "eng_min": 0, "eng_max": 50, "unit": "°C"},
            },
            {
                "name": "door_a",
                "kind": "digital",
                "sensor_type": "DOOR",
                "poll_tier": "fast",
                "s7": {"db": 10, "offset": 8, "type": "BOOL", "bit": 0},
            },
        ]
    }
)


def _install_simulated_plc(api_client) -> SimulatedPLCClient:
    """`api_client` doesn't run the app lifespan (see conftest.py), so the simulate endpoints'
    `app.state.plc_connection`/`app.state.tag_map` have to be set up by hand here, the same way
    the real lifespan does in `app/main.py`.
    """
    client = SimulatedPLCClient(seed=1)
    api_client.app.state.plc_connection = ResilientPLCConnection(client)
    api_client.app.state.tag_map = TAG_MAP
    return client


async def test_simulate_status_requires_active_simulation(api_client, session_maker):
    await create_user(session_maker, "viewer", "pw12345678", UserRole.VIEWER)
    headers = await login_headers(api_client, "viewer", "pw12345678")

    response = await api_client.get("/api/v1/system/simulate", headers=headers)
    assert response.status_code == 409


async def test_simulate_status_lists_tags_once_active(api_client, session_maker):
    client = _install_simulated_plc(api_client)
    await client.connect()
    await create_user(session_maker, "viewer", "pw12345678", UserRole.VIEWER)
    headers = await login_headers(api_client, "viewer", "pw12345678")

    response = await api_client.get("/api/v1/system/simulate", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["active"] is True
    assert body["plc_offline"] is False
    names = {tag["name"] for tag in body["tags"]}
    assert names == {"temp_rack_a", "door_a"}


async def test_viewer_cannot_set_simulated_tag_value(api_client, session_maker):
    _install_simulated_plc(api_client)
    await create_user(session_maker, "viewer", "pw12345678", UserRole.VIEWER)
    headers = await login_headers(api_client, "viewer", "pw12345678")

    response = await api_client.put(
        "/api/v1/system/simulate/tags/temp_rack_a", json={"value": 42.0}, headers=headers
    )
    assert response.status_code == 403


async def test_operator_can_set_simulated_analog_tag_value(api_client, session_maker):
    client = _install_simulated_plc(api_client)
    await create_user(session_maker, "operator", "pw12345678", UserRole.OPERATOR)
    headers = await login_headers(api_client, "operator", "pw12345678")

    response = await api_client.put(
        "/api/v1/system/simulate/tags/temp_rack_a", json={"value": 42.0}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["current_value"] == 42.0
    assert client.get_value("temp_rack_a") == 42.0


async def test_set_simulated_tag_value_rejects_unknown_tag(api_client, session_maker):
    _install_simulated_plc(api_client)
    await create_user(session_maker, "admin", "pw12345678", UserRole.ADMIN)
    headers = await login_headers(api_client, "admin", "pw12345678")

    response = await api_client.put(
        "/api/v1/system/simulate/tags/does_not_exist", json={"value": 1.0}, headers=headers
    )
    assert response.status_code == 404


async def test_set_simulated_tag_value_rejects_wrong_type_for_digital_tag(api_client, session_maker):
    _install_simulated_plc(api_client)
    await create_user(session_maker, "admin", "pw12345678", UserRole.ADMIN)
    headers = await login_headers(api_client, "admin", "pw12345678")

    response = await api_client.put(
        "/api/v1/system/simulate/tags/door_a", json={"value": 1.5}, headers=headers
    )
    assert response.status_code == 422


async def test_set_simulated_tag_failure(api_client, session_maker):
    client = _install_simulated_plc(api_client)
    await create_user(session_maker, "admin", "pw12345678", UserRole.ADMIN)
    headers = await login_headers(api_client, "admin", "pw12345678")

    response = await api_client.put(
        "/api/v1/system/simulate/tags/temp_rack_a/failure", json={"failing": True}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["failing"] is True
    assert client.is_tag_failing("temp_rack_a") is True


async def test_set_simulated_plc_connection_toggles_offline(api_client, session_maker):
    client = _install_simulated_plc(api_client)
    await client.connect()
    await create_user(session_maker, "admin", "pw12345678", UserRole.ADMIN)
    headers = await login_headers(api_client, "admin", "pw12345678")

    response = await api_client.put(
        "/api/v1/system/simulate/plc-connection", json={"disconnected": True}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["plc_offline"] is True
    assert client.is_connected() is False
