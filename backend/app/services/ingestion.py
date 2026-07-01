import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.alarm import Alarm
from app.models.enums import AlarmType, ReadingQuality
from app.models.sensor import Sensor
from app.models.sensor_reading import SensorReading
from app.plc.base import ConnectionState, TagReadResult
from app.plc.tags import TagMap
from app.repositories import AlarmRepository, AlarmRuleRepository, ReadingRepository, SensorRepository
from app.services.alarm_engine import AlarmEngine
from app.services.validation import ReadFailure, ReadingValidator

logger = logging.getLogger(__name__)

#: Consecutive read failures for one tag before it counts toward the SENSOR_FAILURE alarm.
SENSOR_FAILURE_STREAK_THRESHOLD = 3

Broadcaster = Callable[[dict[str, Any]], Awaitable[None]]


def _alarm_message(alarm: Alarm) -> dict[str, Any]:
    return {
        "type": "alarm",
        "data": {
            "id": alarm.id,
            "sensor_id": alarm.sensor_id,
            "alarm_type": alarm.rule.alarm_type.value,
            "severity": alarm.rule.severity.value,
            "state": alarm.state.value,
            "triggered_value": alarm.triggered_value,
            "triggered_at": alarm.triggered_at.isoformat(),
            "message": alarm.message,
        },
    }


def _reading_message(readings: list[tuple[Sensor, float, ReadingQuality]], timestamp: datetime) -> dict[str, Any]:
    return {
        "type": "reading",
        "data": {
            "timestamp": timestamp.isoformat(),
            "readings": [
                {
                    "sensor_id": sensor.id,
                    "tag_name": sensor.tag_name,
                    "value": value,
                    "quality": quality.value,
                }
                for sensor, value, quality in readings
            ],
        },
    }


class ReadingIngestionService:
    """The glue between the PLC layer and everything downstream (ARCHITECTURE.md's
    PLC -> Poller -> Validation Layer -> Repository -> Alarm Engine pipeline). Wired as the
    `PLCPoller`'s `on_readings` callback and the `ResilientPLCConnection`'s `on_state_change`
    callback. Opens one short-lived DB session per event — the poller is a long-running
    background task, not a request, so it can't use the request-scoped `get_db` dependency.

    `broadcaster`, if given, is called with a `{"type": ..., "data": ...}` envelope
    (ARCHITECTURE.md §7's WebSocket spec) after readings are stored and whenever an alarm
    changes state or the PLC connection status changes. Optional so Modules 1-4's tests
    (which predate the WebSocket layer) don't need to know about it.
    """

    def __init__(
        self,
        session_maker: async_sessionmaker[AsyncSession],
        tag_map: TagMap,
        validator: ReadingValidator,
        alarm_engine: AlarmEngine,
        broadcaster: Broadcaster | None = None,
    ) -> None:
        self._session_maker = session_maker
        self._tag_map = tag_map
        self._validator = validator
        self._alarm_engine = alarm_engine
        self._broadcaster = broadcaster
        self._failure_streaks: dict[str, int] = {}

    async def _broadcast(self, message: dict[str, Any]) -> None:
        if self._broadcaster is not None:
            await self._broadcaster(message)

    async def handle_readings(self, results: dict[str, TagReadResult], timestamp: datetime) -> None:
        stored: list[tuple[Sensor, float, ReadingQuality]] = []
        changed_alarms: list[Alarm] = []

        async with self._session_maker() as session:
            sensor_repo = SensorRepository(session)
            reading_repo = ReadingRepository(session)
            rule_repo = AlarmRuleRepository(session)
            alarm_repo = AlarmRepository(session)
            all_rules = await rule_repo.list_enabled()

            for tag in self._tag_map.tags:
                result = results.get(tag.name)
                if result is None:
                    continue

                sensor = await sensor_repo.get_by_tag_name(tag.name)
                if sensor is None:
                    logger.warning("no Sensor row for tag %r, skipping", tag.name)
                    continue

                outcome = self._validator.validate(tag, result, timestamp)
                if isinstance(outcome, ReadFailure):
                    self._failure_streaks[tag.name] = self._failure_streaks.get(tag.name, 0) + 1
                    logger.warning("read failed for %s: %s", tag.name, outcome.error)
                    continue
                self._failure_streaks[tag.name] = 0

                await reading_repo.create(
                    SensorReading(
                        sensor_id=sensor.id,
                        value=outcome.value,
                        quality=outcome.quality,
                        timestamp=timestamp,
                    )
                )
                stored.append((sensor, outcome.value, outcome.quality))

                if outcome.quality == ReadingQuality.GOOD:
                    for rule in all_rules:
                        if rule.sensor_id == sensor.id:
                            changed = await self._alarm_engine.evaluate(alarm_repo, rule, outcome.value, timestamp)
                            if changed is not None:
                                changed_alarms.append(changed)

            changed = await self._evaluate_sensor_failure(all_rules, alarm_repo, timestamp)
            changed_alarms.extend(changed)
            await session.commit()

        if stored:
            await self._broadcast(_reading_message(stored, timestamp))
        for alarm in changed_alarms:
            await self._broadcast(_alarm_message(alarm))

    async def _evaluate_sensor_failure(self, all_rules, alarm_repo: AlarmRepository, now: datetime) -> list[Alarm]:
        any_failing = any(
            count >= SENSOR_FAILURE_STREAK_THRESHOLD for count in self._failure_streaks.values()
        )
        changed_alarms: list[Alarm] = []
        for rule in all_rules:
            if rule.alarm_type == AlarmType.SENSOR_FAILURE:
                changed = await self._alarm_engine.evaluate(alarm_repo, rule, 1.0 if any_failing else 0.0, now)
                if changed is not None:
                    changed_alarms.append(changed)
        return changed_alarms

    async def handle_connection_state_change(self, state: ConnectionState, now: datetime) -> None:
        changed_alarms: list[Alarm] = []
        async with self._session_maker() as session:
            rule_repo = AlarmRuleRepository(session)
            alarm_repo = AlarmRepository(session)
            is_offline = state != ConnectionState.CONNECTED
            for rule in await rule_repo.list_enabled():
                if rule.alarm_type == AlarmType.PLC_OFFLINE:
                    changed = await self._alarm_engine.evaluate(alarm_repo, rule, 1.0 if is_offline else 0.0, now)
                    if changed is not None:
                        changed_alarms.append(changed)
            await session.commit()

        await self._broadcast({"type": "plc_status", "data": {"connected": not is_offline, "state": state.value}})
        for alarm in changed_alarms:
            await self._broadcast(_alarm_message(alarm))
