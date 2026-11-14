from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints

OidcParam = Annotated[str, StringConstraints(min_length=1, max_length=2048)]


class AuthorizationOut(BaseModel):
    url: str
    state: str
    code_verifier: str


class CallbackIn(BaseModel):
    code: OidcParam
    code_verifier: OidcParam


class SessionOut(BaseModel):
    token: str
    expires_at: datetime


class MeOut(BaseModel):
    id: int
    telegram_id: int
    name: str
    username: str | None
    photo_url: str | None
    is_superadmin: bool
