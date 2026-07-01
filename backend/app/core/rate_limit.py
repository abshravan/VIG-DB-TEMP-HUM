import time
from collections import defaultdict, deque


class SlidingWindowRateLimiter:
    """In-memory, single-process rate limiter (ARCHITECTURE.md §15) — no Redis or shared
    store needed since this is one backend process on one Pi. Not persisted across restarts,
    an acceptable trade-off: a restart already means re-establishing PLC connections, and a
    determined attacker gaining that window is a much smaller risk than the complexity of a
    durable limiter would be worth here.
    """

    def __init__(self, max_attempts: int, window_seconds: float) -> None:
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds
        self._attempts: dict[str, deque[float]] = defaultdict(deque)

    def _prune(self, key: str, now: float) -> None:
        attempts = self._attempts[key]
        cutoff = now - self._window_seconds
        while attempts and attempts[0] < cutoff:
            attempts.popleft()

    def is_allowed(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        self._prune(key, now)
        return len(self._attempts[key]) < self._max_attempts

    def record_attempt(self, key: str, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        self._prune(key, now)
        self._attempts[key].append(now)
