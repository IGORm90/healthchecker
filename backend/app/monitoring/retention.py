"""Срок хранения истории: проверки старше HISTORY_RETENTION удаляются при старте и каждую ночь.

Работает в единственном экземпляре в lifespan, рядом с планировщиком.
"""

import asyncio
import logging
from datetime import UTC, datetime, time, timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.types import utcnow
from app.models import Check

logger = logging.getLogger(__name__)

HISTORY_RETENTION = timedelta(days=3)
PRUNE_AT = time(3, 0, tzinfo=UTC)


async def run_retention(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Удаляет устаревшие проверки сразу и далее в PRUNE_AT; сбой ждёт следующего раза."""
    while True:
        try:
            await prune_checks(session_factory, utcnow())
        except Exception:
            logger.exception("Не удалось удалить устаревшие проверки")
        now = utcnow()
        await asyncio.sleep((next_prune_at(now) - now).total_seconds())


async def prune_checks(session_factory: async_sessionmaker[AsyncSession], now: datetime) -> None:
    """Удаляет проверки, начатые раньше now − срок хранения."""
    async with session_factory() as session:
        await session.execute(
            delete(Check)
            .where(Check.started_at < now - HISTORY_RETENTION)
            .execution_options(synchronize_session=False)
        )
        await session.commit()


def next_prune_at(now: datetime) -> datetime:
    """Ближайший момент PRUNE_AT строго позже now."""
    today = datetime.combine(now.astimezone(UTC).date(), PRUNE_AT)
    return today if today > now else today + timedelta(days=1)
