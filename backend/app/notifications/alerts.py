"""Оповещения о мониторах и их Доставки в Каналы оповещения."""

import asyncio
import logging
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime, timedelta
from html import escape
from typing import Any

from sqlalchemy import Select, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.db.types import utcnow
from app.models import (
    Alert,
    AlertDelivery,
    AlertKind,
    DeliveryStatus,
    Monitor,
    TelegramConnection,
)
from app.notifications.telegram import TelegramClient, TelegramError

logger = logging.getLogger(__name__)

NO_CONNECTION = "нет Подключения Telegram"
IS_PENDING = AlertDelivery.status == DeliveryStatus.PENDING
# Что нужно, чтобы показать Доставку: её Оповещение и канал.
DELIVERY_DETAILS = (selectinload(AlertDelivery.alert), selectinload(AlertDelivery.channel))


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


def alert_text(monitor: Monitor, alert: Alert, *, first_attempt_at: datetime | None) -> str:
    """Текст Оповещения; first_attempt_at — у повторной отправки, когда была первая попытка."""
    name = escape(monitor.name)
    if alert.kind is AlertKind.DOWN:
        text = (
            f"🔴 <b>{name}</b> упал\n"
            f"{monitor.method} {escape(monitor.url)}\n"
            f"Причина: {escape(alert.reason or 'неизвестна')}\n"
            f"Время: {format_time(alert.down_since)}"
        )
    else:
        text = (
            f"🟢 <b>{name}</b> восстановился\n"
            f"{escape(monitor.url)}\n"
            f"Простой: {format_duration(alert.created_at - alert.down_since)}"
        )
    if first_attempt_at is not None:
        text += f"\n⚠️ Повторная попытка: первая не удалась {format_time(first_attempt_at)}"
    return text


async def cancel_pending(
    session: AsyncSession, monitor_id: int, channel_ids: Collection[int] | None = None
) -> None:
    """Отменяет недоставленные Оповещения монитора — все или только в эти каналы."""
    alert_ids = select(Alert.id).where(Alert.monitor_id == monitor_id)
    statement = update(AlertDelivery).where(AlertDelivery.alert_id.in_(alert_ids), IS_PENDING)
    if channel_ids is not None:
        statement = statement.where(AlertDelivery.channel_id.in_(channel_ids))
    await session.execute(
        statement.values(status=DeliveryStatus.CANCELLED).execution_options(
            synchronize_session=False
        )
    )


def pending_deliveries(monitor_ids: Collection[int]) -> Select[tuple[AlertDelivery]]:
    """Недоставленные Оповещения мониторов по порядку, с Оповещением, монитором и каналом."""
    return (
        select(AlertDelivery)
        .join(Alert)
        .where(Alert.monitor_id.in_(monitor_ids), IS_PENDING)
        .options(selectinload(AlertDelivery.alert).selectinload(Alert.monitor), *DELIVERY_DETAILS)
        .order_by(Alert.created_at, AlertDelivery.id)
    )


@dataclass(frozen=True)
class _Attempt:
    delivery_id: int
    chat_id: int
    text: str


async def _try_deliver(
    telegram: TelegramClient, token: str | None, attempt: _Attempt
) -> dict[str, Any]:
    """Поля Доставки по итогу попытки."""
    if token is None:
        return {"error": NO_CONNECTION, "telegram_error_code": None}
    try:
        message_id = await telegram.send_message(token, attempt.chat_id, attempt.text)
    except TelegramError as exc:
        logger.warning("Доставка оповещения %s не удалась: %s", attempt.delivery_id, exc)
        return {"error": str(exc), "telegram_error_code": exc.error_code}
    except Exception:
        # Сбой одного канала не должен мешать остальным.
        logger.exception("Сбой доставки оповещения %s", attempt.delivery_id)
        return {"error": "внутренняя ошибка Healthchecker", "telegram_error_code": None}
    return {
        "status": DeliveryStatus.DELIVERED,
        "error": None,
        "telegram_error_code": None,
        "telegram_message_id": message_id,
    }


async def deliver_pending(
    session_factory: async_sessionmaker[AsyncSession], telegram: TelegramClient, monitor_id: int
) -> None:
    """Пытается доставить все недоставленные Оповещения монитора, по разу в каждый канал.

    Сообщения уходят вне транзакции, а итог каждой Доставки пишется отдельным UPDATE: пока
    шла отправка, канал или монитор могли удалить, и это не должно отменить итог остальных.
    """
    async with session_factory() as session:
        deliveries = (await session.scalars(pending_deliveries([monitor_id]))).all()
        if not deliveries:
            return
        # Оповещения идут через бота владельца монитора (ADR 0001).
        token = await session.scalar(
            select(TelegramConnection.bot_token)
            .join(Monitor, Monitor.user_id == TelegramConnection.user_id)
            .where(Monitor.id == monitor_id)
        )
        attempts = [
            _Attempt(
                delivery_id=d.id,
                chat_id=d.channel.telegram_chat_id,
                text=alert_text(d.alert.monitor, d.alert, first_attempt_at=d.first_attempt_at),
            )
            for d in deliveries
        ]

    now = utcnow()
    outcomes = await asyncio.gather(*(_try_deliver(telegram, token, a) for a in attempts))
    async with session_factory() as session:
        for attempt, fields in zip(attempts, outcomes, strict=True):
            # Доставку, отменённую во время отправки, неудача не возвращает в «не доставлено»:
            # status меняется только при успехе.
            await session.execute(
                update(AlertDelivery)
                .where(AlertDelivery.id == attempt.delivery_id)
                .values(
                    attempts=AlertDelivery.attempts + 1,
                    first_attempt_at=func.coalesce(AlertDelivery.first_attempt_at, now),
                    last_attempt_at=now,
                    **fields,
                )
            )
        await session.commit()
