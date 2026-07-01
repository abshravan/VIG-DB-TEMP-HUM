from pydantic import BaseModel, ConfigDict

from app.models.enums import SensorType


class SensorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tag_name: str
    display_name: str
    sensor_type: SensorType
    unit: str | None
    location: str | None
    is_active: bool


class SensorCreate(BaseModel):
    tag_name: str
    display_name: str
    sensor_type: SensorType
    unit: str | None = None
    location: str | None = None


class SensorUpdate(BaseModel):
    display_name: str | None = None
    location: str | None = None
    is_active: bool | None = None
