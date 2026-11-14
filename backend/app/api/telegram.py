from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import validation_error
from app.db.session import get_session
from app.models import (
    TELEGRAM_CONNECTION_ID,
    NotificationChannel,
    NotificationChannelKind,
    TelegramConnection,
)
from app.notifications.telegram import TelegramClient, TelegramError
from app.schemas.notifications import (
    DiscoveredChat,
    TelegramConnectionIn,
    TelegramConnectionOut,
)

router = APIRouter(prefix="/api/telegram", tags=["telegram"])


def get_telegram(request: Request) -> TelegramClient:
    return request.app.state.telegram


Session = Annotated[AsyncSession, Depends(get_session)]
Telegram = Annotated[TelegramClient, Depends(get_telegram)]

# Бот больше не участник чата: такой чат не предлагаем.
LEFT_STATUSES = {"left", "kicked"}
IS_TELEGRAM_CHANNEL = NotificationChannel.kind == NotificationChannelKind.TELEGRAM


async def require_connection(session: AsyncSession) -> TelegramConnection:
    connection = await session.get(TelegramConnection, TELEGRAM_CONNECTION_ID)
    if connection is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "telegram_not_connected", "message": "Telegram не подключён"},
        )
    return connection


def _chat_title(chat: dict[str, Any]) -> str:
    if chat.get("title"):
        return chat["title"]
    full_name = " ".join(filter(None, (chat.get("first_name"), chat.get("last_name"))))
    return full_name or chat.get("username") or str(chat["id"])


@router.get("")
async def get_connection(session: Session) -> TelegramConnectionOut:
    connection = await session.get(TelegramConnection, TELEGRAM_CONNECTION_ID)
    return TelegramConnectionOut(
        connected=connection is not None,
        bot_username=connection.bot_username if connection else None,
    )


@router.put("")
async def connect(
    data: TelegramConnectionIn, session: Session, telegram: Telegram
) -> TelegramConnectionOut:
    try:
        bot = await telegram.get_me(data.token)
    except TelegramError as exc:
        raise validation_error("token", f"Telegram отклонил токен: {exc}", "invalid_token") from exc

    connection = await session.get(TelegramConnection, TELEGRAM_CONNECTION_ID)
    if connection is not None and connection.bot_id != bot.id:
        # Каналы оповещения — чаты прежнего бота: новый бот в них писать не может.
        channels_count = await session.scalar(
            select(func.count()).select_from(NotificationChannel).where(IS_TELEGRAM_CHANNEL)
        )
        if channels_count and not data.confirm_replace:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "bot_change",
                    "message": "Это другой бот: его подключение удалит Каналы оповещения",
                    "channels_count": channels_count,
                },
            )
        await session.execute(delete(NotificationChannel).where(IS_TELEGRAM_CHANNEL))
        # Непрочитанные обновления относятся к прежнему боту.
        connection.updates_offset = 0

    if connection is None:
        connection = TelegramConnection(id=TELEGRAM_CONNECTION_ID, updates_offset=0)
        session.add(connection)
    connection.bot_token = data.token
    connection.bot_id = bot.id
    connection.bot_username = bot.username
    await session.commit()
    return TelegramConnectionOut(connected=True, bot_username=bot.username)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect(session: Session) -> None:
    await session.execute(delete(NotificationChannel).where(IS_TELEGRAM_CHANNEL))
    await session.execute(delete(TelegramConnection))
    await session.commit()


@router.post("/discover")
async def discover_chats(session: Session, telegram: Telegram) -> list[DiscoveredChat]:
    """Чаты, куда добавили бота, из обновлений после прошлого вызова.

    Обновления после чтения подтверждаются (offset), поэтому найденный чат
    надо подключить сразу: повторный вызов его уже не вернёт.
    """
    connection = await require_connection(session)
    try:
        updates = await telegram.get_updates(connection.bot_token, connection.updates_offset)
    except TelegramError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "telegram_error", "message": f"Ошибка Telegram: {exc}"},
        ) from exc

    chats: dict[int, dict[str, Any]] = {}
    for update in updates:
        if member := update.get("my_chat_member"):
            chat = member["chat"]
            if member["new_chat_member"]["status"] in LEFT_STATUSES:
                chats.pop(chat["id"], None)
            else:
                chats[chat["id"]] = chat
        for key in ("message", "channel_post"):
            if message := update.get(key):
                chats[message["chat"]["id"]] = message["chat"]

    if updates:
        connection.updates_offset = updates[-1]["update_id"] + 1
        await session.commit()

    connected = set(
        await session.scalars(
            select(NotificationChannel.telegram_chat_id).where(
                NotificationChannel.telegram_chat_id.in_(chats)
            )
        )
    )
    return [
        DiscoveredChat(
            chat_id=chat_id,
            title=_chat_title(chat),
            type=chat.get("type", ""),
            connected=chat_id in connected,
        )
        for chat_id, chat in chats.items()
    ]
