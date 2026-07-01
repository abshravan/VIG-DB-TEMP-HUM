from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.alarm import Alarm, AlarmRule
from app.models.enums import AlarmSeverity, AlarmState
from app.repositories.base import BaseRepository


class AlarmRuleRepository(BaseRepository[AlarmRule]):
    model = AlarmRule

    async def list_enabled(self) -> list[AlarmRule]:
        result = await self.session.execute(select(AlarmRule).where(AlarmRule.is_enabled.is_(True)))
        return list(result.scalars().all())


class AlarmRepository(BaseRepository[Alarm]):
    model = Alarm

    async def list_active(self) -> list[Alarm]:
        """ACTIVE or ACKNOWLEDGED — anything not yet CLEARED (dashboard 'active alarms').
        Eager-loads `rule` — async sessions can't lazy-load relationships on demand, and
        callers (the Events/alarms API, tests) routinely need `alarm.rule.alarm_type`.
        """
        result = await self.session.execute(
            select(Alarm)
            .where(Alarm.state.in_([AlarmState.ACTIVE, AlarmState.ACKNOWLEDGED]))
            .options(selectinload(Alarm.rule))
        )
        return list(result.scalars().all())

    async def list_filtered(
        self,
        state: AlarmState | None = None,
        severity: AlarmSeverity | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Alarm]:
        """Backs the alarm-history / Events page. Filtering by severity requires a join to
        AlarmRule since severity lives there, not on Alarm itself.
        """
        query = select(Alarm).join(Alarm.rule).options(selectinload(Alarm.rule))
        if state is not None:
            query = query.where(Alarm.state == state)
        if severity is not None:
            query = query.where(AlarmRule.severity == severity)
        if start is not None:
            query = query.where(Alarm.triggered_at >= start)
        if end is not None:
            query = query.where(Alarm.triggered_at <= end)
        query = query.order_by(Alarm.triggered_at.desc())
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_with_rule(self, alarm_id: int) -> Alarm | None:
        result = await self.session.execute(
            select(Alarm).where(Alarm.id == alarm_id).options(selectinload(Alarm.rule))
        )
        return result.scalar_one_or_none()
