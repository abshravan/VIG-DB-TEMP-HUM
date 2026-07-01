import pytest

from app.core.config import Settings
from app.models.enums import LogCategory, LogLevel
from app.repositories import SystemLogRepository
from app.services.startup import mark_clean_shutdown, marker_path_for, record_startup


def _settings_for(db_path) -> Settings:
    return Settings(database_url=f"sqlite+aiosqlite:///{db_path}")


async def test_first_ever_boot_with_no_marker_logs_unclean_restart(tmp_path, session_maker):
    db_path = tmp_path / "monitoring.db"
    settings = _settings_for(db_path)

    await record_startup(session_maker, settings)

    async with session_maker() as session:
        logs = await SystemLogRepository(session).list_recent(limit=10)
    assert len(logs) == 1
    assert logs[0].category == LogCategory.SYSTEM_RESTART
    assert logs[0].level == LogLevel.WARNING
    assert "unclean" in logs[0].message.lower()


async def test_marker_present_after_graceful_shutdown_yields_clean_restart_next_time(tmp_path, session_maker):
    db_path = tmp_path / "monitoring.db"
    settings = _settings_for(db_path)

    mark_clean_shutdown(settings)  # simulate a previous graceful shutdown
    await record_startup(session_maker, settings)

    async with session_maker() as session:
        logs = await SystemLogRepository(session).list_recent(limit=10)
    assert logs[0].level == LogLevel.INFO
    assert logs[0].message == "Clean restart"


async def test_marker_is_consumed_so_a_second_boot_without_shutdown_is_unclean(tmp_path, session_maker):
    db_path = tmp_path / "monitoring.db"
    settings = _settings_for(db_path)

    mark_clean_shutdown(settings)
    await record_startup(session_maker, settings)  # consumes the marker -> clean
    await record_startup(session_maker, settings)  # marker gone, no shutdown in between -> unclean

    async with session_maker() as session:
        logs = await SystemLogRepository(session).list_recent(limit=10)
    assert [log.level for log in logs] == [LogLevel.WARNING, LogLevel.INFO]


async def test_marker_path_is_none_for_in_memory_database(session_maker):
    settings = Settings(database_url="sqlite+aiosqlite:///:memory:")
    assert marker_path_for(settings) is None
    # record_startup must not raise even though there's no marker file to check
    await record_startup(session_maker, settings)


def test_mark_clean_shutdown_creates_parent_directory(tmp_path):
    db_path = tmp_path / "nested" / "monitoring.db"
    settings = _settings_for(db_path)
    mark_clean_shutdown(settings)
    assert marker_path_for(settings).exists()
