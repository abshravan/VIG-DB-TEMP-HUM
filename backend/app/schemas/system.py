from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.models.enums import SensorType


class SystemHealthOut(BaseModel):
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    database_size_bytes: int
    uptime_seconds: float
    plc_connected: bool
    server_time: datetime


class SimulatedTagOut(BaseModel):
    """One tag's current state in the PLC simulator, for the admin `/system/simulate` panel."""

    name: str
    kind: Literal["analog", "digital"]
    sensor_type: SensorType
    unit: str | None
    eng_min: float | None
    eng_max: float | None
    current_value: float | bool | None
    failing: bool


class SimulationStatusOut(BaseModel):
    active: bool
    plc_offline: bool
    tags: list[SimulatedTagOut]


class SimulateTagValueIn(BaseModel):
    value: float | bool


class SimulateTagFailureIn(BaseModel):
    failing: bool


class SimulatePlcConnectionIn(BaseModel):
    disconnected: bool
