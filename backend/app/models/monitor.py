from datetime import datetime
from enum import IntEnum, StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Column, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import UtcDateTime, str_enum, utcnow

if TYPE_CHECKING:
    from app.models.check import Check
    from app.models.notification_channel import NotificationChannel


class HttpMethod(StrEnum):
    GET = "GET"
    HEAD = "HEAD"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    OPTIONS = "OPTIONS"


class CheckInterval(IntEnum):
    """Допустимая периодичность проверок, в секундах."""

    SECONDS_30 = 30
    MINUTE_1 = 60
    MINUTES_5 = 300
    MINUTES_15 = 900
    HOUR_1 = 3600


class MonitorState(StrEnum):
    UNKNOWN = "unknown"
    UP = "up"
    DOWN = "down"
    PAUSED = "paused"


monitor_notification_channels = Table(
    "monitor_notification_channels",
    Base.metadata,
    Column("monitor_id", ForeignKey("monitors.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "channel_id",
        ForeignKey("notification_channels.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Monitor(Base):
    __tablename__ = "monitors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(String(2048))
    method: Mapped[HttpMethod] = mapped_column(str_enum(HttpMethod), default=HttpMethod.GET)
    # Список пар [имя, значение]: порядок и повторяющиеся имена сохраняются.
    headers: Mapped[list[list[str]]] = mapped_column(JSON, default=list)
    body: Mapped[str | None] = mapped_column(Text)
    expected_status: Mapped[int] = mapped_column(Integer, default=200)
    # Подстрока, которую должно содержать тело ответа; None — тело не проверяется.
    expected_body: Mapped[str | None] = mapped_column(Text)
    interval_seconds: Mapped[int] = mapped_column(Integer, default=CheckInterval.MINUTES_5)
    state: Mapped[MonitorState] = mapped_column(
        str_enum(MonitorState), default=MonitorState.UNKNOWN
    )
    state_changed_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    # None — монитор на паузе и исполнителем не выбирается.
    next_check_at: Mapped[datetime | None] = mapped_column(UtcDateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow, onupdate=utcnow)

    channels: Mapped[list[NotificationChannel]] = relationship(
        secondary=monitor_notification_channels,
        back_populates="monitors",
        passive_deletes=True,
    )
    checks: Mapped[list[Check]] = relationship(
        back_populates="monitor",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
