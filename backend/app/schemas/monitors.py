from datetime import datetime
from typing import Annotated, Self

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    UrlConstraints,
    field_validator,
    model_validator,
)

from app.models import CheckInterval, HttpMethod, MonitorState

# Имя заголовка — token из RFC 9110.
HeaderName = Annotated[
    str,
    StringConstraints(min_length=1, max_length=256, pattern=r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$"),
]
# Перевод строки в значении позволил бы внедрить лишние заголовки.
HeaderValue = Annotated[str, StringConstraints(max_length=8192, pattern=r"^[^\r\n]*$")]
MonitorUrl = Annotated[AnyHttpUrl, UrlConstraints(max_length=2048)]

METHODS_WITHOUT_BODY = {HttpMethod.GET, HttpMethod.HEAD}


class Header(BaseModel):
    name: HeaderName
    value: HeaderValue


class MonitorIn(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    url: MonitorUrl
    method: HttpMethod = HttpMethod.GET
    headers: list[Header] = []
    body: str | None = None
    expected_status: Annotated[int, Field(ge=100, le=599)] = 200
    expected_body: str | None = None
    interval_seconds: CheckInterval = CheckInterval.MINUTES_5
    channel_ids: list[int] = []

    @field_validator("body", "expected_body")
    @classmethod
    def _empty_to_none(cls, value: str | None) -> str | None:
        return value or None

    @field_validator("channel_ids")
    @classmethod
    def _dedupe(cls, value: list[int]) -> list[int]:
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def _drop_body_for_bodyless_methods(self) -> Self:
        if self.method in METHODS_WITHOUT_BODY:
            self.body = None
        return self


class MonitorOut(BaseModel):
    id: int
    # Владелец: Суперадмин видит и чужие мониторы.
    user_id: int
    name: str
    url: str
    method: HttpMethod
    headers: list[Header]
    body: str | None
    expected_status: int
    expected_body: str | None
    interval_seconds: int
    channel_ids: list[int]
    state: MonitorState
    state_changed_at: datetime
    next_check_at: datetime | None
    last_check_at: datetime | None


class CheckOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    started_at: datetime
    duration_ms: int
    status_code: int | None
    success: bool
    failure_reason: str | None
