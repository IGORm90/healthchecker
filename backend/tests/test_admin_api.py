from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.models import Monitor, User, UserSession
from app.monitoring.scheduler import Alert, Scheduler
from tests.conftest import ClientFor, add_user

SessionFactory = async_sessionmaker[AsyncSession]

SUPERADMIN_TELEGRAM_ID = 9009


@pytest.fixture
async def superadmin(session_factory: SessionFactory, monkeypatch: pytest.MonkeyPatch) -> User:
    monkeypatch.setattr(settings, "superadmin_telegram_id", SUPERADMIN_TELEGRAM_ID)
    return await add_user(session_factory, SUPERADMIN_TELEGRAM_ID)


@pytest.fixture
async def admin(client_for: ClientFor, superadmin: User) -> AsyncClient:
    return await client_for(superadmin, is_superadmin=True)


async def create_monitor(client: AsyncClient) -> dict[str, Any]:
    response = await client.post(
        "/api/monitors", json={"name": "Example", "url": "https://example.com"}
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
async def scheduler(session_factory: SessionFactory) -> AsyncIterator[Scheduler]:
    async def ignore(_alert: Alert) -> None:
        pass

    async with httpx.AsyncClient() as http:
        yield Scheduler(session_factory, http, ignore)


async def test_admin_api_is_hidden_from_regular_users(client: AsyncClient, user: User) -> None:
    for path in ("/api/admin/users", f"/api/admin/users/{user.id}"):
        assert (await client.get(path)).status_code == 404
    assert (await client.post(f"/api/admin/users/{user.id}/block")).status_code == 404


async def test_superadmin_lists_users_with_monitor_counts(
    admin: AsyncClient, client: AsyncClient, user: User, superadmin: User
) -> None:
    await create_monitor(client)
    await create_monitor(client)

    users = {u["id"]: u for u in (await admin.get("/api/admin/users")).json()}

    assert users[user.id]["monitors_count"] == 2
    assert users[user.id]["is_superadmin"] is False
    assert users[user.id]["blocked_at"] is None
    assert users[superadmin.id]["is_superadmin"] is True
    assert users[superadmin.id]["monitors_count"] == 0


async def test_superadmin_lists_user_monitors(
    admin: AsyncClient, client: AsyncClient, user: User
) -> None:
    monitor = await create_monitor(client)

    response = await admin.get(f"/api/admin/users/{user.id}/monitors")

    assert [m["id"] for m in response.json()] == [monitor["id"]]
    assert (await admin.get("/api/admin/users/999/monitors")).status_code == 404


async def test_block_signs_user_out_and_stops_checks(
    admin: AsyncClient,
    client: AsyncClient,
    user: User,
    scheduler: Scheduler,
    session_factory: SessionFactory,
) -> None:
    monitor = await create_monitor(client)

    blocked = await admin.post(f"/api/admin/users/{user.id}/block")

    assert blocked.status_code == 200
    assert blocked.json()["blocked_at"] is not None
    assert (await client.get("/api/auth/me")).status_code == 401
    async with session_factory() as session:
        sessions_left = await session.scalar(
            select(func.count()).select_from(UserSession).where(UserSession.user_id == user.id)
        )
        stored = await session.get(Monitor, monitor["id"])
    assert sessions_left == 0
    assert await scheduler.take_due_monitors() == []
    # Блокировка не трогает Состояние монитора.
    assert stored is not None and stored.state == "unknown"


async def test_unblock_resumes_overdue_checks(
    admin: AsyncClient, client: AsyncClient, user: User, scheduler: Scheduler
) -> None:
    monitor = await create_monitor(client)
    await admin.post(f"/api/admin/users/{user.id}/block")
    assert await scheduler.take_due_monitors() == []

    unblocked = await admin.post(f"/api/admin/users/{user.id}/unblock")

    assert unblocked.json()["blocked_at"] is None
    [taken] = await scheduler.take_due_monitors()
    assert taken.id == monitor["id"]


async def test_superadmin_cannot_be_blocked(admin: AsyncClient, superadmin: User) -> None:
    response = await admin.post(f"/api/admin/users/{superadmin.id}/block")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "superadmin"


async def test_unknown_user_is_not_found(admin: AsyncClient) -> None:
    assert (await admin.get("/api/admin/users/999")).status_code == 404
    assert (await admin.post("/api/admin/users/999/block")).status_code == 404
