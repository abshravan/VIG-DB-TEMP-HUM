from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, require_roles
from app.core.database import get_db
from app.core.time import utcnow
from app.models.enums import UserRole
from app.models.user import User
from app.repositories import AlarmRuleRepository, ConfigurationRepository
from app.schemas.alarm import AlarmRuleOut, AlarmRuleUpdate
from app.schemas.configuration import ConfigurationBulkUpdate, ConfigurationOut

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=list[ConfigurationOut])
async def list_settings(current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> list[ConfigurationOut]:
    return await ConfigurationRepository(db).list_all()


@router.put("", response_model=list[ConfigurationOut])
async def update_settings(
    payload: ConfigurationBulkUpdate,
    admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: AsyncSession = Depends(get_db),
) -> list[ConfigurationOut]:
    repo = ConfigurationRepository(db)
    now = utcnow()
    for key, value in payload.values.items():
        config = await repo.get_by_key(key)
        if config is None:
            continue  # unknown keys are ignored, not auto-created (see ConfigurationBulkUpdate)
        config.value = value
        config.updated_at = now
        config.updated_by = admin.id
    return await repo.list_all()


@router.get("/alarm-rules", response_model=list[AlarmRuleOut])
async def list_alarm_rules(current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> list[AlarmRuleOut]:
    return await AlarmRuleRepository(db).list()


@router.put("/alarm-rules/{rule_id}", response_model=AlarmRuleOut)
async def update_alarm_rule(
    rule_id: int,
    payload: AlarmRuleUpdate,
    _admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: AsyncSession = Depends(get_db),
) -> AlarmRuleOut:
    repo = AlarmRuleRepository(db)
    rule = await repo.get(rule_id)
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="alarm rule not found")
    for field_name, value in payload.model_dump(exclude_unset=True).items():
        setattr(rule, field_name, value)
    return rule
