from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, require_roles
from app.core.database import get_db
from app.models.enums import UserRole
from app.models.sensor import Sensor
from app.models.user import User
from app.repositories import SensorRepository
from app.schemas.sensor import SensorCreate, SensorOut, SensorUpdate

router = APIRouter(prefix="/sensors", tags=["sensors"])


@router.get("", response_model=list[SensorOut])
async def list_sensors(current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> list[Sensor]:
    return await SensorRepository(db).list()


@router.post("", response_model=SensorOut, status_code=status.HTTP_201_CREATED)
async def create_sensor(
    payload: SensorCreate,
    _admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: AsyncSession = Depends(get_db),
) -> Sensor:
    repo = SensorRepository(db)
    if await repo.get_by_tag_name(payload.tag_name) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="tag_name already exists")
    return await repo.create(Sensor(**payload.model_dump()))


@router.patch("/{sensor_id}", response_model=SensorOut)
async def update_sensor(
    sensor_id: int,
    payload: SensorUpdate,
    _staff: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.OPERATOR))],
    db: AsyncSession = Depends(get_db),
) -> Sensor:
    repo = SensorRepository(db)
    sensor = await repo.get(sensor_id)
    if sensor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="sensor not found")
    for field_name, value in payload.model_dump(exclude_unset=True).items():
        setattr(sensor, field_name, value)
    return sensor
