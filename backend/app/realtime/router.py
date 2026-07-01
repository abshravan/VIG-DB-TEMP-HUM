import asyncio
import json

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.repositories import UserRepository

router = APIRouter()

AUTH_TIMEOUT_SECONDS = 5.0


@router.websocket("/ws/live")
async def ws_live(websocket: WebSocket, db: AsyncSession = Depends(get_db)) -> None:
    """Pushes `{"type": "reading"|"alarm"|"plc_status"|"system_health", "data": {...}}`
    frames (ARCHITECTURE.md §7) to every connected dashboard client.

    Auth: the connection is accepted first, then the client must send `{"token": "<jwt>"}`
    as its first message within `AUTH_TIMEOUT_SECONDS`. Deliberately *not* a `?token=` query
    parameter — browsers can't set a custom Authorization header on a WS handshake, but a
    query-string token ends up verbatim in nginx/proxy access logs and browser history; a
    first-message handshake keeps the token out of any URL entirely (ARCHITECTURE.md §15).
    """
    await websocket.accept()

    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=AUTH_TIMEOUT_SECONDS)
        token = json.loads(raw).get("token")
    except (TimeoutError, ValueError, AttributeError):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        payload = decode_token(token)
    except JWTError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    username = payload.get("sub")
    if payload.get("type") != "access" or not username:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user = await UserRepository(db).get_by_username(username)
    if user is None or not user.is_active:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    manager = websocket.app.state.connection_manager
    await manager.connect(websocket)
    try:
        while True:
            # Clients don't send anything meaningful over this connection past the initial
            # auth message; receiving here just keeps the loop alive so we notice a disconnect.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(websocket)
