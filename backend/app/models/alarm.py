from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import AlarmSeverity, AlarmState, AlarmType


class AlarmRule(Base):
    """Configurable threshold/behavior for one alarm type, optionally scoped to a sensor.
    Global rules (sensor_id is null) cover site-wide conditions such as PLC_OFFLINE.
    """

    __tablename__ = "alarm_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    sensor_id: Mapped[int | None] = mapped_column(
        ForeignKey("sensors.id", ondelete="CASCADE"), nullable=True
    )
    alarm_type: Mapped[AlarmType] = mapped_column(SAEnum(AlarmType, native_enum=False, length=20))
    threshold_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    hysteresis: Mapped[float] = mapped_column(Float, default=0.0)
    min_duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    severity: Mapped[AlarmSeverity] = mapped_column(SAEnum(AlarmSeverity, native_enum=False, length=10))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    sensor: Mapped["Sensor | None"] = relationship(back_populates="alarm_rules")
    alarms: Mapped[list["Alarm"]] = relationship(back_populates="rule", cascade="all, delete-orphan")


class Alarm(Base):
    """One row per alarm episode (not per poll) — the alarm/event history."""

    __tablename__ = "alarms"

    id: Mapped[int] = mapped_column(primary_key=True)
    rule_id: Mapped[int] = mapped_column(ForeignKey("alarm_rules.id", ondelete="CASCADE"))
    sensor_id: Mapped[int | None] = mapped_column(
        ForeignKey("sensors.id", ondelete="SET NULL"), nullable=True
    )
    state: Mapped[AlarmState] = mapped_column(
        SAEnum(AlarmState, native_enum=False, length=15), default=AlarmState.ACTIVE
    )
    triggered_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    triggered_at: Mapped[datetime] = mapped_column(DateTime)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    acknowledged_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    message: Mapped[str | None] = mapped_column(String(500), nullable=True)

    rule: Mapped["AlarmRule"] = relationship(back_populates="alarms")
    acknowledged_by_user: Mapped["User | None"] = relationship(foreign_keys=[acknowledged_by])
