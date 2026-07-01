import asyncio
import logging
from collections.abc import Callable

from app.realtime.connection_manager import ConnectionManager
from app.services.system_health import compute_system_health

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_SECONDS = 10.0


async def run_periodic_health_broadcast(
    connection_manager: ConnectionManager,
    is_plc_connected: Callable[[], bool],
    interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
) -> None:
    """Periodically pushes a `system_health` frame (ARCHITECTURE.md §7) so the System page's
    CPU/RAM/disk/uptime numbers update live without the dashboard having to poll
    `GET /system/health` itself. Only worth running if at least one client is connected —
    skips the (cheap but non-zero) psutil calls otherwise.
    """
    while True:
        await asyncio.sleep(interval_seconds)
        if connection_manager.connection_count == 0:
            continue
        try:
            health = compute_system_health(is_plc_connected())
            await connection_manager.broadcast({"type": "system_health", "data": health.model_dump(mode="json")})
        except Exception:  # noqa: BLE001 — a broadcast hiccup must not kill this background loop
            logger.exception("system_health broadcast failed")
