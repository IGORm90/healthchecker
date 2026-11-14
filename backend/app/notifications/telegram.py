"""Тонкая обёртка над Telegram Bot API.

Токен входит в URL запроса, поэтому ни URL, ни исключения httpx (в них есть URL) не попадают
в текст ошибок: наружу выходит только описание от Telegram или тип сбоя.
"""

from dataclasses import dataclass
from typing import Any

import httpx

API_BASE = "https://api.telegram.org"
TIMEOUT_SECONDS = 10


class TelegramError(Exception):
    """Ошибка Bot API; текст безопасен для логов и пользователя."""


@dataclass(frozen=True)
class Bot:
    id: int
    username: str


class TelegramClient:
    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def _call(self, token: str, method: str, **params: Any) -> Any:
        try:
            response = await self._http.post(
                f"{API_BASE}/bot{token}/{method}", json=params, timeout=TIMEOUT_SECONDS
            )
            payload = response.json()
        except httpx.TimeoutException:
            raise TelegramError("Telegram не ответил вовремя") from None
        except (httpx.HTTPError, ValueError) as exc:
            raise TelegramError(f"сбой связи с Telegram ({type(exc).__name__})") from None
        if not payload.get("ok"):
            raise TelegramError(payload.get("description") or f"HTTP {response.status_code}")
        return payload["result"]

    async def get_me(self, token: str) -> Bot:
        result = await self._call(token, "getMe")
        return Bot(id=result["id"], username=result["username"])

    async def get_updates(self, token: str, offset: int) -> list[dict[str, Any]]:
        return await self._call(
            token,
            "getUpdates",
            offset=offset,
            allowed_updates=["message", "channel_post", "my_chat_member"],
        )

    async def send_message(self, token: str, chat_id: int, text: str) -> None:
        await self._call(
            token,
            "sendMessage",
            chat_id=chat_id,
            text=text,
            parse_mode="HTML",
            link_preview_options={"is_disabled": True},
        )
