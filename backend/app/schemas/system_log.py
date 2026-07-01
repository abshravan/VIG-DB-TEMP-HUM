from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import LogCategory, LogLevel


class SystemLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: datetime
    level: LogLevel
    category: LogCategory
    message: str
    meta: str | None
