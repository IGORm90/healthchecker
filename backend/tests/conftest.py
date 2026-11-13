from collections.abc import AsyncIterator, Callable
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

import app.models  # noqa: F401 — регистрирует модели в Base.metadata
from app.db.base import Base
from app.db.session import create_engine, get_session
from app.main import app
from app.monitoring import ssrf

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
