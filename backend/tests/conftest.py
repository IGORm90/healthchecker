import json
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

import app.models  # noqa: F401 — регистрирует модели в Base.metadata
from app.api.telegram import get_telegram
from app.db.base import Base
from app.db.session import create_engine, get_session
from app.main import app
from app.monitoring import ssrf
from app.notifications.telegram import TelegramClient

# Публичный адрес, в который по умолчанию «резолвится» любое имя в тестах.
PUBLIC_IP = "93.184.215.14"


async def client_for_engine(engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
async def engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
async def client(engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    async for c in client_for_engine(engine):
        yield c


@pytest.fixture
async def client_without_database(tmp_path: Path) -> AsyncIterator[AsyncClient]:
    # Каталога нет — SQLite не сможет открыть файл базы.
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'missing' / 'test.db'}")
    async for c in client_for_engine(engine):
        yield c
    await engine.dispose()


@pytest.fixture(autouse=True)
def fake_dns(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[str]]:
    """Подменяет DNS: имя из словаря резолвится в его адреса, остальные — в PUBLIC_IP."""
    records: dict[str, list[str]] = {}

    async def resolve_host(host: str) -> list[str]:
        return records.get(host, [PUBLIC_IP])

    monkeypatch.setattr(ssrf, "resolve_host", resolve_host)
    return records


@pytest.fixture
def allow_private_targets(monkeypatch: pytest.MonkeyPatch) -> Callable[[bool], None]:
    from app.core.config import settings

    def set_flag(value: bool) -> None:
        monkeypatch.setattr(settings, "allow_private_targets", value)

    return set_flag


class FakeTelegram:
    """Telegram Bot API в памяти: боты по токенам, очередь обновлений, отправленные сообщения."""

    def __init__(self) -> None:
        self.bots: dict[str, dict[str, Any]] = {
            "token-alpha": {"id": 1, "username": "alpha_bot"},
            "token-beta": {"id": 2, "username": "beta_bot"},
        }
        self.updates: list[dict[str, Any]] = []
        self.sent: list[tuple[int, str]] = []
        # Чаты, из которых бота удалили: отправка в них падает.
        self.kicked_from: set[int] = set()

    def handle(self, request: httpx.Request) -> httpx.Response:
        _, bot_token, method = request.url.path.split("/")
        token = bot_token.removeprefix("bot")
        params = json.loads(request.content or b"{}")
        if token not in self.bots:
            return httpx.Response(401, json={"ok": False, "description": "Unauthorized"})
        match method:
            case "getMe":
                return self._ok(self.bots[token])
            case "getUpdates":
                return self._ok([u for u in self.updates if u["update_id"] >= params["offset"]])
            case "sendMessage":
                if params["chat_id"] in self.kicked_from:
                    return httpx.Response(
                        403, json={"ok": False, "description": "Forbidden: bot was kicked"}
                    )
                self.sent.append((params["chat_id"], params["text"]))
                return self._ok({"message_id": len(self.sent)})
        return httpx.Response(404, json={"ok": False, "description": "Not Found"})

    @staticmethod
    def _ok(result: Any) -> httpx.Response:
        return httpx.Response(200, json={"ok": True, "result": result})


@pytest.fixture
async def fake_telegram(client: AsyncClient) -> AsyncIterator[FakeTelegram]:
    fake = FakeTelegram()
    async with httpx.AsyncClient(transport=httpx.MockTransport(fake.handle)) as http:
        app.dependency_overrides[get_telegram] = lambda: TelegramClient(http)
        yield fake


@pytest.fixture
def telegram_client(fake_telegram: FakeTelegram) -> TelegramClient:
    return app.dependency_overrides[get_telegram]()
