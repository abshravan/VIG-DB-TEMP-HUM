import asyncio
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
from app.realtime.connection_manager import ConnectionManager
from app.realtime.health_broadcaster import run_periodic_health_broadcast
from app.realtime.router import router as realtime_router
from app.services.alarm_engine import AlarmEngine
from app.services.ingestion import ReadingIngestionService
from app.services.validation import ReadingValidator
from app.workers.atlas_sync import AtlasSyncWorker, run_periodic_atlas_sync
from app.workers.backup import BackupWorker
from app.workers.retention import RetentionWorker
from app.workers.scheduler import parse_hhmm, run_daily

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _cancel(task: asyncio.Task) -> None:
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Wires PLC -> Poller -> Validation -> Alarm Engine -> Repository -> WebSocket
    (ARCHITECTURE.md's data flow), plus the retention/backup/Atlas-sync background workers
    (§9, §12), all as background asyncio tasks alongside the API, per §3.5 — one process, not
    split containers. `app.state.plc_connection` is read by the /live and /system/health
    endpoints; `app.state.connection_manager` is created in `create_app()` (not here) so
    `/ws/live` works even in tests that don't enter this lifespan.
    """
    settings = get_settings()
    tag_map = load_tag_map(settings.tag_map_path)
    client = build_plc_client(settings)
    validator = ReadingValidator()
    alarm_engine = AlarmEngine()
    connection_manager: ConnectionManager = app.state.connection_manager
    ingestion = ReadingIngestionService(
        async_session_maker, tag_map, validator, alarm_engine, broadcaster=connection_manager.broadcast
    )

    async def on_state_change(state: ConnectionState) -> None:
        await ingestion.handle_connection_state_change(state, utcnow())

    connection = ResilientPLCConnection(client, on_state_change=on_state_change)
    poller = PLCPoller(connection, tag_map, ingestion.handle_readings)

    app.state.plc_connection = connection
    app.state.tag_map = tag_map

    await poller.start()

    retention_worker = RetentionWorker(async_session_maker, raw_retention_days=settings.raw_retention_days)
    backup_worker = BackupWorker(settings=settings)
    atlas_worker = AtlasSyncWorker(
        async_session_maker, settings.atlas_connection_string, settings.atlas_database_name
    )

    background_tasks = [
        asyncio.create_task(
            run_periodic_health_broadcast(connection_manager, lambda: connection.state == ConnectionState.CONNECTED)
        ),
        asyncio.create_task(run_daily(retention_worker.run_once, parse_hhmm(settings.retention_run_at), "retention")),
        asyncio.create_task(run_daily(backup_worker.run_once, parse_hhmm(settings.backup_run_at), "backup")),
        asyncio.create_task(run_periodic_atlas_sync(atlas_worker, settings.atlas_sync_interval_seconds)),
    ]
    logger.info("PLC poller started (protocol=%s, address=%s)", settings.plc_protocol, settings.plc_address)
    logger.info(
        "background workers started (retention@%s, backup@%s, atlas_sync_enabled=%s)",
        settings.retention_run_at,
        settings.backup_run_at,
        atlas_worker.enabled,
    )
    try:
        yield
    finally:
        for task in background_tasks:
            await _cancel(task)
        await poller.stop()
        await client.disconnect()
        logger.info("PLC poller and background workers stopped")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.state.connection_manager = ConnectionManager()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api/v1")
    app.include_router(realtime_router)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "internal server error"},
        )

    return app


app = create_app()
