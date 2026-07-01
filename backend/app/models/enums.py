import enum


class SensorType(str, enum.Enum):
    TEMPERATURE = "TEMPERATURE"
    HUMIDITY = "HUMIDITY"
    SMOKE = "SMOKE"
    WATER_LEAK = "WATER_LEAK"
    DOOR = "DOOR"
    CUSTOM = "CUSTOM"


class ReadingQuality(str, enum.Enum):
    GOOD = "GOOD"
    BAD = "BAD"
    STALE = "STALE"


class AlarmType(str, enum.Enum):
    TEMP_HIGH = "TEMP_HIGH"
    TEMP_LOW = "TEMP_LOW"
    HUMIDITY_HIGH = "HUMIDITY_HIGH"
    HUMIDITY_LOW = "HUMIDITY_LOW"
    SMOKE = "SMOKE"
    DOOR_OPEN = "DOOR_OPEN"
    WATER_LEAK = "WATER_LEAK"
    PLC_OFFLINE = "PLC_OFFLINE"
    SENSOR_FAILURE = "SENSOR_FAILURE"


class AlarmSeverity(str, enum.Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AlarmState(str, enum.Enum):
    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    CLEARED = "CLEARED"


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    OPERATOR = "OPERATOR"
    VIEWER = "VIEWER"


class LogLevel(str, enum.Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogCategory(str, enum.Enum):
    PLC_CONNECTION = "PLC_CONNECTION"
    SYSTEM_RESTART = "SYSTEM_RESTART"
    AUTH = "AUTH"
    CONFIG_CHANGE = "CONFIG_CHANGE"
    BACKUP = "BACKUP"
