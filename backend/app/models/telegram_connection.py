from sqlalchemy import BigInteger, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TelegramConnection(Base):
    __tablename__ = "telegram_connection"

    id: Mapped[int] = mapped_column(primary_key=True)
    # У Пользователя не больше одного Подключения Telegram.
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    bot_token: Mapped[str] = mapped_column(String(256))
    # Один бот у двух Пользователей перехватывал бы их getUpdates (ADR 0001).
    bot_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    bot_username: Mapped[str] = mapped_column(String(64))
    # offset для getUpdates: обновления до него уже прочитаны.
    updates_offset: Mapped[int] = mapped_column(Integer, default=0)
