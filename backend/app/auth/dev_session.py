"""Сессия без Telegram — для входа на localhost, где Telegram OIDC недоступен (нужен HTTPS).

Только для локальной разработки: запускается из консоли, HTTP-эндпоинта нет, а в собранном
образе (BUILD_ID не dev) команда отказывается работать — на проде она создала бы Пользователя,
которому потом не войти через Telegram, и Сессию Суперадмина в обход SUPERADMIN_TELEGRAM_ID.

    uv run python -m app.auth.dev_session 123456789 --superadmin

Печатает строку для консоли браузера, которая ставит cookie Сессии.
"""

import argparse
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.sessions import create_session
from app.core.config import settings
from app.db.session import SessionLocal, engine
from app.models import User

DEV_BUILD_ID = "dev"
# Имя cookie Сессии — SESSION_COOKIE во frontend/src/lib/server/auth.ts.
SESSION_COOKIE = "session"


class NotDevBuild(Exception):
    """Команда запущена не в локальной разработке."""


class UserBlocked(Exception):
    """Заблокированному Пользователю Сессия не выдаётся."""


async def create_dev_session(
    session_factory: async_sessionmaker[AsyncSession], telegram_id: int, *, superadmin: bool
) -> str:
    """Токен новой Сессии Пользователя с этим Telegram ID; нет такого — он создаётся."""
    if settings.build_id != DEV_BUILD_ID:
        raise NotDevBuild(f"Только для локальной разработки, а сборка — {settings.build_id}")
    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
        if user is None:
            # sub настоящего входа неизвестен: вход через Telegram с этим же ID упадёт
            # на уникальности telegram_id. Для локальной базы это допустимо.
            user = User(telegram_sub=f"dev-{telegram_id}", telegram_id=telegram_id, name="Dev user")
            session.add(user)
            await session.flush()
        elif user.blocked_at is not None:
            raise UserBlocked(f"Пользователь {telegram_id} заблокирован")
        new_session = create_session(session, user, is_superadmin=superadmin)
        await session.commit()
        return new_session.token


async def _main(telegram_id: int, superadmin: bool) -> None:
    try:
        token = await create_dev_session(SessionLocal, telegram_id, superadmin=superadmin)
    finally:
        await engine.dispose()
    print("Выполните в консоли браузера на странице Healthchecker и обновите её:")
    print(f'document.cookie = "{SESSION_COOKIE}={token}; path=/"')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Сессия без Telegram для входа на localhost")
    parser.add_argument("telegram_id", type=int, help="Telegram ID Пользователя")
    parser.add_argument("--superadmin", action="store_true", help="с правами Суперадмина")
    args = parser.parse_args()
    try:
        asyncio.run(_main(args.telegram_id, args.superadmin))
    except (NotDevBuild, UserBlocked) as exc:
        raise SystemExit(str(exc)) from None
