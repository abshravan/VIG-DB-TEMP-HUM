from datetime import UTC, datetime


def utcnow() -> datetime:
    """Naive datetime representing the current UTC instant.

    SQLite (via SQLAlchemy) silently strips tzinfo from stored DateTimes on read-back — an
    aware `datetime.now(UTC)` written to a `SensorReading.timestamp` comes back naive. Mixing
    aware "now" values against those naive reads raises `TypeError` the moment they're
    subtracted (e.g. staleness checks), so the whole app standardizes on naive-but-implicitly-
    UTC datetimes instead.
    """
    return datetime.now(UTC).replace(tzinfo=None)
