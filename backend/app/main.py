import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.database import async_session_maker
from app.core.time import utcnow
from app.plc.base import ConnectionState
from app.plc.connection import ResilientPLCConnection
from app.plc.factory import build_plc_client
from app.plc.poller import PLCPoller
from app.plc.tags import load_tag_map
from app.services.alarm_engine import AlarmEngine
from app.services.ingestion import ReadingIngestionService
from app.services.validation import ReadingValidator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Wires PLC -> Poller -> Validation -> Alarm Engine -> Repository (ARCHITECTURE.md's data
    flow) as background asyncio tasks alongside the API, per §3.5 — one process, not split
    containers. `app.state.plc_connection` is read by the /live and /system/health endpoints.
    """
    settings = get_settings()
    tag_map = load_tag_map(settings.tag_map_path)
    client = build_plc_client(settings)
    validator = ReadingValidator()
    alarm_engine = AlarmEngine()
    ingestion = ReadingIngestionService(async_session_maker, tag_map, validator, alarm_engine)

    async def on_state_change(state: ConnectionState) -> None:
        await ingestion.handle_connection_state_change(state, utcnow())

    connection = ResilientPLCConnection(client, on_state_change=on_state_change)
    poller = PLCPoller(connection, tag_map, ingestion.handle_readings)

    app.state.plc_connection = connection
    app.state.tag_map = tag_map

    await poller.start()
    logger.info("PLC poller started (protocol=%s, address=%s)", settings.plc_protocol, settings.plc_address)
    try:
        yield
    finally:
        await poller.stop()
        await client.disconnect()
        logger.info("PLC poller stopped")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api/v1")

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "internal server error"},
        )

    return app


app = create_app()
