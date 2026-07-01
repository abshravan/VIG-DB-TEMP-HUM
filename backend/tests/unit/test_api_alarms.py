from datetime import datetime

import pytest

from app.models.alarm import Alarm, AlarmRule
from app.models.enums import AlarmSeverity, AlarmState, AlarmType, LogCategory, LogLevel, UserRole
from app.repositories import AlarmRepository, AlarmRuleRepository, SystemLogRepository
from app.models.system_log import SystemLog
from tests.conftest import create_user, login_headers

pytestmark = pytest.mark.asyncio

T0 = datetime(2026, 1, 1, 12, 0, 0)


async def _seed_active_alarm(session_maker) -> int:
    async with session_maker() as session:
        rule = await AlarmRuleRepository(session).create(
            AlarmRule(alarm_type=AlarmType.PLC_OFFLINE, severity=AlarmSeverity.CRITICAL)
        )
        alarm = await AlarmRepository(session).create(
            Alarm(rule_id=rule.id, state=AlarmState.ACTIVE, triggered_at=T0)
        )
        await session.commit()
        return alarm.id


async def test_list_alarms_requires_auth(api_client):
    response = await api_client.get("/api/v1/alarms")
    assert response.status_code == 401


async def test_list_alarms_returns_seeded_alarm_with_type_and_severity(api_client, session_maker):
    await _seed_active_alarm(session_maker)
    await create_user(session_maker, "viewer", "pw12345678", UserRole.VIEWER)
    headers = await login_headers(api_client, "viewer", "pw12345678")

    response = await api_client.get("/api/v1/alarms", headers=headers)
    assert response.status_code == 200
    alarms = response.json()
    assert len(alarms) == 1
    assert alarms[0]["alarm_type"] == "PLC_OFFLINE"
    assert alarms[0]["severity"] == "CRITICAL"
    assert alarms[0]["state"] == "ACTIVE"


async def test_list_alarms_filters_by_state(api_client, session_maker):
    await _seed_active_alarm(session_maker)
    await create_user(session_maker, "viewer", "pw12345678", UserRole.VIEWER)
    headers = await login_headers(api_client, "viewer", "pw12345678")

    response = await api_client.get("/api/v1/alarms", params={"state": "CLEARED"}, headers=headers)
    assert response.json() == []


async def test_acknowledge_alarm_transitions_state_and_records_user(api_client, session_maker):
    alarm_id = await _seed_active_alarm(session_maker)
    await create_user(session_maker, "op", "pw12345678", UserRole.OPERATOR)
    headers = await login_headers(api_client, "op", "pw12345678")

    response = await api_client.post(f"/api/v1/alarms/{alarm_id}/acknowledge", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "ACKNOWLEDGED"
    assert body["acknowledged_by"] is not None
    assert body["alarm_type"] == "PLC_OFFLINE"


async def test_acknowledge_missing_alarm_returns_404(api_client, session_maker):
    await create_user(session_maker, "op", "pw12345678", UserRole.OPERATOR)
    headers = await login_headers(api_client, "op", "pw12345678")

    response = await api_client.post("/api/v1/alarms/9999/acknowledge", headers=headers)
    assert response.status_code == 404


async def test_events_returns_system_logs_most_recent_first(api_client, session_maker):
    async with session_maker() as session:
        repo = SystemLogRepository(session)
        await repo.create(
            SystemLog(
                timestamp=T0,
                level=LogLevel.INFO,
                category=LogCategory.SYSTEM_RESTART,
                message="first",
            )
        )
        await repo.create(
            SystemLog(
                timestamp=T0.replace(minute=5),
                level=LogLevel.WARNING,
                category=LogCategory.PLC_CONNECTION,
                message="second",
            )
        )
        await session.commit()

    await create_user(session_maker, "viewer", "pw12345678", UserRole.VIEWER)
    headers = await login_headers(api_client, "viewer", "pw12345678")

    response = await api_client.get("/api/v1/events", headers=headers)
    assert response.status_code == 200
    messages = [log["message"] for log in response.json()]
    assert messages == ["second", "first"]
