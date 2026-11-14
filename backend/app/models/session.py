from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import UtcDateTime, utcnow
from app.models.user import User


class UserSession(Base):
    """Сессия Пользователя; имя отличается от сессии SQLAlchemy."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # SHA-256 токена: украденная база не даёт войти чужой Сессией.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    # Права Суперадмина вычисляются при входе и действуют до конца Сессии.
    is_superadmin: Mapped[bool] = mapped_column(default=False)
    build_id: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime, index=True)

    user: Mapped[User] = relationship(lazy="joined")
