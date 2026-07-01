from datetime import datetime

from pydantic import BaseModel

from app.models.enums import ReadingQuality


class LiveSensorOut(BaseModel):
    sensor_id: int
    tag_name: str
    display_name: str
    sensor_type: str
    unit: str | None
    value: float | None
    quality: ReadingQuality | None
    timestamp: datetime | None
    is_stale: bool


class LiveStatusOut(BaseModel):
    plc_connected: bool
    sensors: list[LiveSensorOut]
    active_alarm_count: int
    server_time: datetime


class HistoryPoint(BaseModel):
    timestamp: datetime
    value: float
    quality: ReadingQuality
