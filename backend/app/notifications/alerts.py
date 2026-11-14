"""Оповещения о мониторах и доставка сообщений в Каналы оповещения."""

import asyncio
import logging
from datetime import datetime, timedelta
from html import escape

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.db.types import utcnow
from app.models import TELEGRAM_CONNECTION_ID, Monitor, NotificationChannel, TelegramConnection
from app.monitoring.scheduler import Alert
from app.monitoring.state import AlertKind
from app.notifications.telegram import TelegramClient, TelegramError

logger = logging.getLogger(__name__)


def format_time(moment: datetime) -> str:
    return moment.strftime("%d.%m.%Y %H:%M:%S UTC")


def format_duration(duration: timedelta) -> str:
    """Длительность простоя: две старшие ненулевые единицы, например «2 ч 5 мин»."""
    seconds = max(int(duration.total_seconds()), 0)
    parts = []
    for unit_seconds, unit in ((86400, "д"), (3600, "ч"), (60, "мин"), (1, "с")):
        value, seconds = divmod(seconds, unit_seconds)
        if value:
            parts.append(f"{value} {unit}")
    return " ".join(parts[:2]) or "0 с"


def alert_text(alert: Alert, now: datetime) -> str:
    monitor = alert.monitor
    name = escape(monitor.name)
    if alert.kind is AlertKind.DOWN:
        return (
            f"🔴 <b>{name}</b> упал\n"
            f"{monitor.method} {escape(monitor.url)}\n"
            f"Причина: {escape(alert.reason or 'неизвестна')}\n"
            f"Время: {format_time(alert.down_since)}"
        )
    return (
        f"🟢 <b>{name}</b> восстановился\n"
        f"{escape(monitor.url)}\n"
        f"Простой: {format_duration(now - alert.down_since)}"
    )


async def deliver(
    telegram: TelegramClient, token: str, channel: NotificationChannel, text: str
) -> None:
    """Отправляет сообщение в Канал оповещения и записывает в него итог; коммит — за вызывающим."""
    try:
        await telegram.send_message(token, channel.telegram_chat_id, text)
        channel.last_delivery_error = None
    except TelegramError as exc:
        logger.warning("Не удалось отправить сообщение в Канал оповещения %s: %s", channel.id, exc)
        channel.last_delivery_error = str(exc)
    channel.last_delivery_at = utcnow()


async def send_alert(
    session_factory: async_sessionmaker[AsyncSession], telegram: TelegramClient, alert: Alert
) -> None:
    async with session_factory() as session:
        connection = await session.get(TelegramConnection, TELEGRAM_CONNECTION_ID)
        monitor = await session.get(
            Monitor, alert.monitor.id, options=[selectinload(Monitor.channels)]
        )
        if monitor is None or not monitor.channels:
            return
        if connection is None:
            logger.warning("Оповещение о мониторе %s не отправлено: нет Telegram", monitor.id)
            return

        text = alert_text(alert, utcnow())
        await asyncio.gather(
            *(deliver(telegram, connection.bot_token, c, text) for c in monitor.channels)
        )
        await session.commit()
