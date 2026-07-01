from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Configuration(Base):
    """Runtime-editable settings (poll interval, session timeout, sync toggles, ...).
    Read by the poller/alarm engine from an in-memory cache invalidated on update — see
    ARCHITECTURE.md §10. Distinct from the .env-backed infra Settings, which need a restart.
    """

    __tablename__ = "configurations"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    value_type: Mapped[str] = mapped_column(String(20), default="string")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
