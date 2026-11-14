"""Сессии Пользователей: в базе только SHA-256 токена, сам токен знает лишь браузер.

Сессия живёт SESSION_TTL с момента входа без продления и действует только в той сборке
сервиса, в которой создана (решение 7 плана 0005).
"""

import asyncio
import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.db.types import utcnow
from app.models import User, UserSession

logger = logging.getLogger(__name__)

SESSION_TTL = timedelta(days=7)
PRUNE_EVERY = timedelta(days=1)


@dataclass(frozen=True)
class NewSession:
    token: str
    expires_at: datetime


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(session: AsyncSession, user: User, *, is_superadmin: bool) -> NewSession:
    """Добавляет Сессию Пользователя; коммит — за вызывающим."""
    token = secrets.token_urlsafe(32)
    now = utcnow()
    expires_at = now + SESSION_TTL
    session.add(
        UserSession(
            user_id=user.id,
            token_hash=hash_token(token),
            is_superadmin=is_superadmin,
            build_id=settings.build_id,
            created_at=now,
            expires_at=expires_at,
        )
    )
    return NewSession(token, expires_at)


async def find_session(session: AsyncSession, token: str) -> UserSession | None:
    """Действующая Сессия по токену: не истекла, своей сборки, Пользователь не заблокирован."""
    return await session.scalar(
        select(UserSession)
        .join(UserSession.user)
        .where(
            UserSession.token_hash == hash_token(token),
            UserSession.expires_at > utcnow(),
            UserSession.build_id == settings.build_id,
            User.blocked_at.is_(None),
        )
    )


async def delete_session(session: AsyncSession, token: str) -> None:
    await session.execute(delete(UserSession).where(UserSession.token_hash == hash_token(token)))
    await session.commit()


async def delete_user_sessions(session: AsyncSession, user_id: int) -> None:
    """Удаляет все Сессии Пользователя; коммит — за вызывающим."""
    await session.execute(delete(UserSession).where(UserSession.user_id == user_id))


async def prune_sessions(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Удаляет просроченные Сессии и Сессии других сборок."""
    async with session_factory() as session:
        await session.execute(
            delete(UserSession).where(
                or_(UserSession.expires_at <= utcnow(), UserSession.build_id != settings.build_id)
            )
        )
        await session.commit()


async def run_session_pruning(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Чистит Сессии сразу и далее раз в PRUNE_EVERY; сбой ждёт следующего раза."""
    while True:
        try:
            await prune_sessions(session_factory)
        except Exception:
            logger.exception("Не удалось удалить устаревшие Сессии")
        await asyncio.sleep(PRUNE_EVERY.total_seconds())
