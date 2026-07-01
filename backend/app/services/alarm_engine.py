from dataclasses import dataclass
from datetime import datetime

from app.models.alarm import Alarm, AlarmRule
from app.models.enums import AlarmState, AlarmType
from app.repositories import AlarmRepository, AlarmRuleRepository

#: Threshold-style alarms: trigger above/below `threshold_value`, clear only once past
#: `hysteresis` beyond it (the deadband that stops the alarm flapping right at the line).
_HIGH_ALARM_TYPES = {AlarmType.TEMP_HIGH, AlarmType.HUMIDITY_HIGH}
_LOW_ALARM_TYPES = {AlarmType.TEMP_LOW, AlarmType.HUMIDITY_LOW}

#: Boolean-style alarms: condition is simply true/false (encoded as 1.0/0.0 by the caller),
#: no hysteresis needed — clears the instant the condition is no longer true.
_BOOLEAN_ALARM_TYPES = {
    AlarmType.SMOKE,
    AlarmType.WATER_LEAK,
    AlarmType.DOOR_OPEN,
    AlarmType.PLC_OFFLINE,
    AlarmType.SENSOR_FAILURE,
}


def _is_trigger_condition(rule: AlarmRule, value: float) -> bool:
    if rule.alarm_type in _HIGH_ALARM_TYPES:
        return value > rule.threshold_value
    if rule.alarm_type in _LOW_ALARM_TYPES:
        return value < rule.threshold_value
    if rule.alarm_type in _BOOLEAN_ALARM_TYPES:
        return value >= 0.5
    raise ValueError(f"unhandled alarm type: {rule.alarm_type}")


def _is_clear_condition(rule: AlarmRule, value: float) -> bool:
    if rule.alarm_type in _HIGH_ALARM_TYPES:
        return value < (rule.threshold_value - rule.hysteresis)
    if rule.alarm_type in _LOW_ALARM_TYPES:
        return value > (rule.threshold_value + rule.hysteresis)
    if rule.alarm_type in _BOOLEAN_ALARM_TYPES:
        return value < 0.5
    raise ValueError(f"unhandled alarm type: {rule.alarm_type}")


def _message_for(rule: AlarmRule, value: float) -> str:
    return f"{rule.alarm_type.value} triggered (value={value:g})"


@dataclass
class _AlarmCandidate:
    """In-memory state for one rule, tracked across poll cycles: when its trigger condition
    first became true (pending debounce) and the DB id of the currently open Alarm, if any.
    """

    condition_since: datetime | None = None
    open_alarm_id: int | None = None


class AlarmEngine:
    """Threshold evaluation, hysteresis, and debounce for all nine alarm types
    (ARCHITECTURE.md §8). Owns in-memory debounce/candidate state across poll cycles, so a
    single instance must be reused for the process lifetime — repositories are passed in per
    call instead of held on `self`, since they're bound to a short-lived per-cycle DB session.
    """

    def __init__(self) -> None:
        self._candidates: dict[int, _AlarmCandidate] = {}

    async def evaluate(
        self,
        alarm_repo: AlarmRepository,
        rule: AlarmRule,
        value: float,
        now: datetime,
    ) -> Alarm | None:
        """Returns the `Alarm` that just changed state (newly created or newly cleared) this
        call, or `None` if nothing changed — callers (the ingestion pipeline) use this to know
        what to broadcast over the WebSocket without re-deriving it from scratch.
        """
        if not rule.is_enabled:
            return None
        candidate = self._candidates.setdefault(rule.id, _AlarmCandidate())

        if candidate.open_alarm_id is None:
            if _is_trigger_condition(rule, value):
                if candidate.condition_since is None:
                    candidate.condition_since = now
                elapsed = (now - candidate.condition_since).total_seconds()
                if elapsed >= rule.min_duration_seconds:
                    alarm = await alarm_repo.create(
                        Alarm(
                            rule_id=rule.id,
                            sensor_id=rule.sensor_id,
                            state=AlarmState.ACTIVE,
                            triggered_value=value,
                            triggered_at=now,
                            message=_message_for(rule, value),
                        )
                    )
                    candidate.open_alarm_id = alarm.id
                    alarm.rule = rule  # avoid a re-fetch just to broadcast alarm_type/severity
                    return alarm
            else:
                candidate.condition_since = None
            return None

        if _is_clear_condition(rule, value):
            alarm = await alarm_repo.get(candidate.open_alarm_id)
            candidate.open_alarm_id = None
            candidate.condition_since = None
            if alarm is not None and alarm.state != AlarmState.CLEARED:
                alarm.state = AlarmState.CLEARED
                alarm.cleared_at = now
                alarm.rule = rule
                return alarm
        return None

    async def acknowledge(self, alarm_repo: AlarmRepository, alarm_id: int, user_id: int, now: datetime) -> Alarm | None:
        alarm = await alarm_repo.get(alarm_id)
        if alarm is None or alarm.state != AlarmState.ACTIVE:
            return alarm
        alarm.state = AlarmState.ACKNOWLEDGED
        alarm.acknowledged_at = now
        alarm.acknowledged_by = user_id
        return alarm
