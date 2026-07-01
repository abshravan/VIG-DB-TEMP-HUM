from datetime import datetime, timedelta

import pytest

from app.models.alarm import Alarm, AlarmRule
from app.models.enums import AlarmSeverity, AlarmState, AlarmType, UserRole
from app.models.sensor import Sensor
from app.models.user import User
from app.repositories import AlarmRepository, AlarmRuleRepository, SensorRepository, UserRepository
from app.services.alarm_engine import AlarmEngine

pytestmark = pytest.mark.asyncio

T0 = datetime(2026, 1, 1, 12, 0, 0)


async def _make_sensor(session) -> Sensor:
    sensor = await SensorRepository(session).create(
        Sensor(tag_name="temp_a", display_name="Temp A", sensor_type="TEMPERATURE")
    )
    await session.commit()
    return sensor


async def test_threshold_alarm_respects_debounce(session):
    sensor = await _make_sensor(session)
    rule = await AlarmRuleRepository(session).create(
        AlarmRule(
            sensor_id=sensor.id,
            alarm_type=AlarmType.TEMP_HIGH,
            threshold_value=30.0,
            hysteresis=2.0,
            min_duration_seconds=60,
            severity=AlarmSeverity.WARNING,
        )
    )
    await session.commit()

    alarm_repo = AlarmRepository(session)
    engine = AlarmEngine()

    # condition true, but debounce (60s) not yet elapsed -> no alarm created
    await engine.evaluate(alarm_repo, rule, 35.0, T0)
    await session.commit()
    assert await alarm_repo.list() == []

    # condition still true 61s later -> alarm now fires
    await engine.evaluate(alarm_repo, rule, 35.0, T0 + timedelta(seconds=61))
    await session.commit()
    alarms = await alarm_repo.list()
    assert len(alarms) == 1
    assert alarms[0].state == AlarmState.ACTIVE
    assert alarms[0].triggered_value == 35.0


async def test_threshold_alarm_condition_reset_restarts_debounce(session):
    sensor = await _make_sensor(session)
    rule = await AlarmRuleRepository(session).create(
        AlarmRule(
            sensor_id=sensor.id,
            alarm_type=AlarmType.TEMP_HIGH,
            threshold_value=30.0,
            hysteresis=2.0,
            min_duration_seconds=60,
            severity=AlarmSeverity.WARNING,
        )
    )
    await session.commit()
    alarm_repo = AlarmRepository(session)
    engine = AlarmEngine()

    await engine.evaluate(alarm_repo, rule, 35.0, T0)
    await engine.evaluate(alarm_repo, rule, 25.0, T0 + timedelta(seconds=30))  # condition drops, resets timer
    await engine.evaluate(alarm_repo, rule, 35.0, T0 + timedelta(seconds=61))  # only 31s since it came back
    await session.commit()

    assert await alarm_repo.list() == []


async def test_threshold_alarm_clears_only_past_hysteresis_band(session):
    sensor = await _make_sensor(session)
    rule = await AlarmRuleRepository(session).create(
        AlarmRule(
            sensor_id=sensor.id,
            alarm_type=AlarmType.TEMP_HIGH,
            threshold_value=30.0,
            hysteresis=2.0,
            min_duration_seconds=0,
            severity=AlarmSeverity.WARNING,
        )
    )
    await session.commit()
    alarm_repo = AlarmRepository(session)
    engine = AlarmEngine()

    await engine.evaluate(alarm_repo, rule, 35.0, T0)
    await session.commit()
    assert (await alarm_repo.list())[0].state == AlarmState.ACTIVE

    # inside the deadband (28-30) — must stay open, not clear
    await engine.evaluate(alarm_repo, rule, 29.0, T0 + timedelta(seconds=1))
    await session.commit()
    assert (await alarm_repo.list())[0].state == AlarmState.ACTIVE

    # below threshold - hysteresis (< 28) — now it clears
    await engine.evaluate(alarm_repo, rule, 27.0, T0 + timedelta(seconds=2))
    await session.commit()
    alarm = (await alarm_repo.list())[0]
    assert alarm.state == AlarmState.CLEARED
    assert alarm.cleared_at is not None


