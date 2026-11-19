from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import UtcDateTime, str_enum

if TYPE_CHECKING:
    from app.models.check import Check
    from app.models.monitor import Monitor
    from app.models.notification_channel import NotificationChannel


class AlertKind(StrEnum):
    DOWN = "down"
    RECOVERED = "recovered"


class DeliveryStatus(StrEnum):
    # Не доставлено: повторяется при следующей проверке монитора.
    PENDING = "pending"
    DELIVERED = "delivered"
    # Вытеснено следующим Оповещением или стало неактуальным (пауза, правка монитора).
    CANCELLED = "cancelled"


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    monitor_id: Mapped[int] = mapped_column(
        ForeignKey("monitors.id", ondelete="CASCADE"), index=True
    )
    # Проверка, сменившая Состояние; None — она удалена по сроку хранения истории,
    # а Оповещение осталось, потому что ещё не доставлено.
    check_id: Mapped[int | None] = mapped_column(
        ForeignKey("checks.id", ondelete="SET NULL"), index=True
    )
    kind: Mapped[AlertKind] = mapped_column(str_enum(AlertKind))
    # Причина неуспеха проверки; у восстановления — None.
    reason: Mapped[str | None] = mapped_column(Text)
    # Когда монитор упал: у восстановления от этого момента до created_at считается простой.
    down_since: Mapped[datetime] = mapped_column(UtcDateTime)
    # Момент смены Состояния — начало породившей проверки.
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)

    monitor: Mapped[Monitor] = relationship()
    check: Mapped[Check | None] = relationship()
    deliveries: Mapped[list[AlertDelivery]] = relationship(
        back_populates="alert", cascade="all, delete-orphan", passive_deletes=True
    )


class AlertDelivery(Base):
    """Доставка оповещения: судьба одного Оповещения в одном Канале оповещения."""

    __tablename__ = "alert_deliveries"
    __table_args__ = (UniqueConstraint("alert_id", "channel_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    alert_id: Mapped[int] = mapped_column(ForeignKey("alerts.id", ondelete="CASCADE"))
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("notification_channels.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[DeliveryStatus] = mapped_column(
        str_enum(DeliveryStatus), default=DeliveryStatus.PENDING, index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    first_attempt_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    last_attempt_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    # Причина последней неудачной попытки: описание от Telegram или наша.
    error: Mapped[str | None] = mapped_column(Text)
    telegram_error_code: Mapped[int | None] = mapped_column(Integer)
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger)

    alert: Mapped[Alert] = relationship(back_populates="deliveries")
    channel: Mapped[NotificationChannel] = relationship()
