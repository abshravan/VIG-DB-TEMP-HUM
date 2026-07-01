from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.alarm import Alarm
from app.models.enums import AlarmSeverity, AlarmState, AlarmType


class AlarmOut(BaseModel):
    """Built manually from an `Alarm` + its eager-loaded `rule` (alarm_type/severity live on
    the rule, not the alarm instance) rather than via `from_attributes` directly.
    """

    id: int
    rule_id: int
    sensor_id: int | None
    alarm_type: AlarmType
    severity: AlarmSeverity
    state: AlarmState
    triggered_value: float | None
    triggered_at: datetime
    acknowledged_at: datetime | None
    acknowledged_by: int | None
    cleared_at: datetime | None
    message: str | None

    @classmethod
    def from_alarm(cls, alarm: Alarm) -> "AlarmOut":
        return cls(
            id=alarm.id,
            rule_id=alarm.rule_id,
            sensor_id=alarm.sensor_id,
            alarm_type=alarm.rule.alarm_type,
            severity=alarm.rule.severity,
            state=alarm.state,
            triggered_value=alarm.triggered_value,
            triggered_at=alarm.triggered_at,
            acknowledged_at=alarm.acknowledged_at,
            acknowledged_by=alarm.acknowledged_by,
            cleared_at=alarm.cleared_at,
            message=alarm.message,
        )


class AlarmRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sensor_id: int | None
    alarm_type: AlarmType
    threshold_value: float | None
    hysteresis: float
    min_duration_seconds: int
    severity: AlarmSeverity
    is_enabled: bool


class AlarmRuleUpdate(BaseModel):
    threshold_value: float | None = None
    hysteresis: float | None = None
    min_duration_seconds: int | None = None
    severity: AlarmSeverity | None = None
    is_enabled: bool | None = None
