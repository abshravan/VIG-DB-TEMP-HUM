from datetime import datetime, timedelta

import pytest

from app.models.alarm import AlarmRule
from app.models.enums import AlarmSeverity, AlarmType, SensorType
from app.models.sensor import Sensor
from app.plc.base import ConnectionState, TagReadResult
from app.plc.tags import TagMap
from app.repositories import AlarmRuleRepository, SensorRepository
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
            }
        ]
    }
)


class RecordingBroadcaster:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def __call__(self, message: dict) -> None:
        self.messages.append(message)


async def _seed(session_maker) -> None:
    async with session_maker() as session:
        sensor_repo = SensorRepository(session)
        rule_repo = AlarmRuleRepository(session)
        temp = await sensor_repo.create(
            Sensor(tag_name="temp_a", display_name="Temp A", sensor_type=SensorType.TEMPERATURE)
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
            AlarmRule(alarm_type=AlarmType.PLC_OFFLINE, hysteresis=0.0, min_duration_seconds=0, severity=AlarmSeverity.CRITICAL)
        )
        await session.commit()


async def test_good_reading_broadcasts_reading_message(session_maker):
    await _seed(session_maker)
    broadcaster = RecordingBroadcaster()
    service = ReadingIngestionService(session_maker, TAG_MAP, ReadingValidator(), AlarmEngine(), broadcaster)

    await service.handle_readings({"temp_a": TagReadResult(value=20.0, ok=True)}, T0)

    reading_messages = [m for m in broadcaster.messages if m["type"] == "reading"]
    assert len(reading_messages) == 1
    assert reading_messages[0]["data"]["readings"] == [
        {"sensor_id": 1, "tag_name": "temp_a", "value": 20.0, "quality": "GOOD"}
    ]
    assert reading_messages[0]["data"]["timestamp"] == T0.isoformat()


async def test_no_reading_broadcast_when_nothing_stored(session_maker):
    await _seed(session_maker)
    broadcaster = RecordingBroadcaster()
    service = ReadingIngestionService(session_maker, TAG_MAP, ReadingValidator(), AlarmEngine(), broadcaster)

    await service.handle_readings({}, T0)

    assert not any(m["type"] == "reading" for m in broadcaster.messages)


async def test_threshold_breach_broadcasts_active_alarm(session_maker):
    await _seed(session_maker)
    broadcaster = RecordingBroadcaster()
    service = ReadingIngestionService(session_maker, TAG_MAP, ReadingValidator(), AlarmEngine(), broadcaster)

    await service.handle_readings({"temp_a": TagReadResult(value=35.0, ok=True)}, T0)

    alarm_messages = [m for m in broadcaster.messages if m["type"] == "alarm"]
    assert len(alarm_messages) == 1
    assert alarm_messages[0]["data"]["alarm_type"] == "TEMP_HIGH"
    assert alarm_messages[0]["data"]["severity"] == "WARNING"
    assert alarm_messages[0]["data"]["state"] == "ACTIVE"


async def test_alarm_clear_broadcasts_cleared_alarm(session_maker):
    await _seed(session_maker)
    broadcaster = RecordingBroadcaster()
    service = ReadingIngestionService(session_maker, TAG_MAP, ReadingValidator(), AlarmEngine(), broadcaster)

    await service.handle_readings({"temp_a": TagReadResult(value=35.0, ok=True)}, T0)
    broadcaster.messages.clear()
    await service.handle_readings({"temp_a": TagReadResult(value=20.0, ok=True)}, T0 + timedelta(seconds=1))

    alarm_messages = [m for m in broadcaster.messages if m["type"] == "alarm"]
    assert len(alarm_messages) == 1
    assert alarm_messages[0]["data"]["state"] == "CLEARED"


async def test_no_broadcast_calls_when_broadcaster_not_configured(session_maker):
    await _seed(session_maker)
    service = ReadingIngestionService(session_maker, TAG_MAP, ReadingValidator(), AlarmEngine(), broadcaster=None)

    # must not raise even though there's no broadcaster and a threshold breach occurs
    await service.handle_readings({"temp_a": TagReadResult(value=35.0, ok=True)}, T0)


async def test_connection_state_change_broadcasts_plc_status_and_alarm(session_maker):
    await _seed(session_maker)
    broadcaster = RecordingBroadcaster()
    service = ReadingIngestionService(session_maker, TAG_MAP, ReadingValidator(), AlarmEngine(), broadcaster)

    await service.handle_connection_state_change(ConnectionState.ERROR, T0)

    status_messages = [m for m in broadcaster.messages if m["type"] == "plc_status"]
    assert status_messages == [{"type": "plc_status", "data": {"connected": False, "state": "ERROR"}}]

    alarm_messages = [m for m in broadcaster.messages if m["type"] == "alarm"]
    assert len(alarm_messages) == 1
    assert alarm_messages[0]["data"]["alarm_type"] == "PLC_OFFLINE"
    assert alarm_messages[0]["data"]["state"] == "ACTIVE"


async def test_connection_recovery_broadcasts_connected_status(session_maker):
    await _seed(session_maker)
    broadcaster = RecordingBroadcaster()
    service = ReadingIngestionService(session_maker, TAG_MAP, ReadingValidator(), AlarmEngine(), broadcaster)

    await service.handle_connection_state_change(ConnectionState.ERROR, T0)
    broadcaster.messages.clear()
    await service.handle_connection_state_change(ConnectionState.CONNECTED, T0 + timedelta(seconds=5))

    status_messages = [m for m in broadcaster.messages if m["type"] == "plc_status"]
    assert status_messages == [{"type": "plc_status", "data": {"connected": True, "state": "CONNECTED"}}]
