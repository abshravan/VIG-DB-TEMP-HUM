from sqlalchemy import select

from app.models.system_log import SystemLog
from app.repositories.base import BaseRepository


class SystemLogRepository(BaseRepository[SystemLog]):
    model = SystemLog

    async def list_recent(self, limit: int = 100) -> list[SystemLog]:
        result = await self.session.execute(
            select(SystemLog).order_by(SystemLog.timestamp.desc()).limit(limit)
        )
        return list(result.scalars().all())
