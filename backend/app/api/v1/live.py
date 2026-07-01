from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.config import get_settings
from app.core.database import get_db
from app.core.time import utcnow
from app.models.sensor import Sensor
from app.models.sensor_reading import SensorReading
from app.plc.base import ConnectionState
from app.repositories import AlarmRepository, ReadingRepository, SensorRepository
from app.schemas.reading import LiveSensorOut, LiveStatusOut

router = APIRouter(prefix="/live", tags=["live"])


def _to_live_out(sensor: Sensor, latest: SensorReading | None) -> LiveSensorOut:
    settings = get_settings()
    is_stale = True
    if latest is not None:
        is_stale = (utcnow() - latest.timestamp).total_seconds() > settings.live_stale_threshold_seconds
    return LiveSensorOut(
        sensor_id=sensor.id,
        tag_name=sensor.tag_name,
        display_name=sensor.display_name,
        sensor_type=sensor.sensor_type.value,
        unit=sensor.unit,
        value=latest.value if latest else None,
        quality=latest.quality if latest else None,
        timestamp=latest.timestamp if latest else None,
        is_stale=is_stale,
    )


def _plc_connected(request: Request) -> bool:
    connection = getattr(request.app.state, "plc_connection", None)
    return connection is not None and connection.state == ConnectionState.CONNECTED


@router.get("", response_model=LiveStatusOut)
async def get_live_status(
    request: Request, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> LiveStatusOut:
    sensor_repo = SensorRepository(db)
    reading_repo = ReadingRepository(db)
    alarm_repo = AlarmRepository(db)

    sensors = await sensor_repo.list_active()
    sensor_outs = []
    for sensor in sensors:
        latest = await reading_repo.latest_for_sensor(sensor.id)
        sensor_outs.append(_to_live_out(sensor, latest))

    active_alarms = await alarm_repo.list_active()
    return LiveStatusOut(
        plc_connected=_plc_connected(request),
        sensors=sensor_outs,
        active_alarm_count=len(active_alarms),
        server_time=utcnow(),
    )


@router.get("/{sensor_id}", response_model=LiveSensorOut)
async def get_live_sensor(
    sensor_id: int, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> LiveSensorOut:
    sensor_repo = SensorRepository(db)
    sensor = await sensor_repo.get(sensor_id)
    if sensor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="sensor not found")
    latest = await ReadingRepository(db).latest_for_sensor(sensor_id)
    return _to_live_out(sensor, latest)