async def test_new_alarm_opens_after_clear_when_condition_returns(session):
    sensor = await _make_sensor(session)
    rule = await AlarmRuleRepository(session).create(
        AlarmRule(
            sensor_id=sensor.id,
            alarm_type=AlarmType.TEMP_HIGH,
            threshold_value=30.0,
            hysteresis=2.0,
            min_duration_seconds=0,
            severity=AlarmSeverity.WARNING,
        )
    )
    await session.commit()
    alarm_repo = AlarmRepository(session)
    engine = AlarmEngine()

    await engine.evaluate(alarm_repo, rule, 35.0, T0)
    await engine.evaluate(alarm_repo, rule, 27.0, T0 + timedelta(seconds=1))
    await engine.evaluate(alarm_repo, rule, 35.0, T0 + timedelta(seconds=2))
    await session.commit()

    alarms = await alarm_repo.list()
    assert len(alarms) == 2
    assert alarms[0].state == AlarmState.CLEARED
    assert alarms[1].state == AlarmState.ACTIVE


async def test_boolean_alarm_no_debounce_no_hysteresis(session):
    sensor = await SensorRepository(session).create(
        Sensor(tag_name="smoke_a", display_name="Smoke A", sensor_type="SMOKE")
    )
    rule = await AlarmRuleRepository(session).create(
        AlarmRule(
            sensor_id=sensor.id,
            alarm_type=AlarmType.SMOKE,
            hysteresis=0.0,
            min_duration_seconds=0,
            severity=AlarmSeverity.CRITICAL,
        )
    )
    await session.commit()
    alarm_repo = AlarmRepository(session)
    engine = AlarmEngine()

    await engine.evaluate(alarm_repo, rule, 1.0, T0)
    await session.commit()
    assert (await alarm_repo.list())[0].state == AlarmState.ACTIVE

    await engine.evaluate(alarm_repo, rule, 0.0, T0 + timedelta(seconds=1))
    await session.commit()
    assert (await alarm_repo.list())[0].state == AlarmState.CLEARED


async def test_disabled_rule_never_triggers(session):
    sensor = await _make_sensor(session)
    rule = await AlarmRuleRepository(session).create(
        AlarmRule(
            sensor_id=sensor.id,
            alarm_type=AlarmType.TEMP_HIGH,
            threshold_value=30.0,
            hysteresis=2.0,
            min_duration_seconds=0,
            severity=AlarmSeverity.WARNING,
            is_enabled=False,
        )
    )
    await session.commit()
    alarm_repo = AlarmRepository(session)
    engine = AlarmEngine()

    await engine.evaluate(alarm_repo, rule, 100.0, T0)
    await session.commit()
    assert await alarm_repo.list() == []


async def test_acknowledge_transitions_active_to_acknowledged(session):
    sensor = await _make_sensor(session)
    rule = await AlarmRuleRepository(session).create(
        AlarmRule(
            sensor_id=sensor.id,
            alarm_type=AlarmType.TEMP_HIGH,
            threshold_value=30.0,
            hysteresis=2.0,
            min_duration_seconds=0,
            severity=AlarmSeverity.WARNING,
        )
    )
    user = await UserRepository(session).create(
        User(username="op", hashed_password="x", role=UserRole.OPERATOR)
    )
    await session.commit()
    alarm_repo = AlarmRepository(session)
    engine = AlarmEngine()

    await engine.evaluate(alarm_repo, rule, 35.0, T0)
    await session.commit()
    alarm_id = (await alarm_repo.list())[0].id

    acked = await engine.acknowledge(alarm_repo, alarm_id, user.id, T0 + timedelta(seconds=5))
    await session.commit()
    assert acked is not None
    assert acked.state == AlarmState.ACKNOWLEDGED
    assert acked.acknowledged_by == user.id


async def test_acknowledge_ignores_non_active_alarm(session):
    sensor = await _make_sensor(session)
    rule = await AlarmRuleRepository(session).create(
        AlarmRule(
            sensor_id=sensor.id,
            alarm_type=AlarmType.TEMP_HIGH,
            threshold_value=30.0,
            hysteresis=2.0,
            min_duration_seconds=0,
            severity=AlarmSeverity.WARNING,
        )
    )
    await session.commit()
    alarm_repo = AlarmRepository(session)
    already_cleared = await alarm_repo.create(
        Alarm(rule_id=rule.id, sensor_id=sensor.id, state=AlarmState.CLEARED, triggered_at=T0)
    )
    await session.commit()

    engine = AlarmEngine()
    result = await engine.acknowledge(alarm_repo, already_cleared.id, 1, T0 + timedelta(seconds=5))
    assert result is not None
    assert result.state == AlarmState.CLEARED  # unchanged
