"""Вход через Telegram. Вызывает только серверный код SvelteKit: он хранит state и
code_verifier в cookie браузера и ставит cookie Сессии."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import Auth, get_oidc
from app.auth.sessions import create_session, delete_session
from app.auth.telegram_oidc import OidcError, TelegramIdentity, TelegramOidc
from app.core.config import settings
from app.db.session import get_session
from app.db.types import utcnow
from app.models import User
from app.schemas.auth import AuthorizationOut, CallbackIn, MeOut, SessionOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

Session = Annotated[AsyncSession, Depends(get_session)]
Oidc = Annotated[TelegramOidc, Depends(get_oidc)]


def is_superadmin(user: User) -> bool:
    return settings.superadmin_telegram_id is not None and (
        user.telegram_id == settings.superadmin_telegram_id
    )


def _require_configured(oidc: TelegramOidc) -> None:
    if not oidc.configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "oidc_not_configured", "message": "Вход через Telegram не настроен"},
        )


async def _upsert_user(session: AsyncSession, identity: TelegramIdentity) -> User:
    """Находит Пользователя по sub или регистрирует; профиль обновляется при каждом входе."""
    user = await session.scalar(select(User).where(User.telegram_sub == identity.sub))
    if user is None:
        user = User(telegram_sub=identity.sub)
        session.add(user)
    user.telegram_id = identity.telegram_id
    user.name = identity.name
    user.username = identity.username
    user.photo_url = identity.photo_url
    user.last_login_at = utcnow()
    await session.flush()
    return user


@router.post("/telegram/start")
async def start(oidc: Oidc) -> AuthorizationOut:
    _require_configured(oidc)
    authorization = oidc.start()
    return AuthorizationOut(
        url=authorization.url,
        state=authorization.state,
        code_verifier=authorization.code_verifier,
    )


@router.post("/telegram/callback")
async def callback(data: CallbackIn, session: Session, oidc: Oidc) -> SessionOut:
    _require_configured(oidc)
    try:
        identity = await oidc.finish(data.code, data.code_verifier)
    except OidcError as exc:
        logger.warning("Вход через Telegram не удался: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "oidc_failed", "message": str(exc)},
        ) from exc

    user = await _upsert_user(session, identity)
    if user.blocked_at is not None:
        # Профиль обновлён, но Сессии нет.
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "user_blocked", "message": "Доступ заблокирован администратором"},
        )

    new_session = create_session(session, user, is_superadmin=is_superadmin(user))
    await session.commit()
    return SessionOut(token=new_session.token, expires_at=new_session.expires_at)


@router.get("/me")
async def me(current: Auth) -> MeOut:
    user = current.user
    return MeOut(
        id=user.id,
        telegram_id=user.telegram_id,
        name=user.name,
        username=user.username,
        photo_url=user.photo_url,
        is_superadmin=current.is_superadmin,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(current: Auth, session: Session) -> None:
    await delete_session(session, current.token)
