from datetime import datetime

from pydantic import BaseModel


class SystemHealthOut(BaseModel):
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    database_size_bytes: int
    uptime_seconds: float
    plc_connected: bool
    server_time: datetime
