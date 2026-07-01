from datetime import datetime, timedelta

import pytest

from app.models.alarm import AlarmRule
from app.models.enums import AlarmSeverity, AlarmState, AlarmType, ReadingQuality, SensorType
from app.models.sensor import Sensor
from app.plc.base import ConnectionState, TagReadResult
from app.plc.tags import TagMap
from app.repositories import AlarmRepository, AlarmRuleRepository, ReadingRepository, SensorRepository
from app.services.alarm_engine import AlarmEngine
from app.services.ingestion import ReadingIngestionService
from app.services.validation import ReadingValidator

pytestmark = pytest.mark.asyncio

T0 = datetime(2026, 1, 1, 12, 0, 0)

TAG_MAP = TagMap.model_validate(
    {
        "tags": [
            {
                "name": "temp_a",
                "kind": "analog",
                "sensor_type": "TEMPERATURE",
                "poll_tier": "normal",
                "s7": {"db": 1, "offset": 0, "type": "REAL"},
                "scale": {"raw_min": 0, "raw_max": 100, "eng_min": 0, "eng_max": 50, "unit": "°C"},
            },
            {
                "name": "door_a",
                "kind": "digital",
                "sensor_type": "DOOR",
                "poll_tier": "fast",
                "s7": {"db": 1, "offset": 8, "type": "BOOL", "bit": 0},
            },
        ]
    }
)


async def _seed(session_maker) -> None:
    async with session_maker() as session:
        sensor_repo = SensorRepository(session)
        rule_repo = AlarmRuleRepository(session)
        temp = await sensor_repo.create(
            Sensor(tag_name="temp_a", display_name="Temp A", sensor_type=SensorType.TEMPERATURE)
        )
        await sensor_repo.create(
            Sensor(tag_name="door_a", display_name="Door A", sensor_type=SensorType.DOOR)
        )
        await rule_repo.create(
            AlarmRule(
                sensor_id=temp.id,
                alarm_type=AlarmType.TEMP_HIGH,
                threshold_value=30.0,
                hysteresis=2.0,
                min_duration_seconds=0,
                severity=AlarmSeverity.WARNING,
            )
        )
        await rule_repo.create(
            AlarmRule(
                alarm_type=AlarmType.SENSOR_FAILURE,
                hysteresis=0.0,
                min_duration_seconds=0,
                severity=AlarmSeverity.WARNING,
            )
        )
        await rule_repo.create(
            AlarmRule(
                alarm_type=AlarmType.PLC_OFFLINE,
                hysteresis=0.0,
                min_duration_seconds=0,
                severity=AlarmSeverity.CRITICAL,
            )
        )
        await session.commit()


async def test_good_reading_is_stored_and_no_alarm_below_threshold(session_maker):
    await _seed(session_maker)
    service = ReadingIngestionService(session_maker, TAG_MAP, ReadingValidator(), AlarmEngine())

    await service.handle_readings({"temp_a": TagReadResult(value=20.0, ok=True)}, T0)

    async with session_maker() as session:
        sensor = await SensorRepository(session).get_by_tag_name("temp_a")
        readings = await ReadingRepository(session).list()
        assert len(readings) == 1
        assert readings[0].sensor_id == sensor.id
        assert readings[0].value == 20.0
        assert readings[0].quality == ReadingQuality.GOOD
        assert await AlarmRepository(session).list_active() == []


async def test_threshold_breach_creates_alarm(session_maker):
    await _seed(session_maker)
    service = ReadingIngestionService(session_maker, TAG_MAP, ReadingValidator(), AlarmEngine())

    await service.handle_readings({"temp_a": TagReadResult(value=35.0, ok=True)}, T0)

    async with session_maker() as session:
        active = await AlarmRepository(session).list_active()
        assert len(active) == 1
        assert active[0].state == AlarmState.ACTIVE
        assert active[0].triggered_value == 35.0


async def test_implausible_reading_stored_as_bad_and_does_not_alarm(session_maker):
    await _seed(session_maker)
    service = ReadingIngestionService(session_maker, TAG_MAP, ReadingValidator(), AlarmEngine())

    # 500 is far outside the 0-50 span -> BAD quality, must not feed the alarm engine
    await service.handle_readings({"temp_a": TagReadResult(value=500.0, ok=True)}, T0)

    async with session_maker() as session:
        readings = await ReadingRepository(session).list()
        assert readings[0].quality == ReadingQuality.BAD
        assert await AlarmRepository(session).list_active() == []


async def test_repeated_read_failures_raise_sensor_failure_alarm(session_maker):
    await _seed(session_maker)
    service = ReadingIngestionService(session_maker, TAG_MAP, ReadingValidator(), AlarmEngine())

    for i in range(3):
        await service.handle_readings(
            {"temp_a": TagReadResult(value=None, ok=False, error="decode error")},
            T0 + timedelta(seconds=i),
        )

    async with session_maker() as session:
        active = await AlarmRepository(session).list_active()
        assert any(a.rule.alarm_type == AlarmType.SENSOR_FAILURE for a in active)
        # a read failure never produces a SensorReading row
        assert await ReadingRepository(session).list() == []


async def test_recovering_after_failures_clears_sensor_failure_alarm(session_maker):
    await _seed(session_maker)
    service = ReadingIngestionService(session_maker, TAG_MAP, ReadingValidator(), AlarmEngine())

    for i in range(3):
        await service.handle_readings(
            {"temp_a": TagReadResult(value=None, ok=False, error="decode error")},
            T0 + timedelta(seconds=i),
        )
    await service.handle_readings({"temp_a": TagReadResult(value=20.0, ok=True)}, T0 + timedelta(seconds=5))

    async with session_maker() as session:
        active = await AlarmRepository(session).list_active()
        assert not any(a.rule.alarm_type == AlarmType.SENSOR_FAILURE for a in active)


async def test_plc_disconnect_raises_plc_offline_alarm(session_maker):
    await _seed(session_maker)
    service = ReadingIngestionService(session_maker, TAG_MAP, ReadingValidator(), AlarmEngine())

    await service.handle_connection_state_change(ConnectionState.ERROR, T0)

    async with session_maker() as session:
        active = await AlarmRepository(session).list_active()
        assert any(a.rule.alarm_type == AlarmType.PLC_OFFLINE for a in active)


async def test_plc_reconnect_clears_plc_offline_alarm(session_maker):
    await _seed(session_maker)
    service = ReadingIngestionService(session_maker, TAG_MAP, ReadingValidator(), AlarmEngine())

    await service.handle_connection_state_change(ConnectionState.ERROR, T0)
    await service.handle_connection_state_change(ConnectionState.CONNECTED, T0 + timedelta(seconds=5))

    async with session_maker() as session:
        active = await AlarmRepository(session).list_active()
        assert not any(a.rule.alarm_type == AlarmType.PLC_OFFLINE for a in active)


async def test_unknown_tag_in_results_is_ignored(session_maker):
    await _seed(session_maker)
    service = ReadingIngestionService(session_maker, TAG_MAP, ReadingValidator(), AlarmEngine())

    # tag not present in this cycle's results at all -> simply skipped, no crash
    await service.handle_readings({}, T0)

    async with session_maker() as session:
        assert await ReadingRepository(session).list() == []
