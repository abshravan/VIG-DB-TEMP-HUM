"""Import every model so `Base.metadata` is fully populated for Alembic autogenerate."""

from app.models.alarm import Alarm, AlarmRule
from app.models.configuration import Configuration
from app.models.sensor import Sensor
from app.models.sensor_reading import SensorReading, SensorReadingDaily, SensorReadingHourly
from app.models.system_log import SystemLog
from app.models.user import User

__all__ = [
    "Sensor",
    "SensorReading",
    "SensorReadingHourly",
    "SensorReadingDaily",
    "AlarmRule",
    "Alarm",
    "User",
    "SystemLog",
    "Configuration",
]
