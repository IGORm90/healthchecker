from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints

from app.models import NotificationChannelKind

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


class NotificationChannelOut(BaseModel):
    id: int
    name: str
    kind: NotificationChannelKind
    telegram_chat_id: int
    monitors_count: int
    last_delivery_at: datetime | None
    last_delivery_error: str | None
