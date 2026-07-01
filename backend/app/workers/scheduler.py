import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, time, timedelta

from app.core.time import utcnow

logger = logging.getLogger(__name__)


def seconds_until(run_at: time, now: datetime) -> float:
    candidate = datetime.combine(now.date(), run_at)
    if candidate <= now:
        candidate += timedelta(days=1)
    return (candidate - now).total_seconds()


def parse_hhmm(value: str) -> time:
    """Parses the "HH:MM" strings used by Settings.retention_run_at / backup_run_at."""
    hour, minute = value.split(":")
    return time(hour=int(hour), minute=int(minute))


async def run_daily(job: Callable[[datetime], Awaitable[None]], run_at: time, job_name: str) -> None:
    """Runs `job(now)` once every day at `run_at` (UTC — the whole app standardizes on
    naive-UTC timestamps, see app/core/time.py). A plain sleep-until-next-run loop rather than
    pulling in a scheduling library for what's just one or two daily jobs (retention rollup,
    local backup) — consistent with how the rest of the backend does periodic work
    (PLCPoller, health_broadcaster).
    """
    while True:
        delay = seconds_until(run_at, utcnow())
        await asyncio.sleep(delay)
        try:
            await job(utcnow())
        except Exception:  # noqa: BLE001 — one bad run must not kill the daily loop
            logger.exception("%s job failed", job_name)
