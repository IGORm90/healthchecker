"""Раздел Суперадмина: Пользователи и их Блокировка. Остальным — 404."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.monitors import user_monitors
from app.auth.deps import Superadmin
from app.auth.router import is_superadmin
from app.auth.sessions import delete_user_sessions
from app.db.session import get_session
from app.db.types import utcnow
from app.models import Monitor, User
from app.schemas.admin import UserOut
from app.schemas.monitors import MonitorOut

router = APIRouter(prefix="/api/admin", tags=["admin"])

Session = Annotated[AsyncSession, Depends(get_session)]

_monitors_count = (
    select(func.count())
    .select_from(Monitor)
    .where(Monitor.user_id == User.id)
    .correlate(User)
    .scalar_subquery()
)


def _to_out(user: User, monitors_count: int) -> UserOut:
    return UserOut(
        id=user.id,
        telegram_id=user.telegram_id,
        name=user.name,
        username=user.username,
        photo_url=user.photo_url,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        blocked_at=user.blocked_at,
        is_superadmin=is_superadmin(user),
        monitors_count=monitors_count,
    )


async def _user_out(session: AsyncSession, user_id: int) -> UserOut:
    row = (await session.execute(select(User, _monitors_count).where(User.id == user_id))).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
    return _to_out(*row)


async def _get_user(session: AsyncSession, user_id: int) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
    return user


@router.get("/users")
async def list_users(_: Superadmin, session: Session) -> list[UserOut]:
    rows = await session.execute(select(User, _monitors_count).order_by(User.created_at, User.id))
    return [_to_out(user, count) for user, count in rows]


@router.get("/users/{user_id}")
async def get_user(user_id: int, _: Superadmin, session: Session) -> UserOut:
    return await _user_out(session, user_id)


@router.get("/users/{user_id}/monitors")
async def list_user_monitors(user_id: int, _: Superadmin, session: Session) -> list[MonitorOut]:
    await _get_user(session, user_id)
    return await user_monitors(session, user_id)


@router.post("/users/{user_id}/block")
async def block_user(user_id: int, _: Superadmin, session: Session) -> UserOut:
    user = await _get_user(session, user_id)
    if is_superadmin(user):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "superadmin", "message": "Суперадмина нельзя заблокировать"},
        )
    if user.blocked_at is None:
        user.blocked_at = utcnow()
        # Заблокированный выходит сразу, а не по истечении Сессии.
        await delete_user_sessions(session, user.id)
        await session.commit()
    return await _user_out(session, user_id)


@router.post("/users/{user_id}/unblock")
async def unblock_user(user_id: int, _: Superadmin, session: Session) -> UserOut:
    user = await _get_user(session, user_id)
    if user.blocked_at is not None:
        user.blocked_at = None
        await session.commit()
    return await _user_out(session, user_id)
