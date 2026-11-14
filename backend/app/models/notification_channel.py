from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import UtcDateTime, str_enum
from app.models.monitor import monitor_notification_channels

if TYPE_CHECKING:
    from app.models.monitor import Monitor


class NotificationChannelKind(StrEnum):
    TELEGRAM = "telegram"


class NotificationChannel(Base):
    __tablename__ = "notification_channels"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[NotificationChannelKind] = mapped_column(
        str_enum(NotificationChannelKind),
        default=NotificationChannelKind.TELEGRAM,
    )
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    last_delivery_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    # None — последняя отправка прошла успешно (или отправок ещё не было).
    last_delivery_error: Mapped[str | None] = mapped_column(Text)

    monitors: Mapped[list[Monitor]] = relationship(
        secondary=monitor_notification_channels,
        back_populates="channels",
        passive_deletes=True,
    )
