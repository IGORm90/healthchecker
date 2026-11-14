from html import escape
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import validation_error
from app.api.telegram import get_telegram, require_connection
from app.auth.deps import Auth
from app.db.session import get_session
from app.models import NotificationChannel, monitor_notification_channels
from app.notifications.alerts import deliver
from app.notifications.telegram import TelegramClient
from app.schemas.notifications import (
    NotificationChannelIn,
    NotificationChannelOut,
    NotificationChannelRename,
)

router = APIRouter(prefix="/api/channels", tags=["channels"])

Session = Annotated[AsyncSession, Depends(get_session)]
Telegram = Annotated[TelegramClient, Depends(get_telegram)]

_monitors_count = (
    select(func.count())
    .select_from(monitor_notification_channels)
    .where(monitor_notification_channels.c.channel_id == NotificationChannel.id)
    .correlate(NotificationChannel)
    .scalar_subquery()
)


def _to_out(channel: NotificationChannel, monitors_count: int) -> NotificationChannelOut:
    return NotificationChannelOut(
        id=channel.id,
        name=channel.name,
        kind=channel.kind,
        telegram_chat_id=channel.telegram_chat_id,
        monitors_count=monitors_count,
        last_delivery_at=channel.last_delivery_at,
        last_delivery_error=channel.last_delivery_error,
    )


async def _channel_out(
    session: AsyncSession, channel: NotificationChannel
) -> NotificationChannelOut:
    monitors_count = await session.scalar(
        select(func.count())
        .select_from(monitor_notification_channels)
        .where(monitor_notification_channels.c.channel_id == channel.id)
    )
    return _to_out(channel, monitors_count or 0)


async def _get_channel(session: AsyncSession, channel_id: int, user_id: int) -> NotificationChannel:
    channel = await session.get(NotificationChannel, channel_id)
    # Чужой Канал оповещения неотличим от несуществующего.
    if channel is None or channel.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Канал оповещения не найден"
        )
    return channel


@router.get("")
async def list_channels(current: Auth, session: Session) -> list[NotificationChannelOut]:
    rows = await session.execute(
        select(NotificationChannel, _monitors_count)
        .where(NotificationChannel.user_id == current.id)
        .order_by(NotificationChannel.name, NotificationChannel.id)
    )
    return [_to_out(channel, count) for channel, count in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_channel(
    data: NotificationChannelIn, current: Auth, session: Session, telegram: Telegram
) -> NotificationChannelOut:
    connection = await require_connection(session, current.id)
    duplicate = await session.scalar(
        select(NotificationChannel.id).where(
            NotificationChannel.user_id == current.id,
            NotificationChannel.telegram_chat_id == data.telegram_chat_id,
        )
    )
    if duplicate is not None:
        raise validation_error("telegram_chat_id", "Этот чат уже подключён", "duplicate_channel")

    channel = NotificationChannel(
        user_id=current.id, name=data.name, telegram_chat_id=data.telegram_chat_id
    )
    session.add(channel)
    # Ошибка тестового сообщения не мешает созданию: она видна в списке Каналов оповещения.
    await deliver(
        telegram,
        connection.bot_token,
        channel,
        f"✅ Канал оповещения «{escape(data.name)}» подключён к Healthchecker",
    )
    await session.commit()
    return _to_out(channel, 0)


@router.patch("/{channel_id}")
async def rename_channel(
    channel_id: int, data: NotificationChannelRename, current: Auth, session: Session
) -> NotificationChannelOut:
    channel = await _get_channel(session, channel_id, current.id)
    channel.name = data.name
    await session.commit()
    return await _channel_out(session, channel)


@router.delete("/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_channel(channel_id: int, current: Auth, session: Session) -> None:
    channel = await _get_channel(session, channel_id, current.id)
    await session.delete(channel)
    await session.commit()


@router.post("/{channel_id}/test")
async def test_channel(
    channel_id: int, current: Auth, session: Session, telegram: Telegram
) -> NotificationChannelOut:
    connection = await require_connection(session, current.id)
    channel = await _get_channel(session, channel_id, current.id)
    await deliver(telegram, connection.bot_token, channel, "🔔 Тестовое сообщение Healthchecker")
    await session.commit()
    return await _channel_out(session, channel)
