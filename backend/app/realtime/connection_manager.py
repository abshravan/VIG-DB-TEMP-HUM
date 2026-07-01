import asyncio
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """In-process pub/sub for `/ws/live` (ARCHITECTURE.md §3.4, §7) — no message broker,
    since a single backend process and a single LAN audience don't need one. Every connected
    dashboard client receives every broadcast message; there is no per-client subscription
    filtering (the frontend store filters/merges by `type` on receipt).
    """

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """Registers an already-accepted connection. Accepting is the caller's
        responsibility (not done here) because `/ws/live` must accept the socket *before* it
        can read the client's first-message auth token — see `app/realtime/router.py`.
        """
        async with self._lock:
            self._connections.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send to every connected client. A client that's gone stale (send fails) is
        dropped rather than allowed to break the broadcast for everyone else.
        """
        async with self._lock:
            targets = list(self._connections)

        dead: list[WebSocket] = []
        for websocket in targets:
            try:
                await websocket.send_json(message)
            except Exception as exc:  # noqa: BLE001 — one dead socket must not stop the broadcast
                logger.debug("dropping dead websocket connection: %s", exc)
                dead.append(websocket)

        if dead:
            async with self._lock:
                for websocket in dead:
                    self._connections.discard(websocket)

    @property
    def connection_count(self) -> int:
        return len(self._connections)
