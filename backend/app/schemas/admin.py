from datetime import datetime

from pydantic import BaseModel


class UserOut(BaseModel):
    id: int
    telegram_id: int
    name: str
    username: str | None
    photo_url: str | None
    created_at: datetime
    last_login_at: datetime
    blocked_at: datetime | None
    is_superadmin: bool
    monitors_count: int
