from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import UserRole


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: UserRole
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=8, max_length=72)
    role: UserRole = UserRole.VIEWER


class UserUpdate(BaseModel):
    password: str | None = Field(default=None, min_length=8, max_length=72)
    role: UserRole | None = None
    is_active: bool | None = None
