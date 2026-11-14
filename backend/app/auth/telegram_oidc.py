"""Вход через Telegram OpenID Connect: Authorization Code + PKCE.

https://core.telegram.org/bots/telegram-login. Эндпоинта userinfo у Telegram нет:
всё о Пользователе приходит в ID-токене.
"""

import asyncio
import base64
import hashlib
import secrets
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt

ISSUER = "https://oauth.telegram.org"
AUTH_URL = f"{ISSUER}/auth"
TOKEN_URL = f"{ISSUER}/token"
JWKS_URL = f"{ISSUER}/.well-known/jwks.json"
SCOPE = "openid profile"
# EdDSA и ES256K Telegram не сочетает со scope profile.
ALGORITHMS = ["RS256", "ES256"]
TIMEOUT_SECONDS = 10


class OidcError(Exception):
    """Вход не удался; текст безопасен для логов и пользователя."""


@dataclass(frozen=True)
class Authorization:
    """Начало входа: куда отправить браузер и что сохранить до возврата."""

    url: str
    state: str
    code_verifier: str


@dataclass(frozen=True)
class TelegramIdentity:
    """Пользователь Telegram из проверенного ID-токена."""

    sub: str
    telegram_id: int
    name: str
    username: str | None
    photo_url: str | None


def code_challenge(code_verifier: str) -> str:
    digest = hashlib.sha256(code_verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


class TelegramOidc:
    def __init__(
        self, http: httpx.AsyncClient, client_id: str, client_secret: str, redirect_uri: str
    ) -> None:
        self._http = http
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        # Ключи JWKS по kid; создаётся один клиент на приложение, поэтому кеш общий.
        self._keys: dict[str, jwt.PyJWK] = {}
        self._keys_lock = asyncio.Lock()

    @property
    def configured(self) -> bool:
        return bool(self._client_id and self._client_secret and self._redirect_uri)

    def start(self) -> Authorization:
        state = secrets.token_urlsafe(32)
        code_verifier = secrets.token_urlsafe(64)
        params = {
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "response_type": "code",
            "scope": SCOPE,
            "state": state,
            "code_challenge": code_challenge(code_verifier),
            "code_challenge_method": "S256",
        }
        return Authorization(f"{AUTH_URL}?{urlencode(params)}", state, code_verifier)

    async def finish(self, code: str, code_verifier: str) -> TelegramIdentity:
        """Обменивает код на токены и возвращает Пользователя из проверенного ID-токена."""
        id_token = await self._exchange(code, code_verifier)
        return self._identity(await self._verify(id_token))

    async def _exchange(self, code: str, code_verifier: str) -> str:
        try:
            response = await self._http.post(
                TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self._redirect_uri,
                    "client_id": self._client_id,
                    "code_verifier": code_verifier,
                },
                auth=(self._client_id, self._client_secret),
                timeout=TIMEOUT_SECONDS,
            )
            payload = response.json()
        except httpx.TimeoutException:
            raise OidcError("Telegram не ответил вовремя") from None
        except (httpx.HTTPError, ValueError) as exc:
            raise OidcError(f"сбой связи с Telegram ({type(exc).__name__})") from None
        if response.is_error or "id_token" not in payload:
            reason = payload.get("error_description") or payload.get("error")
            raise OidcError(f"Telegram отклонил код: {reason or f'HTTP {response.status_code}'}")
        return payload["id_token"]

    async def _verify(self, id_token: str) -> dict[str, Any]:
        try:
            kid = jwt.get_unverified_header(id_token).get("kid")
            key = await self._key(kid)
            return jwt.decode(
                id_token,
                key=key,
                algorithms=ALGORITHMS,
                audience=self._client_id,
                issuer=ISSUER,
                options={"require": ["iss", "aud", "exp", "sub"]},
            )
        except jwt.PyJWTError as exc:
            raise OidcError(f"ID-токен не прошёл проверку: {exc}") from None

    async def _key(self, kid: str | None) -> jwt.PyJWK:
        if kid in self._keys:
            return self._keys[kid]
        # Неизвестный kid — Telegram мог сменить ключи: загружаем набор заново.
        async with self._keys_lock:
            if kid not in self._keys:
                self._keys = await self._load_keys()
        if kid not in self._keys:
            raise OidcError("ID-токен подписан неизвестным ключом")
        return self._keys[kid]

    async def _load_keys(self) -> dict[str, jwt.PyJWK]:
        try:
            response = await self._http.get(JWKS_URL, timeout=TIMEOUT_SECONDS)
            response.raise_for_status()
            jwks = jwt.PyJWKSet.from_dict(response.json())
        except httpx.HTTPError as exc:
            raise OidcError(f"не удалось загрузить ключи Telegram ({type(exc).__name__})") from None
        except ValueError, jwt.PyJWTError:
            raise OidcError("Telegram вернул некорректные ключи") from None
        return {key.key_id: key for key in jwks.keys if key.key_id}

    @staticmethod
    def _identity(claims: dict[str, Any]) -> TelegramIdentity:
        if not isinstance(claims.get("id"), int):
            raise OidcError("в ID-токене нет Telegram ID: нужен scope profile")
        return TelegramIdentity(
            sub=str(claims["sub"]),
            telegram_id=claims["id"],
            name=claims.get("name") or claims.get("preferred_username") or str(claims["id"]),
            username=claims.get("preferred_username"),
            photo_url=claims.get("picture"),
        )
