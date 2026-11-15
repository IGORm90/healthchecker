import base64
import time
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.deps import get_oidc
from app.auth.telegram_oidc import ISSUER, TelegramOidc, code_challenge
from app.core.config import settings
from app.db.types import utcnow
from app.main import app
from app.models import User, UserSession
from tests.conftest import add_user, login

SessionFactory = async_sessionmaker[AsyncSession]

CLIENT_ID = "123456789"
CLIENT_SECRET = "client-secret"
REDIRECT_URI = "https://hc.example.com/auth/callback"
TELEGRAM_ID = 777


def new_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


class FakeTelegramOAuth:
    """oauth.telegram.org в памяти: выдаёт ID-токен, подписанный своим ключом, по любому коду."""

    def __init__(self) -> None:
        self.key = new_key()
        self.kid = "key-1"
        self.claims: dict[str, Any] = self.valid_claims()
        # Чем подписать ID-токен; по умолчанию — ключом из JWKS.
        self.signing_key: rsa.RSAPrivateKey = self.key
        self.token_requests: list[httpx.Request] = []
        self.jwks_requests = 0

    @staticmethod
    def valid_claims(**overrides: Any) -> dict[str, Any]:
        now = int(time.time())
        claims = {
            "iss": ISSUER,
            "aud": CLIENT_ID,
            "sub": "sub-777",
            "iat": now,
            "exp": now + 300,
            "id": TELEGRAM_ID,
            "name": "Igor",
            "preferred_username": "igor",
            "picture": "https://t.me/i/userpic/igor.jpg",
        }
        return claims | overrides

    def handle(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/.well-known/jwks.json":
            self.jwks_requests += 1
            jwk = jwt.algorithms.RSAAlgorithm.to_jwk(self.key.public_key(), as_dict=True)
            return httpx.Response(200, json={"keys": [jwk | {"kid": self.kid, "alg": "RS256"}]})
        if request.url.path == "/token":
            self.token_requests.append(request)
            form = parse_qs(request.content.decode())
            if form.get("code") != ["good-code"]:
                return httpx.Response(400, json={"error": "invalid_grant"})
            id_token = jwt.encode(
                self.claims, self.signing_key, algorithm="RS256", headers={"kid": self.kid}
            )
            return httpx.Response(
                200, json={"access_token": "at", "token_type": "Bearer", "id_token": id_token}
            )
        return httpx.Response(404)


@pytest.fixture
async def oauth(anonymous_client: AsyncClient) -> AsyncIterator[FakeTelegramOAuth]:
    fake = FakeTelegramOAuth()
    async with httpx.AsyncClient(transport=httpx.MockTransport(fake.handle)) as http:
        oidc = TelegramOidc(http, CLIENT_ID, CLIENT_SECRET, REDIRECT_URI)
        app.dependency_overrides[get_oidc] = lambda: oidc
        yield fake


async def sign_in(client: AsyncClient, code: str = "good-code") -> httpx.Response:
    return await client.post(
        "/api/auth/telegram/callback", json={"code": code, "code_verifier": "verifier"}
    )


async def count(session_factory: SessionFactory, model: type) -> int:
    async with session_factory() as session:
        return await session.scalar(select(func.count()).select_from(model)) or 0


async def test_start_builds_pkce_authorization_url(
    anonymous_client: AsyncClient, oauth: FakeTelegramOAuth
) -> None:
    response = await anonymous_client.post("/api/auth/telegram/start")

    assert response.status_code == 200
    body = response.json()
    url = urlsplit(body["url"])
    params = {k: v for k, [v] in parse_qs(url.query).items()}
    assert f"{url.scheme}://{url.netloc}{url.path}" == "https://oauth.telegram.org/auth"
    assert params == {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "openid profile",
        "state": body["state"],
        "code_challenge": code_challenge(body["code_verifier"]),
        "code_challenge_method": "S256",
    }


async def test_start_without_configuration_is_unavailable(
    anonymous_client: AsyncClient,
) -> None:
    async with httpx.AsyncClient() as http:
        app.dependency_overrides[get_oidc] = lambda: TelegramOidc(http, "", "", "")

        response = await anonymous_client.post("/api/auth/telegram/start")

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "oidc_not_configured"


async def test_valid_token_creates_user_and_session(
    anonymous_client: AsyncClient, oauth: FakeTelegramOAuth, session_factory: SessionFactory
) -> None:
    response = await sign_in(anonymous_client)

    assert response.status_code == 200, response.text
    token = response.json()["token"]
    [request] = oauth.token_requests
    form = parse_qs(request.content.decode())
    assert form["code_verifier"] == ["verifier"]
    assert form["redirect_uri"] == [REDIRECT_URI]
    expected_auth = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    assert request.headers["authorization"] == f"Basic {expected_auth}"

    me = await anonymous_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json() == {
        "id": me.json()["id"],
        "telegram_id": TELEGRAM_ID,
        "name": "Igor",
        "username": "igor",
        "photo_url": "https://t.me/i/userpic/igor.jpg",
        "is_superadmin": False,
    }
    async with session_factory() as session:
        [stored] = await session.scalars(select(UserSession))
    assert stored.token_hash != token
    assert timedelta(days=6, hours=23) < stored.expires_at - utcnow() <= timedelta(days=7)


async def test_repeated_sign_in_updates_the_same_user(
    anonymous_client: AsyncClient, oauth: FakeTelegramOAuth, session_factory: SessionFactory
) -> None:
    await sign_in(anonymous_client)
    oauth.claims = oauth.valid_claims(name="Igor M", preferred_username="igor_m")

    await sign_in(anonymous_client)

    assert await count(session_factory, User) == 1
    assert await count(session_factory, UserSession) == 2
    async with session_factory() as session:
        [user] = await session.scalars(select(User))
    assert (user.name, user.username) == ("Igor M", "igor_m")


@pytest.mark.parametrize(
    "claims",
    [
        pytest.param({"aud": "987654321"}, id="foreign aud"),
        pytest.param({"iss": "https://evil.example"}, id="foreign iss"),
        pytest.param({"exp": int(time.time()) - 60}, id="expired"),
    ],
)
async def test_invalid_claims_are_rejected(
    anonymous_client: AsyncClient,
    oauth: FakeTelegramOAuth,
    session_factory: SessionFactory,
    claims: dict[str, Any],
) -> None:
    oauth.claims = oauth.valid_claims(**claims)

    response = await sign_in(anonymous_client)

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "oidc_failed"
    assert await count(session_factory, User) == 0


async def test_telegram_id_as_string_is_accepted(
    anonymous_client: AsyncClient, oauth: FakeTelegramOAuth, session_factory: SessionFactory
) -> None:
    oauth.claims = oauth.valid_claims(id=str(TELEGRAM_ID))

    response = await sign_in(anonymous_client)

    assert response.status_code == 200, response.text
    async with session_factory() as session:
        [user] = await session.scalars(select(User))
    assert user.telegram_id == TELEGRAM_ID


async def test_missing_telegram_id_names_received_claims(
    anonymous_client: AsyncClient, oauth: FakeTelegramOAuth, session_factory: SessionFactory
) -> None:
    oauth.claims = oauth.valid_claims()
    del oauth.claims["id"]

    response = await sign_in(anonymous_client)

    assert response.status_code == 400
    assert "preferred_username" in response.json()["detail"]["message"]
    assert await count(session_factory, User) == 0


async def test_foreign_signature_is_rejected(
    anonymous_client: AsyncClient, oauth: FakeTelegramOAuth, session_factory: SessionFactory
) -> None:
    oauth.signing_key = new_key()

    response = await sign_in(anonymous_client)

    assert response.status_code == 400
    assert await count(session_factory, UserSession) == 0


async def test_rejected_code_is_an_error(
    anonymous_client: AsyncClient, oauth: FakeTelegramOAuth
) -> None:
    response = await sign_in(anonymous_client, code="bad-code")

    assert response.status_code == 400
    assert "invalid_grant" in response.json()["detail"]["message"]


async def test_jwks_is_cached_and_reloaded_for_unknown_key(
    anonymous_client: AsyncClient, oauth: FakeTelegramOAuth
) -> None:
    await sign_in(anonymous_client)
    await sign_in(anonymous_client)
    assert oauth.jwks_requests == 1

    oauth.key = oauth.signing_key = new_key()
    oauth.kid = "key-2"

    assert (await sign_in(anonymous_client)).status_code == 200
    assert oauth.jwks_requests == 2


async def test_blocked_user_gets_no_session_but_profile_is_updated(
    anonymous_client: AsyncClient, oauth: FakeTelegramOAuth, session_factory: SessionFactory
) -> None:
    await add_user(session_factory, TELEGRAM_ID, blocked_at=utcnow())

    response = await sign_in(anonymous_client)

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "user_blocked"
    assert await count(session_factory, UserSession) == 0
    async with session_factory() as session:
        [user] = await session.scalars(select(User))
    assert user.name == "Igor"


async def test_superadmin_flag_is_granted_at_sign_in(
    anonymous_client: AsyncClient,
    oauth: FakeTelegramOAuth,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "superadmin_telegram_id", TELEGRAM_ID)
    token = (await sign_in(anonymous_client)).json()["token"]
    # Смена env не отбирает права у уже выданной Сессии.
    monkeypatch.setattr(settings, "superadmin_telegram_id", None)

    me = await anonymous_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert me.json()["is_superadmin"] is True


async def test_requests_without_session_are_unauthorized(anonymous_client: AsyncClient) -> None:
    for path in ("/api/auth/me", "/api/monitors", "/api/channels", "/api/telegram"):
        response = await anonymous_client.get(path)
        assert response.status_code == 401, path

    wrong = await anonymous_client.get("/api/monitors", headers={"Authorization": "Bearer nope"})
    assert wrong.status_code == 401


async def test_health_is_public(anonymous_client: AsyncClient) -> None:
    assert (await anonymous_client.get("/api/health")).status_code == 200


async def test_expired_session_is_unauthorized(
    anonymous_client: AsyncClient, session_factory: SessionFactory, user: User
) -> None:
    token = await login(session_factory, user)
    async with session_factory() as session:
        [stored] = await session.scalars(select(UserSession))
        stored.expires_at = utcnow() - timedelta(seconds=1)
        await session.commit()

    response = await anonymous_client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401


async def test_session_of_another_build_is_unauthorized(
    anonymous_client: AsyncClient,
    session_factory: SessionFactory,
    user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = await login(session_factory, user)
    monkeypatch.setattr(settings, "build_id", "next-build")

    response = await anonymous_client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401


async def test_logout_deletes_session(client: AsyncClient, session_factory: SessionFactory) -> None:
    assert (await client.post("/api/auth/logout")).status_code == 204

    assert await count(session_factory, UserSession) == 0
    assert (await client.get("/api/auth/me")).status_code == 401
