"""Срок хранения истории: проверки старше HISTORY_RETENTION удаляются при старте и каждую ночь.

Оповещения удаляются по тому же сроку, кроме недоставленных: их повтор продолжается (план 0006).

Работает в единственном экземпляре в lifespan, рядом с планировщиком.
"""

import asyncio
import logging
from datetime import UTC, datetime, time, timedelta

from sqlalchemy import delete, exists
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.types import utcnow
from app.models import Alert, AlertDelivery, Check
from app.notifications.alerts import IS_PENDING

logger = logging.getLogger(__name__)

HISTORY_RETENTION = timedelta(days=3)
PRUNE_AT = time(3, 0, tzinfo=UTC)


async def run_retention(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Удаляет устаревшие проверки сразу и далее в PRUNE_AT; сбой ждёт следующего раза."""
    while True:
        try:
            await prune_history(session_factory, utcnow())
        except Exception:
            logger.exception("Не удалось удалить устаревшую историю")
        now = utcnow()
        await asyncio.sleep((next_prune_at(now) - now).total_seconds())


async def prune_history(session_factory: async_sessionmaker[AsyncSession], now: datetime) -> None:
    """Удаляет проверки и доставленные или отменённые Оповещения старше now − срок хранения."""
    cutoff = now - HISTORY_RETENTION
    pending = exists().where(AlertDelivery.alert_id == Alert.id, IS_PENDING)
    async with session_factory() as session:
        await session.execute(
            delete(Alert)
            .where(Alert.created_at < cutoff, ~pending)
            .execution_options(synchronize_session=False)
        )
        await session.execute(
            delete(Check)
            .where(Check.started_at < cutoff)
            .execution_options(synchronize_session=False)
        )
        await session.commit()


def next_prune_at(now: datetime) -> datetime:
    """Ближайший момент PRUNE_AT строго позже now."""
    today = datetime.combine(now.astimezone(UTC).date(), PRUNE_AT)
    return today if today > now else today + timedelta(days=1)
