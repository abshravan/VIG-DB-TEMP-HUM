import asyncio
import logging
from collections.abc import Awaitable, Callable

from app.plc.base import ConnectionState, PLCClient

logger = logging.getLogger(__name__)

DEFAULT_BACKOFF_SCHEDULE: tuple[float, ...] = (1.0, 2.0, 5.0, 10.0, 30.0)


class ResilientPLCConnection:
    """Wraps any `PLCClient` with reconnect + exponential backoff (capped) so callers (the
    poller) never see raw connection exceptions — they see a `ConnectionState` and, while
    disconnected, simply get no fresh values. The capped backoff is what keeps this from
    hammering a PLC that's mid-reboot. See ARCHITECTURE.md §4.4.
    """

    def __init__(
        self,
        client: PLCClient,
        backoff_schedule: tuple[float, ...] = DEFAULT_BACKOFF_SCHEDULE,
        on_state_change: Callable[[ConnectionState], Awaitable[None]] | None = None,
    ) -> None:
        self._client = client
        self._backoff_schedule = backoff_schedule
        self._on_state_change = on_state_change
        self._state = ConnectionState.DISCONNECTED
        self._attempt = 0

    @property
    def state(self) -> ConnectionState:
        return self._state

    @property
    def client(self) -> PLCClient:
        return self._client

    async def _set_state(self, state: ConnectionState) -> None:
        if state == self._state:
            return
        self._state = state
        if self._on_state_change is not None:
            await self._on_state_change(state)

    async def ensure_connected(self) -> bool:
        """(Re)connect if necessary. Returns True if connected afterward. Never raises —
        on failure it records ERROR state, sleeps the current backoff step, and returns False
        so the caller's poll loop just tries again next cycle.
        """
        if self._client.is_connected():
            await self._set_state(ConnectionState.CONNECTED)
            self._attempt = 0
            return True

        await self._set_state(ConnectionState.CONNECTING)
        try:
            await self._client.connect()
        except Exception as exc:  # noqa: BLE001 — connection failures are absorbed here, not raised
            logger.warning("PLC connect attempt failed: %s", exc)
            await self._set_state(ConnectionState.ERROR)
            delay = self._backoff_schedule[min(self._attempt, len(self._backoff_schedule) - 1)]
            self._attempt += 1
            await asyncio.sleep(delay)
            return False

        await self._set_state(ConnectionState.CONNECTED)
        self._attempt = 0
        return True
