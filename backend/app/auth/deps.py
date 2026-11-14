from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.sessions import find_session
from app.auth.telegram_oidc import TelegramOidc
from app.db.session import get_session
from app.models import User

# auto_error=False: без заголовка — тот же 401, что и с недействительным токеном.
bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    user: User
    is_superadmin: bool
    # Токен Сессии запроса: нужен для выхода.
    token: str

    @property
    def id(self) -> int:
        return self.user.id

    def can_manage(self, owner_id: int) -> bool:
        """Владелец или Суперадмин: просмотр, история, пауза и возобновление монитора."""
        return self.is_superadmin or owner_id == self.user.id


async def get_current_user(
    session: Annotated[AsyncSession, Depends(get_session)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> CurrentUser:
    user_session = credentials and await find_session(session, credentials.credentials)
    if not user_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется вход",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return CurrentUser(user_session.user, user_session.is_superadmin, credentials.credentials)


async def get_superadmin(
    current: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    # 404, а не 403: обычный Пользователь не узнаёт, что такой раздел существует.
    if not current.is_superadmin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Не найдено")
    return current


def get_oidc(request: Request) -> TelegramOidc:
    return request.app.state.oidc


Auth = Annotated[CurrentUser, Depends(get_current_user)]
Superadmin = Annotated[CurrentUser, Depends(get_superadmin)]
