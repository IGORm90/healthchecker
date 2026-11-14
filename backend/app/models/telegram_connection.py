from sqlalchemy import BigInteger, CheckConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Подключение Telegram одно на сервис, поэтому строка в таблице одна и её id всегда 1.
TELEGRAM_CONNECTION_ID = 1


class TelegramConnection(Base):
    __tablename__ = "telegram_connection"
    __table_args__ = (CheckConstraint(f"id = {TELEGRAM_CONNECTION_ID}", name="singleton"),)

    id: Mapped[int] = mapped_column(primary_key=True, default=TELEGRAM_CONNECTION_ID)
    bot_token: Mapped[str] = mapped_column(String(256))
    bot_id: Mapped[int] = mapped_column(BigInteger)
    bot_username: Mapped[str] = mapped_column(String(64))
    # offset для getUpdates: обновления до него уже прочитаны.
    updates_offset: Mapped[int] = mapped_column(Integer, default=0)
