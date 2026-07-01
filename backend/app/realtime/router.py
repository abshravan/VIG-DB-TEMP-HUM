from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.repositories import UserRepository

router = APIRouter()


@router.websocket("/ws/live")
async def ws_live(websocket: WebSocket, db: AsyncSession = Depends(get_db)) -> None:
    """Pushes `{"type": "reading"|"alarm"|"plc_status"|"system_health", "data": {...}}`
    frames (ARCHITECTURE.md §7) to every connected dashboard client. Browsers can't set a
    custom Authorization header on a WebSocket handshake, so the JWT access token is passed
    as a query parameter instead: `wss://host/ws/live?token=...`.
    """
    token = websocket.query_params.get("token")
    if token is None:
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
            # Clients don't send anything meaningful over this connection; receiving here
            # just keeps the loop alive so we notice a disconnect (WebSocketDisconnect).
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(websocket)
