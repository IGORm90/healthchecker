from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import User
from tests.conftest import ClientFor, FakeTelegram, add_user
from tests.test_telegram_api import add_channel, chat_member_update, connect

SessionFactory = async_sessionmaker[AsyncSession]

MONITOR = {"name": "Example", "url": "https://example.com"}
GROUP = {"id": -100, "title": "Ops", "type": "group"}


async def create_monitor(client: AsyncClient, **overrides: Any) -> dict[str, Any]:
    response = await client.post("/api/monitors", json=MONITOR | overrides)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
async def other(session_factory: SessionFactory) -> User:
    return await add_user(session_factory, 2002)


@pytest.fixture
async def other_client(client_for: ClientFor, other: User) -> AsyncClient:
    return await client_for(other)


@pytest.fixture
async def superadmin_client(client_for: ClientFor, session_factory: SessionFactory) -> AsyncClient:
    return await client_for(await add_user(session_factory, 9009), is_superadmin=True)


async def test_users_see_only_their_monitors(
    client: AsyncClient, other_client: AsyncClient, user: User
) -> None:
    mine = await create_monitor(client)
    await create_monitor(other_client, name="Other")

    listed = (await client.get("/api/monitors")).json()

    assert [m["id"] for m in listed] == [mine["id"]]
    assert mine["user_id"] == user.id


@pytest.mark.parametrize(
    ("method", "suffix", "body"),
    [
        ("GET", "", None),
        ("PUT", "", MONITOR),
        ("DELETE", "", None),
        ("POST", "/pause", None),
        ("POST", "/resume", None),
        ("GET", "/checks", None),
    ],
)
async def test_foreign_monitor_is_not_found(
    client: AsyncClient,
    other_client: AsyncClient,
    method: str,
    suffix: str,
    body: dict[str, Any] | None,
) -> None:
    monitor = await create_monitor(other_client)

    response = await client.request(method, f"/api/monitors/{monitor['id']}{suffix}", json=body)

    assert response.status_code == 404


async def test_superadmin_views_pauses_and_resumes_foreign_monitor(
    superadmin_client: AsyncClient, other_client: AsyncClient
) -> None:
    monitor = await create_monitor(other_client)
    url = f"/api/monitors/{monitor['id']}"

    assert (await superadmin_client.get(url)).status_code == 200
    assert (await superadmin_client.get(f"{url}/checks")).status_code == 200
    paused = await superadmin_client.post(f"{url}/pause")
    assert paused.json()["state"] == "paused"

    # Владелец может снять паузу, поставленную Суперадмином.
    resumed = await other_client.post(f"{url}/resume")
    assert resumed.json()["state"] == "unknown"


async def test_superadmin_cannot_edit_or_delete_foreign_monitor(
    superadmin_client: AsyncClient, other_client: AsyncClient
) -> None:
    monitor = await create_monitor(other_client)
    url = f"/api/monitors/{monitor['id']}"

    assert (await superadmin_client.put(url, json=MONITOR)).status_code == 404
    assert (await superadmin_client.delete(url)).status_code == 404
    assert (await superadmin_client.get("/api/monitors")).json() == []


async def test_foreign_channel_cannot_be_linked_or_managed(
    client: AsyncClient, other_client: AsyncClient, fake_telegram: FakeTelegram
) -> None:
    await connect(other_client, token="token-beta")
    channel = await add_channel(other_client, chat_id=-100)

    created = await client.post("/api/monitors", json=MONITOR | {"channel_ids": [channel["id"]]})
    assert created.status_code == 422
    assert (await client.get("/api/channels")).json() == []
    url = f"/api/channels/{channel['id']}"
    assert (await client.patch(url, json={"name": "x"})).status_code == 404
    assert (await client.delete(url)).status_code == 404


async def test_each_user_has_own_telegram_connection(
    client: AsyncClient, other_client: AsyncClient, fake_telegram: FakeTelegram
) -> None:
    await connect(client)

    assert (await other_client.get("/api/telegram")).json()["connected"] is False
    assert (await connect(other_client, token="token-beta")).status_code == 200
    assert (await client.get("/api/telegram")).json()["bot_username"] == "alpha_bot"

    assert (await other_client.delete("/api/telegram")).status_code == 204
    assert (await client.get("/api/telegram")).json()["connected"] is True


async def test_bot_of_another_user_is_rejected(
    client: AsyncClient, other_client: AsyncClient, fake_telegram: FakeTelegram
) -> None:
    await connect(client)

    response = await connect(other_client)

    assert response.status_code == 422
    [error] = response.json()["detail"]
    assert (error["loc"][-1], error["type"]) == ("token", "bot_taken")


async def test_users_may_connect_the_same_chat(
    client: AsyncClient, other_client: AsyncClient, fake_telegram: FakeTelegram
) -> None:
    await connect(client)
    await connect(other_client, token="token-beta")

    await add_channel(client, chat_id=-100)
    await add_channel(other_client, chat_id=-100)

    fake_telegram.updates = [chat_member_update(1, GROUP, "member")]
    [chat] = (await other_client.post("/api/telegram/discover")).json()
    assert chat["connected"] is True
