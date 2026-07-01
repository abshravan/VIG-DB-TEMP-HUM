from datetime import datetime

import pytest

from app.models.alarm import Alarm, AlarmRule
from app.models.enums import AlarmSeverity, AlarmState, AlarmType
from app.repositories import AlarmRepository, AlarmRuleRepository

pytestmark = pytest.mark.asyncio


async def test_list_enabled_excludes_disabled_rules(session):
    repo = AlarmRuleRepository(session)
    await repo.create(
        AlarmRule(alarm_type=AlarmType.PLC_OFFLINE, severity=AlarmSeverity.CRITICAL, is_enabled=True)
    )
    await repo.create(
        AlarmRule(alarm_type=AlarmType.SENSOR_FAILURE, severity=AlarmSeverity.WARNING, is_enabled=False)
    )
    await session.commit()

    enabled = await repo.list_enabled()
    assert {r.alarm_type for r in enabled} == {AlarmType.PLC_OFFLINE}


async def test_list_active_excludes_cleared_alarms(session):
    rule = await AlarmRuleRepository(session).create(
        AlarmRule(alarm_type=AlarmType.SMOKE, severity=AlarmSeverity.CRITICAL)
    )
    await session.commit()

    repo = AlarmRepository(session)
    await repo.create(
        Alarm(rule_id=rule.id, state=AlarmState.ACTIVE, triggered_at=datetime.utcnow())
    )
    await repo.create(
        Alarm(rule_id=rule.id, state=AlarmState.ACKNOWLEDGED, triggered_at=datetime.utcnow())
    )
    await repo.create(
        Alarm(rule_id=rule.id, state=AlarmState.CLEARED, triggered_at=datetime.utcnow())
    )
    await session.commit()

    active = await repo.list_active()
    assert {a.state for a in active} == {AlarmState.ACTIVE, AlarmState.ACKNOWLEDGED}


async def test_alarms_deleted_when_rule_deleted(session):
    rule = await AlarmRuleRepository(session).create(
        AlarmRule(alarm_type=AlarmType.DOOR_OPEN, severity=AlarmSeverity.INFO)
    )
    await session.commit()

    alarm_repo = AlarmRepository(session)
    await alarm_repo.create(Alarm(rule_id=rule.id, state=AlarmState.ACTIVE, triggered_at=datetime.utcnow()))
    await session.commit()

    await AlarmRuleRepository(session).delete(rule)
    await session.commit()

    assert await alarm_repo.list() == []
