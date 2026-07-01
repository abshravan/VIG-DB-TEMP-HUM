from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.core.time import utcnow
from app.models.enums import AlarmSeverity, AlarmState
from app.repositories import AlarmRepository, SystemLogRepository
from app.schemas.alarm import AlarmOut
from app.schemas.system_log import SystemLogOut
from app.services.alarm_engine import AlarmEngine

router = APIRouter(tags=["alarms"])


@router.get("/alarms", response_model=list[AlarmOut])
async def list_alarms(
    current_user: CurrentUser,
    state: AlarmState | None = None,
    severity: AlarmSeverity | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[AlarmOut]:
    alarms = await AlarmRepository(db).list_filtered(state=state, severity=severity, start=start, end=end)
    return [AlarmOut.from_alarm(a) for a in alarms]


@router.post("/alarms/{alarm_id}/acknowledge", response_model=AlarmOut)
async def acknowledge_alarm(
    alarm_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> AlarmOut:
    alarm_repo = AlarmRepository(db)
    # Stateless here — acknowledge() only reads/mutates one row by id, no debounce state needed.
    engine = AlarmEngine()
    alarm = await engine.acknowledge(alarm_repo, alarm_id, current_user.id, utcnow())
    if alarm is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="alarm not found")
    # Re-fetch with `rule` eager-loaded; same identity-mapped object, now with the relationship set.
    alarm = await alarm_repo.get_with_rule(alarm_id)
    return AlarmOut.from_alarm(alarm)


@router.get("/events", response_model=list[SystemLogOut])
async def list_events(
    current_user: CurrentUser,
    limit: int = Query(default=100, le=1000),
    db: AsyncSession = Depends(get_db),
) -> list[SystemLogOut]:
    logs = await SystemLogRepository(db).list_recent(limit=limit)
    return [SystemLogOut.model_validate(log) for log in logs]
