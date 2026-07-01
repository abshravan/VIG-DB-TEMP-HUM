from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.alarm import Alarm, AlarmRule
from app.models.enums import AlarmState
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
