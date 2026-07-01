import logging
from pathlib import Path

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.time import utcnow
from app.models.enums import LogCategory, LogLevel
from app.models.system_log import SystemLog
from app.repositories import SystemLogRepository

logger = logging.getLogger(__name__)

MARKER_FILENAME = ".clean_shutdown"


def marker_path_for(settings: Settings) -> Path | None:
    url = make_url(settings.database_url)
    if not url.database or url.database == ":memory:":
        return None
    return Path(url.database).parent / MARKER_FILENAME


async def record_startup(session_maker: async_sessionmaker[AsyncSession], settings: Settings) -> None:
    """Distinguishes a clean restart from a crash/power-loss (ARCHITECTURE.md §14). The marker
    is removed here and only rewritten by `mark_clean_shutdown` on graceful shutdown, so its
    absence at this point means the previous run never reached a graceful shutdown.
    """
    marker = marker_path_for(settings)
    was_clean = marker is not None and marker.exists()
    if marker is not None:
        marker.unlink(missing_ok=True)

    message = "Clean restart" if was_clean else "Restart after unclean shutdown (crash or power loss)"
    async with session_maker() as session:
        await SystemLogRepository(session).create(
            SystemLog(
                timestamp=utcnow(),
                level=LogLevel.INFO if was_clean else LogLevel.WARNING,
                category=LogCategory.SYSTEM_RESTART,
                message=message,
            )
        )
        await session.commit()

    if not was_clean:
        logger.warning(message)


def mark_clean_shutdown(settings: Settings) -> None:
    marker = marker_path_for(settings)
    if marker is not None:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()
