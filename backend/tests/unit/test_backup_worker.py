import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app.core.config import Settings
from app.workers.backup import DAILY_KEEP, MONTHLY_KEEP, BackupWorker

pytestmark = pytest.mark.asyncio


def _make_settings_for(db_path: Path) -> Settings:
    return Settings(database_url=f"sqlite+aiosqlite:///{db_path}")


def _make_real_sqlite_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, value TEXT)")
    conn.execute("INSERT INTO t (value) VALUES ('hello')")
    conn.commit()
    conn.close()


async def test_run_once_creates_a_restorable_backup(tmp_path):
    db_path = tmp_path / "data" / "monitoring.db"
    db_path.parent.mkdir()
    _make_real_sqlite_db(db_path)

    worker = BackupWorker(settings=_make_settings_for(db_path))
    result = await worker.run_once(datetime(2026, 1, 1, 2, 0, 0))

    assert result is not None
    assert result.exists()
    conn = sqlite3.connect(result)
    rows = conn.execute("SELECT value FROM t").fetchall()
    conn.close()
    assert rows == [("hello",)]


async def test_backup_dir_defaults_to_sibling_of_data_dir(tmp_path):
    db_path = tmp_path / "data" / "monitoring.db"
    db_path.parent.mkdir()
    _make_real_sqlite_db(db_path)

    worker = BackupWorker(settings=_make_settings_for(db_path))
    await worker.run_once(datetime(2026, 1, 1, 2, 0, 0))

    assert (tmp_path / "backups").is_dir()
    assert list((tmp_path / "backups").glob("monitoring-*.db"))


async def test_run_once_with_missing_database_returns_none(tmp_path):
    db_path = tmp_path / "data" / "monitoring.db"  # never created
    worker = BackupWorker(settings=_make_settings_for(db_path))
    result = await worker.run_once(datetime(2026, 1, 1, 2, 0, 0))
    assert result is None


async def test_rotation_drops_the_oldest_snapshots_once_past_daily_keep(tmp_path):
    db_path = tmp_path / "data" / "monitoring.db"
    db_path.parent.mkdir()
    _make_real_sqlite_db(db_path)
    backup_dir = tmp_path / "backups"

    worker = BackupWorker(backup_dir=backup_dir, settings=_make_settings_for(db_path))
    base = datetime(2026, 1, 1, 2, 0, 0)
    for i in range(DAILY_KEEP + 5):
        await worker.run_once(base + timedelta(days=i))

    remaining = sorted(backup_dir.glob("monitoring-*.db"))
    # DAILY_KEEP most recent are always kept, plus (since everything here falls in the same
    # calendar month) at most one extra monthly representative from the days just before that
    # window — the oldest snapshots must still be gone.
    assert DAILY_KEEP <= len(remaining) <= DAILY_KEEP + 1
    assert "monitoring-20260101" not in {p.stem for p in remaining}
    assert any(p.stem.startswith("monitoring-20260119") for p in remaining)  # most recent day kept


async def test_rotation_keeps_monthly_representatives_beyond_daily_window(tmp_path):
    db_path = tmp_path / "data" / "monitoring.db"
    db_path.parent.mkdir()
    _make_real_sqlite_db(db_path)
    backup_dir = tmp_path / "backups"

    worker = BackupWorker(backup_dir=backup_dir, settings=_make_settings_for(db_path))
    base = datetime(2025, 1, 1, 2, 0, 0)
    # simulate roughly 15 months of nightly backups (one every ~5 days keeps the test fast)
    for i in range(90):
        await worker.run_once(base + timedelta(days=5 * i))

    remaining = sorted(backup_dir.glob("monitoring-*.db"))
    # DAILY_KEEP most recent, plus at most MONTHLY_KEEP older monthly representatives
    assert len(remaining) <= DAILY_KEEP + MONTHLY_KEEP
    assert len(remaining) > DAILY_KEEP  # confirms some monthly history survived, not just recent
