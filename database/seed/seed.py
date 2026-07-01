"""Seed default admin user, example sensors, and default alarm rules.

Run with the backend's virtualenv so `app` resolves (backend was installed with
`pip install -e .`):

    backend/.venv/bin/python database/seed/seed.py

Idempotent: safe to run multiple times, existing rows are left untouched.
"""

import asyncio
import os

from app.core.database import async_session_maker
from app.core.security import hash_password
from app.models.enums import AlarmSeverity, AlarmType, SensorType, UserRole
from app.repositories import AlarmRuleRepository, SensorRepository, UserRepository
from app.models.alarm import AlarmRule
from app.models.sensor import Sensor
from app.models.user import User

DEFAULT_SENSORS = [
    dict(
        tag_name="temp_rack_a",
        display_name="Rack A Temperature",
        sensor_type=SensorType.TEMPERATURE,
        unit="°C",
        location="Rack A",
    ),
    dict(
        tag_name="humidity_room",
        display_name="Room Humidity",
        sensor_type=SensorType.HUMIDITY,
        unit="%RH",
        location="Server Room",
    ),
    dict(
        tag_name="smoke_main",
        display_name="Smoke Detector",
        sensor_type=SensorType.SMOKE,
        unit=None,
        location="Server Room",
    ),
    dict(
        tag_name="water_leak_floor",
        display_name="Floor Water Leak Sensor",
        sensor_type=SensorType.WATER_LEAK,
        unit=None,
        location="Server Room Floor",
    ),
    dict(
        tag_name="door_main",
        display_name="Main Door",
        sensor_type=SensorType.DOOR,
        unit=None,
        location="Server Room Entrance",
    ),
]

# (sensor tag_name or None for global, alarm_type, threshold, hysteresis, min_duration_seconds, severity)
DEFAULT_ALARM_RULES = [
    ("temp_rack_a", AlarmType.TEMP_HIGH, 30.0, 2.0, 60, AlarmSeverity.WARNING),
    ("temp_rack_a", AlarmType.TEMP_LOW, 10.0, 2.0, 60, AlarmSeverity.WARNING),
    ("humidity_room", AlarmType.HUMIDITY_HIGH, 70.0, 5.0, 120, AlarmSeverity.WARNING),
    ("humidity_room", AlarmType.HUMIDITY_LOW, 20.0, 5.0, 120, AlarmSeverity.WARNING),
    ("smoke_main", AlarmType.SMOKE, None, 0.0, 0, AlarmSeverity.CRITICAL),
    ("water_leak_floor", AlarmType.WATER_LEAK, None, 0.0, 0, AlarmSeverity.CRITICAL),
    ("door_main", AlarmType.DOOR_OPEN, None, 0.0, 300, AlarmSeverity.INFO),
    (None, AlarmType.PLC_OFFLINE, None, 0.0, 10, AlarmSeverity.CRITICAL),
    (None, AlarmType.SENSOR_FAILURE, None, 0.0, 0, AlarmSeverity.WARNING),
]


async def seed() -> None:
    async with async_session_maker() as session:
        sensor_repo = SensorRepository(session)
        user_repo = UserRepository(session)
        rule_repo = AlarmRuleRepository(session)

        sensors_by_tag: dict[str, Sensor] = {}
        for spec in DEFAULT_SENSORS:
            existing = await sensor_repo.get_by_tag_name(spec["tag_name"])
            if existing is None:
                existing = await sensor_repo.create(Sensor(**spec))
                print(f"created sensor: {spec['tag_name']}")
            sensors_by_tag[spec["tag_name"]] = existing

        admin = await user_repo.get_by_username("admin")
        if admin is None:
            password = os.environ.get("SEED_ADMIN_PASSWORD", "ChangeMe123!")
            if "SEED_ADMIN_PASSWORD" not in os.environ:
                print("WARNING: SEED_ADMIN_PASSWORD not set — using insecure default, change it after login.")
            await user_repo.create(
                User(username="admin", hashed_password=hash_password(password), role=UserRole.ADMIN)
            )
            print("created user: admin")

        existing_rules = await rule_repo.list()
        existing_keys = {(r.sensor_id, r.alarm_type) for r in existing_rules}
        for tag_name, alarm_type, threshold, hysteresis, min_duration, severity in DEFAULT_ALARM_RULES:
            sensor_id = sensors_by_tag[tag_name].id if tag_name else None
            if (sensor_id, alarm_type) in existing_keys:
                continue
            await rule_repo.create(
                AlarmRule(
                    sensor_id=sensor_id,
                    alarm_type=alarm_type,
                    threshold_value=threshold,
                    hysteresis=hysteresis,
                    min_duration_seconds=min_duration,
                    severity=severity,
                )
            )
            print(f"created alarm rule: {tag_name or 'GLOBAL'} / {alarm_type.value}")

        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
