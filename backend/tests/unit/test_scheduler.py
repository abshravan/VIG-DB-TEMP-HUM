import asyncio
from datetime import datetime, time

import pytest

from app.workers import scheduler
from app.workers.scheduler import parse_hhmm, run_daily, seconds_until


def test_seconds_until_later_today():
    now = datetime(2026, 1, 1, 10, 0, 0)
    assert seconds_until(time(14, 0), now) == 4 * 3600


def test_seconds_until_wraps_to_tomorrow_when_time_has_passed():
    now = datetime(2026, 1, 1, 10, 0, 0)
    assert seconds_until(time(2, 0), now) == 16 * 3600


def test_seconds_until_exactly_now_wraps_to_tomorrow():
    now = datetime(2026, 1, 1, 2, 0, 0)
    assert seconds_until(time(2, 0), now) == 24 * 3600


def test_parse_hhmm():
    assert parse_hhmm("02:00") == time(2, 0)
    assert parse_hhmm("23:45") == time(23, 45)


@pytest.mark.asyncio
async def test_run_daily_invokes_job_repeatedly(monkeypatch):
    monkeypatch.setattr(scheduler, "seconds_until", lambda run_at, now: 0.0)
    calls: list[datetime] = []

    async def job(now: datetime) -> None:
        calls.append(now)

    task = asyncio.create_task(run_daily(job, time(0, 0), "test-job"))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert len(calls) > 1  # the loop actually re-ran the job, not just once


@pytest.mark.asyncio
async def test_run_daily_survives_a_failing_job(monkeypatch):
    monkeypatch.setattr(scheduler, "seconds_until", lambda run_at, now: 0.0)
    calls = 0

    async def failing_job(now: datetime) -> None:
        nonlocal calls
        calls += 1
        raise RuntimeError("boom")

    task = asyncio.create_task(run_daily(failing_job, time(0, 0), "test-job"))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert calls > 1  # kept looping and re-invoking the job despite every call failing
