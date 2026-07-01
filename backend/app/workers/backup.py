import asyncio
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from sqlalchemy.engine import make_url

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

DAILY_KEEP = 14
MONTHLY_KEEP = 12


class BackupWorker:
    """Nightly SQLite backup (ARCHITECTURE.md §12). Uses sqlite3's online backup API — not a
    raw file copy — so the snapshot is crash-consistent even against a live WAL-mode database,
    then rotates old snapshots: the most recent `DAILY_KEEP` are always kept, plus one
    representative per month for `MONTHLY_KEEP` months beyond that.
    """

    def __init__(self, backup_dir: Path | None = None, settings: Settings | None = None) -> None:
        settings = settings or get_settings()
        url = make_url(settings.database_url)
        self._db_path = Path(url.database) if url.database and url.database != ":memory:" else None
        self._backup_dir = backup_dir or (
            self._db_path.parent.parent / "backups" if self._db_path else Path("backups")
        )

    async def run_once(self, now: datetime) -> Path | None:
        if self._db_path is None or not self._db_path.exists():
            logger.warning("backup: no database file to back up (in-memory DB?)")
            return None

        self._backup_dir.mkdir(parents=True, exist_ok=True)
        destination = self._backup_dir / f"monitoring-{now.strftime('%Y%m%d-%H%M%S')}.db"

        await asyncio.to_thread(self._backup_sync, destination)
        logger.info("backup: wrote %s", destination)
        self._rotate()
        return destination

    def _backup_sync(self, destination: Path) -> None:
        source_conn = sqlite3.connect(self._db_path)
        dest_conn = sqlite3.connect(destination)
        try:
            source_conn.backup(dest_conn)
        finally:
            dest_conn.close()
            source_conn.close()

    def _rotate(self) -> None:
        backups = sorted(self._backup_dir.glob("monitoring-*.db"))
        if len(backups) <= DAILY_KEEP:
            return

        recent = backups[-DAILY_KEEP:]
        older = backups[:-DAILY_KEEP]

        # one representative (the latest in that month, since `older` is sorted ascending)
        # per month, for the most recent MONTHLY_KEEP distinct months.
        monthly_representative: dict[str, Path] = {}
        for path in older:
            month_key = path.stem.split("-")[1][:6]  # "monitoring-YYYYMMDD-HHMMSS" -> "YYYYMM"
            monthly_representative[month_key] = path

        keep_months = sorted(monthly_representative.keys())[-MONTHLY_KEEP:]
        keep_paths = set(recent) | {monthly_representative[month] for month in keep_months}

        for path in backups:
            if path not in keep_paths:
                path.unlink()
                logger.info("backup: pruned old snapshot %s", path)
