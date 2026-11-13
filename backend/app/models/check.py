from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import UtcDateTime

if TYPE_CHECKING:
    from app.models.monitor import Monitor


class Check(Base):
    __tablename__ = "checks"
    __table_args__ = (Index("ix_checks_monitor_id_started_at", "monitor_id", "started_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    monitor_id: Mapped[int] = mapped_column(ForeignKey("monitors.id", ondelete="CASCADE"))
    started_at: Mapped[datetime] = mapped_column(UtcDateTime)
    duration_ms: Mapped[int] = mapped_column(Integer)
    # None — ответа не было (таймаут, ошибка соединения, запрещённый адрес).
    status_code: Mapped[int | None] = mapped_column(Integer)
    success: Mapped[bool]
    failure_reason: Mapped[str | None] = mapped_column(Text)

    monitor: Mapped[Monitor] = relationship(back_populates="checks")
