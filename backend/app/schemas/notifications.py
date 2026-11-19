from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints

from app.models import AlertDelivery, AlertKind, DeliveryStatus, NotificationChannelKind

ChannelName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class TelegramConnectionIn(BaseModel):
    token: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=256)]
    # Подтверждение смены бота: каналы прежнего бота будут удалены.
    confirm_replace: bool = False


class TelegramConnectionOut(BaseModel):
    connected: bool
    bot_username: str | None


class DiscoveredChat(BaseModel):
    chat_id: int
    title: str
    type: str
    # Чат уже стал Каналом оповещения.
    connected: bool


class NotificationChannelIn(BaseModel):
    name: ChannelName
    telegram_chat_id: int


class NotificationChannelRename(BaseModel):
    name: ChannelName


class AlertDeliveryOut(BaseModel):
    """Доставка оповещения вместе с видом Оповещения и названием канала."""

    alert_kind: AlertKind
    # Момент смены Состояния, о которой Оповещение.
    alert_created_at: datetime
    channel_id: int
    channel_name: str
    status: DeliveryStatus
    attempts: int
    first_attempt_at: datetime | None
    last_attempt_at: datetime | None
    error: str | None
    telegram_error_code: int | None

    @classmethod
    def of(cls, delivery: AlertDelivery) -> AlertDeliveryOut:
        """Нужны загруженные delivery.alert и delivery.channel."""
        return cls(
            alert_kind=delivery.alert.kind,
            alert_created_at=delivery.alert.created_at,
            channel_id=delivery.channel_id,
            channel_name=delivery.channel.name,
            status=delivery.status,
            attempts=delivery.attempts,
            first_attempt_at=delivery.first_attempt_at,
            last_attempt_at=delivery.last_attempt_at,
            error=delivery.error,
            telegram_error_code=delivery.telegram_error_code,
        )


class NotificationChannelOut(BaseModel):
    id: int
    name: str
    kind: NotificationChannelKind
    telegram_chat_id: int
    monitors_count: int
    # Последняя попытка доставить Оповещение в этот канал.
    last_delivery: AlertDeliveryOut | None


class NotificationChannelCreated(NotificationChannelOut):
    # Тестовое сообщение при подключении не дошло; канал всё равно создан.
    test_message_error: str | None
