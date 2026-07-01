import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.enums import AlarmType, ReadingQuality
from app.models.sensor_reading import SensorReading
from app.plc.base import ConnectionState, TagReadResult
from app.plc.tags import TagMap
from app.repositories import AlarmRepository, AlarmRuleRepository, ReadingRepository, SensorRepository
from app.services.alarm_engine import AlarmEngine
from app.services.validation import ReadFailure, ReadingValidator

logger = logging.getLogger(__name__)

#: Consecutive read failures for one tag before it counts toward the SENSOR_FAILURE alarm.
SENSOR_FAILURE_STREAK_THRESHOLD = 3


class ReadingIngestionService:
    """The glue between the PLC layer and everything downstream (ARCHITECTURE.md's
    PLC -> Poller -> Validation Layer -> Repository -> Alarm Engine pipeline). Wired as the
    `PLCPoller`'s `on_readings` callback and the `ResilientPLCConnection`'s `on_state_change`
    callback. Opens one short-lived DB session per event — the poller is a long-running
    background task, not a request, so it can't use the request-scoped `get_db` dependency.
    """

    def __init__(
        self,
        session_maker: async_sessionmaker[AsyncSession],
        tag_map: TagMap,
        validator: ReadingValidator,
        alarm_engine: AlarmEngine,
    ) -> None:
        self._session_maker = session_maker
        self._tag_map = tag_map
        self._validator = validator
        self._alarm_engine = alarm_engine
        self._failure_streaks: dict[str, int] = {}

    async def handle_readings(self, results: dict[str, TagReadResult], timestamp: datetime) -> None:
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

                if outcome.quality == ReadingQuality.GOOD:
                    for rule in all_rules:
                        if rule.sensor_id == sensor.id:
                            await self._alarm_engine.evaluate(alarm_repo, rule, outcome.value, timestamp)

            await self._evaluate_sensor_failure(all_rules, alarm_repo, timestamp)
            await session.commit()

    async def _evaluate_sensor_failure(self, all_rules, alarm_repo: AlarmRepository, now: datetime) -> None:
        any_failing = any(
            count >= SENSOR_FAILURE_STREAK_THRESHOLD for count in self._failure_streaks.values()
        )
        for rule in all_rules:
            if rule.alarm_type == AlarmType.SENSOR_FAILURE:
                await self._alarm_engine.evaluate(alarm_repo, rule, 1.0 if any_failing else 0.0, now)

    async def handle_connection_state_change(self, state: ConnectionState, now: datetime) -> None:
        async with self._session_maker() as session:
            rule_repo = AlarmRuleRepository(session)
            alarm_repo = AlarmRepository(session)
            is_offline = state != ConnectionState.CONNECTED
            for rule in await rule_repo.list_enabled():
                if rule.alarm_type == AlarmType.PLC_OFFLINE:
                    await self._alarm_engine.evaluate(alarm_repo, rule, 1.0 if is_offline else 0.0, now)
            await session.commit()
