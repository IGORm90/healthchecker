from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.session import create_engine, get_session
from app.main import app


async def client_for_database(db_path: Path) -> AsyncIterator[AsyncClient]:
    engine = create_engine(f"sqlite+aiosqlite:///{db_path}")
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
        await engine.dispose()


@pytest.fixture
async def client(tmp_path: Path) -> AsyncIterator[AsyncClient]:
    async for c in client_for_database(tmp_path / "test.db"):
        yield c


async def test_health_ok(client: AsyncClient) -> None:
    response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.fixture
async def client_without_database(tmp_path: Path) -> AsyncIterator[AsyncClient]:
    # Каталога нет — SQLite не сможет открыть файл базы.
    async for c in client_for_database(tmp_path / "missing" / "test.db"):
        yield c


async def test_health_reports_error_when_database_unavailable(
    client_without_database: AsyncClient,
) -> None:
    response = await client_without_database.get("/api/health")

    assert response.status_code == 503
    assert response.json() == {"status": "error"}
