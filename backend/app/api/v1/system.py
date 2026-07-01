from fastapi import APIRouter, Request

from app.api.deps import CurrentUser
from app.plc.base import ConnectionState
from app.schemas.system import SystemHealthOut
from app.services.system_health import compute_system_health

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health", response_model=SystemHealthOut)
async def get_system_health(request: Request, current_user: CurrentUser) -> SystemHealthOut:
    connection = getattr(request.app.state, "plc_connection", None)
    plc_connected = connection is not None and connection.state == ConnectionState.CONNECTED
    return compute_system_health(plc_connected)
