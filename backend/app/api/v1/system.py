from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import CurrentUser, require_roles
from app.models.enums import UserRole
from app.models.user import User
from app.plc.base import ConnectionState
from app.plc.simulator import SimulatedPLCClient
from app.schemas.system import (
    SimulatePlcConnectionIn,
    SimulatedTagOut,
    SimulateTagFailureIn,
    SimulateTagValueIn,
    SimulationStatusOut,
    SystemHealthOut,
)
from app.services.system_health import compute_system_health

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health", response_model=SystemHealthOut)
async def get_system_health(request: Request, current_user: CurrentUser) -> SystemHealthOut:
    connection = getattr(request.app.state, "plc_connection", None)
    plc_connected = connection is not None and connection.state == ConnectionState.CONNECTED
    return compute_system_health(plc_connected)


def _require_simulated_client(request: Request) -> SimulatedPLCClient:
    """The `/system/simulate/*` endpoints only make sense when the app is actually running
    against `SimulatedPLCClient` (PLC_PROTOCOL=simulated) — against a real S7/Modbus PLC there
    is nothing here to control.
    """
    connection = getattr(request.app.state, "plc_connection", None)
    client = connection.client if connection is not None else None
    if not isinstance(client, SimulatedPLCClient):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="PLC simulation is not active (set PLC_PROTOCOL=simulated to enable it)",
        )
    return client


@router.get("/simulate", response_model=SimulationStatusOut)
async def get_simulation_status(request: Request, current_user: CurrentUser) -> SimulationStatusOut:
    client = _require_simulated_client(request)
    tag_map = request.app.state.tag_map
    tags = [
        SimulatedTagOut(
            name=tag.name,
            kind=tag.kind,
            sensor_type=tag.sensor_type,
            unit=tag.scale.unit if tag.scale else None,
            eng_min=tag.scale.eng_min if tag.scale else None,
            eng_max=tag.scale.eng_max if tag.scale else None,
            current_value=client.get_value(tag.name),
            failing=client.is_tag_failing(tag.name),
        )
        for tag in tag_map.tags
    ]
    return SimulationStatusOut(active=True, plc_offline=not client.is_connected(), tags=tags)


@router.put("/simulate/tags/{tag_name}", response_model=SimulatedTagOut)
async def set_simulated_tag_value(
    tag_name: str,
    payload: SimulateTagValueIn,
    request: Request,
    _staff: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.OPERATOR))],
) -> SimulatedTagOut:
    client = _require_simulated_client(request)
    tag_map = request.app.state.tag_map
    tag = next((t for t in tag_map.tags if t.name == tag_name), None)
    if tag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown tag")
    if tag.kind == "digital" and not isinstance(payload.value, bool):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="digital tags require a boolean value")
    if tag.kind == "analog" and not isinstance(payload.value, (int, float)):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="analog tags require a numeric value")

    client.set_value(tag_name, payload.value)
    return SimulatedTagOut(
        name=tag.name,
        kind=tag.kind,
        sensor_type=tag.sensor_type,
        unit=tag.scale.unit if tag.scale else None,
        eng_min=tag.scale.eng_min if tag.scale else None,
        eng_max=tag.scale.eng_max if tag.scale else None,
        current_value=client.get_value(tag.name),
        failing=client.is_tag_failing(tag.name),
    )


@router.put("/simulate/tags/{tag_name}/failure", response_model=SimulatedTagOut)
async def set_simulated_tag_failure(
    tag_name: str,
    payload: SimulateTagFailureIn,
    request: Request,
    _staff: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.OPERATOR))],
) -> SimulatedTagOut:
    client = _require_simulated_client(request)
    tag_map = request.app.state.tag_map
    tag = next((t for t in tag_map.tags if t.name == tag_name), None)
    if tag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown tag")

    client.set_tag_failing(tag_name, payload.failing)
    return SimulatedTagOut(
        name=tag.name,
        kind=tag.kind,
        sensor_type=tag.sensor_type,
        unit=tag.scale.unit if tag.scale else None,
        eng_min=tag.scale.eng_min if tag.scale else None,
        eng_max=tag.scale.eng_max if tag.scale else None,
        current_value=client.get_value(tag.name),
        failing=client.is_tag_failing(tag.name),
    )


@router.put("/simulate/plc-connection", response_model=SimulationStatusOut)
async def set_simulated_plc_connection(
    payload: SimulatePlcConnectionIn,
    request: Request,
    _staff: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.OPERATOR))],
) -> SimulationStatusOut:
    client = _require_simulated_client(request)
    client.set_force_disconnected(payload.disconnected)
    return await get_simulation_status(request, _staff)
