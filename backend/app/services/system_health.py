import shutil
import time
from pathlib import Path

import psutil
from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.core.time import utcnow
from app.schemas.system import SystemHealthOut

_process_start_monotonic = time.monotonic()


def compute_system_health(plc_connected: bool) -> SystemHealthOut:
    """Shared by `GET /system/health` and the periodic `system_health` WebSocket broadcast
    (ARCHITECTURE.md §7) so there's exactly one place computing CPU/RAM/disk/DB-size/uptime.
    """
    settings = get_settings()
    url = make_url(settings.database_url)
    db_path = Path(url.database) if url.database and url.database != ":memory:" else None
    db_size = db_path.stat().st_size if db_path and db_path.exists() else 0
    disk_target = db_path.parent if db_path and db_path.exists() else Path("/")
    disk = shutil.disk_usage(disk_target)

    return SystemHealthOut(
        cpu_percent=psutil.cpu_percent(interval=None),
        memory_percent=psutil.virtual_memory().percent,
        disk_percent=(disk.used / disk.total * 100) if disk.total else 0.0,
        database_size_bytes=db_size,
        uptime_seconds=time.monotonic() - _process_start_monotonic,
        plc_connected=plc_connected,
        server_time=utcnow(),
    )
