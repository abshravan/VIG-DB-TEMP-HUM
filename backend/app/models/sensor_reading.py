from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import ReadingQuality


class SensorReading(Base):
    """Raw time series. Retention-limited and rolled up into the hourly/daily tables below
    (see ARCHITECTURE.md §9) so history queries and SD-card storage stay bounded.
    """

    __tablename__ = "sensor_readings"
    __table_args__ = (Index("ix_sensor_readings_sensor_timestamp", "sensor_id", "timestamp"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    sensor_id: Mapped[int] = mapped_column(ForeignKey("sensors.id", ondelete="CASCADE"))
    value: Mapped[float] = mapped_column(Float)
    quality: Mapped[ReadingQuality] = mapped_column(SAEnum(ReadingQuality, native_enum=False, length=10))
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    sensor: Mapped["Sensor"] = relationship(back_populates="readings")


class SensorReadingHourly(Base):
    """Hourly min/max/avg rollup, produced by the nightly retention/rollup worker."""

    __tablename__ = "sensor_readings_hourly"
    __table_args__ = (
        Index("ix_sensor_readings_hourly_sensor_bucket", "sensor_id", "bucket_start", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sensor_id: Mapped[int] = mapped_column(ForeignKey("sensors.id", ondelete="CASCADE"))
    bucket_start: Mapped[datetime] = mapped_column(DateTime, index=True)
    min_value: Mapped[float] = mapped_column(Float)
    max_value: Mapped[float] = mapped_column(Float)
    avg_value: Mapped[float] = mapped_column(Float)
    sample_count: Mapped[int] = mapped_column(Integer)


class SensorReadingDaily(Base):
    """Daily min/max/avg rollup, for long-range history views."""

    __tablename__ = "sensor_readings_daily"
    __table_args__ = (
        Index("ix_sensor_readings_daily_sensor_bucket", "sensor_id", "bucket_start", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sensor_id: Mapped[int] = mapped_column(ForeignKey("sensors.id", ondelete="CASCADE"))
    bucket_start: Mapped[datetime] = mapped_column(DateTime, index=True)
    min_value: Mapped[float] = mapped_column(Float)
    max_value: Mapped[float] = mapped_column(Float)
    avg_value: Mapped[float] = mapped_column(Float)
    sample_count: Mapped[int] = mapped_column(Integer)
