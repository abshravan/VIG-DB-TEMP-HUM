from sqlalchemy import select

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
        """ACTIVE or ACKNOWLEDGED — anything not yet CLEARED (dashboard 'active alarms')."""
        result = await self.session.execute(
            select(Alarm).where(Alarm.state.in_([AlarmState.ACTIVE, AlarmState.ACKNOWLEDGED]))
        )
        return list(result.scalars().all())
