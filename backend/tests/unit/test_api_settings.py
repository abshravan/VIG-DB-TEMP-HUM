import pytest

from app.models.alarm import AlarmRule
from app.models.configuration import Configuration
from app.models.enums import AlarmSeverity, AlarmType, UserRole
from app.repositories import AlarmRuleRepository, ConfigurationRepository
from tests.conftest import create_user, login_headers

pytestmark = pytest.mark.asyncio


async def _seed_configuration(session_maker) -> None:
    async with session_maker() as session:
        await ConfigurationRepository(session).create(
            Configuration(key="poll_interval_seconds", value="5", value_type="int")
        )
        await session.commit()


async def _seed_alarm_rule(session_maker) -> int:
    async with session_maker() as session:
        rule = await AlarmRuleRepository(session).create(
            AlarmRule(
                alarm_type=AlarmType.TEMP_HIGH,
                threshold_value=30.0,
                hysteresis=2.0,
                min_duration_seconds=60,
                severity=AlarmSeverity.WARNING,
            )
        )
        await session.commit()
        return rule.id


async def test_list_settings_requires_auth(api_client):
    response = await api_client.get("/api/v1/settings")
    assert response.status_code == 401


async def test_update_settings_requires_admin(api_client, session_maker):
    await _seed_configuration(session_maker)
    await create_user(session_maker, "viewer", "pw12345678", UserRole.VIEWER)
    headers = await login_headers(api_client, "viewer", "pw12345678")

    response = await api_client.put(
        "/api/v1/settings", json={"values": {"poll_interval_seconds": "10"}}, headers=headers
    )
    assert response.status_code == 403


async def test_update_settings_as_admin_changes_value(api_client, session_maker):
    await _seed_configuration(session_maker)
    await create_user(session_maker, "admin", "pw12345678", UserRole.ADMIN)
    headers = await login_headers(api_client, "admin", "pw12345678")

    response = await api_client.put(
        "/api/v1/settings", json={"values": {"poll_interval_seconds": "10"}}, headers=headers
    )
    assert response.status_code == 200
    updated = next(c for c in response.json() if c["key"] == "poll_interval_seconds")
    assert updated["value"] == "10"


async def test_update_settings_ignores_unknown_keys(api_client, session_maker):
    await create_user(session_maker, "admin", "pw12345678", UserRole.ADMIN)
    headers = await login_headers(api_client, "admin", "pw12345678")

    response = await api_client.put(
        "/api/v1/settings", json={"values": {"not_a_real_key": "x"}}, headers=headers
    )
    assert response.status_code == 200
    assert response.json() == []


async def test_update_alarm_rule_as_admin(api_client, session_maker):
    rule_id = await _seed_alarm_rule(session_maker)
    await create_user(session_maker, "admin", "pw12345678", UserRole.ADMIN)
    headers = await login_headers(api_client, "admin", "pw12345678")

    response = await api_client.put(
        f"/api/v1/settings/alarm-rules/{rule_id}",
        json={"threshold_value": 35.0, "is_enabled": False},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["threshold_value"] == 35.0
    assert body["is_enabled"] is False
    assert body["hysteresis"] == 2.0  # untouched fields keep their prior value


async def test_update_alarm_rule_requires_admin(api_client, session_maker):
    rule_id = await _seed_alarm_rule(session_maker)
    await create_user(session_maker, "op", "pw12345678", UserRole.OPERATOR)
    headers = await login_headers(api_client, "op", "pw12345678")

    response = await api_client.put(
        f"/api/v1/settings/alarm-rules/{rule_id}", json={"threshold_value": 35.0}, headers=headers
    )
    assert response.status_code == 403


async def test_update_missing_alarm_rule_returns_404(api_client, session_maker):
    await create_user(session_maker, "admin", "pw12345678", UserRole.ADMIN)
    headers = await login_headers(api_client, "admin", "pw12345678")

    response = await api_client.put(
        "/api/v1/settings/alarm-rules/9999", json={"threshold_value": 35.0}, headers=headers
    )
    assert response.status_code == 404
