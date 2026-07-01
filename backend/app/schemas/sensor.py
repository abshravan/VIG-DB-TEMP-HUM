from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import SensorType

# Matches the PLC tag map's naming convention (config/plc_tags.yaml) and keeps tag_name safe
# to use unescaped in the CSV export's Content-Disposition header (ARCHITECTURE.md §15) — no
# quotes, CR/LF, or path separators to inject.
TAG_NAME_PATTERN = r"^[A-Za-z0-9_]+$"


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
    tag_name: str = Field(min_length=1, max_length=100, pattern=TAG_NAME_PATTERN)
    display_name: str = Field(min_length=1, max_length=200)
    sensor_type: SensorType
    unit: str | None = Field(default=None, max_length=20)
    location: str | None = Field(default=None, max_length=200)


class SensorUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    location: str | None = Field(default=None, max_length=200)
    is_active: bool | None = None
