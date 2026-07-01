from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import LogCategory, LogLevel


class SystemLog(Base):
    """Connection failures, restarts, config changes, backup outcomes — the Events page
    "system logs" feed. `meta` holds category-specific structured detail as JSON text.
    """

    __tablename__ = "system_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    level: Mapped[LogLevel] = mapped_column(SAEnum(LogLevel, native_enum=False, length=10))
    category: Mapped[LogCategory] = mapped_column(SAEnum(LogCategory, native_enum=False, length=20))
    message: Mapped[str] = mapped_column(String(1000))
    meta: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
