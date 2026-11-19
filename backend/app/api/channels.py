from collections.abc import Sequence
from html import escape
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import validation_error
from app.api.telegram import get_telegram, require_connection
from app.auth.deps import Auth
from app.db.session import get_session
from app.models import AlertDelivery, NotificationChannel, monitor_notification_channels
from app.notifications.alerts import DELIVERY_DETAILS
from app.notifications.telegram import TelegramClient, TelegramError
from app.schemas.notifications import (
    AlertDeliveryOut,
    NotificationChannelCreated,
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


# Последняя попытка доставить Оповещение в канал.
_last_delivery_id = (
    select(AlertDelivery.id)
    .where(
        AlertDelivery.channel_id == NotificationChannel.id,
        AlertDelivery.last_attempt_at.is_not(None),
    )
    .order_by(AlertDelivery.last_attempt_at.desc(), AlertDelivery.id.desc())
    .limit(1)
    .correlate(NotificationChannel)
    .scalar_subquery()
)


def _to_out(
    channel: NotificationChannel, monitors_count: int, last_delivery: AlertDeliveryOut | None
) -> NotificationChannelOut:
    return NotificationChannelOut(
        id=channel.id,
        name=channel.name,
        kind=channel.kind,
        telegram_chat_id=channel.telegram_chat_id,
        monitors_count=monitors_count,
        last_delivery=last_delivery,
    )


async def _deliveries_by_id(session: AsyncSession, ids: list[int]) -> dict[int, AlertDeliveryOut]:
    deliveries = await session.scalars(
        select(AlertDelivery).where(AlertDelivery.id.in_(ids)).options(*DELIVERY_DETAILS)
    )
    return {d.id: AlertDeliveryOut.of(d) for d in deliveries}


async def _channel_outs(
    session: AsyncSession, rows: Sequence[Row[tuple[NotificationChannel, int, int | None]]]
) -> list[NotificationChannelOut]:
    """Каналы из строк (канал, число мониторов, id последней Доставки оповещения)."""
    deliveries = await _deliveries_by_id(session, [d for _, _, d in rows if d is not None])
    return [
        _to_out(channel, count, deliveries.get(delivery_id) if delivery_id else None)
        for channel, count, delivery_id in rows
    ]


async def _channel_out(
    session: AsyncSession, channel: NotificationChannel
) -> NotificationChannelOut:
    rows = await session.execute(
        select(NotificationChannel, _monitors_count, _last_delivery_id).where(
            NotificationChannel.id == channel.id
        )
    )
    [out] = await _channel_outs(session, rows.all())
    return out


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
        select(NotificationChannel, _monitors_count, _last_delivery_id)
        .where(NotificationChannel.user_id == current.id)
        .order_by(NotificationChannel.name, NotificationChannel.id)
    )
    return await _channel_outs(session, rows.all())


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_channel(
    data: NotificationChannelIn, current: Auth, session: Session, telegram: Telegram
) -> NotificationChannelCreated:
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
    await session.commit()
    # Ошибка тестового сообщения не мешает созданию: она возвращается в ответе и не хранится.
    try:
        await telegram.send_message(
            connection.bot_token,
            channel.telegram_chat_id,
            f"✅ Канал оповещения «{escape(data.name)}» подключён к Healthchecker",
        )
        test_message_error = None
    except TelegramError as exc:
        test_message_error = str(exc)
    return NotificationChannelCreated(
        **_to_out(channel, 0, None).model_dump(), test_message_error=test_message_error
    )


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
    # Результат теста не хранится: он нужен только в ответе.
    try:
        await telegram.send_message(
            connection.bot_token, channel.telegram_chat_id, "🔔 Тестовое сообщение Healthchecker"
        )
    except TelegramError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "telegram_error", "message": str(exc)},
        ) from exc
    return await _channel_out(session, channel)
