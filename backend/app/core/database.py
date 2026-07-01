from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

_url = make_url(settings.database_url)
if _url.drivername.startswith("sqlite") and _url.database and _url.database != ":memory:":
    # First run on a fresh checkout/deploy has no data/ dir yet — SQLite won't create it for us.
    Path(_url.database).parent.mkdir(parents=True, exist_ok=True)

engine = create_async_engine(settings.database_url, echo=settings.sql_echo)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

if settings.database_url.startswith("sqlite"):
    # SQLite ignores FK constraints (our ondelete=CASCADE/SET NULL) and defaults to rollback-journal
    # mode unless told otherwise per-connection — neither applies automatically like on PostgreSQL.
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, connection_record) -> None:  # noqa: ANN001, ARG001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


class Base(DeclarativeBase):
    """Shared declarative base. Only standard, dialect-agnostic column types are used across
    all models (Integer/Float/String/DateTime/Boolean, enums stored as plain strings) so the
    same models and Alembic migrations work unchanged against PostgreSQL later.
    """


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: one session per request, committed on success, rolled back on error."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
