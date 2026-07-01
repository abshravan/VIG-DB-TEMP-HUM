from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models.enums import ReadingQuality
from app.repositories import ReadingDailyRepository, ReadingHourlyRepository, ReadingRepository, SensorRepository
from app.schemas.reading import HistoryPoint

router = APIRouter(prefix="/history", tags=["history"])

Resolution = Literal["raw", "hourly", "daily"]


async def _points_for(
    db: AsyncSession, sensor_id: int, start: datetime, end: datetime, resolution: Resolution
) -> list[HistoryPoint]:
    if resolution == "raw":
        rows = await ReadingRepository(db).list_in_range(sensor_id, start, end)
        return [HistoryPoint(timestamp=r.timestamp, value=r.value, quality=r.quality) for r in rows]
    if resolution == "hourly":
        hourly_rows = await ReadingHourlyRepository(db).list_in_range(sensor_id, start, end)
        return [
            HistoryPoint(timestamp=r.bucket_start, value=r.avg_value, quality=ReadingQuality.GOOD)
            for r in hourly_rows
        ]
    daily_rows = await ReadingDailyRepository(db).list_in_range(sensor_id, start, end)
    return [
        HistoryPoint(timestamp=r.bucket_start, value=r.avg_value, quality=ReadingQuality.GOOD)
        for r in daily_rows
    ]


async def _get_sensor_or_404(db: AsyncSession, sensor_id: int):
    sensor = await SensorRepository(db).get(sensor_id)
    if sensor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="sensor not found")
    return sensor


@router.get("", response_model=list[HistoryPoint])
async def get_history(
    current_user: CurrentUser,
    sensor_id: int,
    start: datetime,
    end: datetime,
    resolution: Resolution = "raw",
    db: AsyncSession = Depends(get_db),
) -> list[HistoryPoint]:
    await _get_sensor_or_404(db, sensor_id)
    return await _points_for(db, sensor_id, start, end, resolution)


@router.get("/export")
async def export_history_csv(
    current_user: CurrentUser,
    sensor_id: int,
    start: datetime,
    end: datetime,
    resolution: Resolution = "raw",
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    sensor = await _get_sensor_or_404(db, sensor_id)
    points = await _points_for(db, sensor_id, start, end, resolution)

    def generate():
        yield "timestamp,value,quality\n"
        for point in points:
            yield f"{point.timestamp.isoformat()},{point.value},{point.quality.value}\n"

    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{sensor.tag_name}_history.csv"'},
    )
