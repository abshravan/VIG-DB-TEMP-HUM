from datetime import datetime, timedelta

import pytest

from app.models.enums import LogCategory, LogLevel
from app.models.system_log import SystemLog
from app.repositories import SystemLogRepository

pytestmark = pytest.mark.asyncio


async def test_list_recent_orders_newest_first_and_respects_limit(session):
    repo = SystemLogRepository(session)
    base = datetime(2026, 1, 1, 12, 0, 0)
    for i in range(5):
        await repo.create(
            SystemLog(
                timestamp=base + timedelta(minutes=i),
                level=LogLevel.INFO,
                category=LogCategory.SYSTEM_RESTART,
                message=f"event {i}",
            )
        )
    await session.commit()

    recent = await repo.list_recent(limit=3)
    assert [r.message for r in recent] == ["event 4", "event 3", "event 2"]
