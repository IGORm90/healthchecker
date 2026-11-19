from typing import Any

from httpx import AsyncClient

from tests.conftest import FakeTelegram
from tests.test_telegram_api import add_channel, connect


async def create_monitor(client: AsyncClient, channel_ids: list[int]) -> dict[str, Any]:
    response = await client.post(
        "/api/monitors",
        json={"name": "Example", "url": "https://example.com", "channel_ids": channel_ids},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_created_channel_gets_test_message(
    client: AsyncClient, fake_telegram: FakeTelegram
) -> None:
    await connect(client)

    channel = await add_channel(client, chat_id=-100)

    assert [chat_id for chat_id, _ in fake_telegram.sent] == [-100]
    assert channel["name"] == "chat -100"
    assert channel["kind"] == "telegram"
    assert channel["monitors_count"] == 0
    assert channel["test_message_error"] is None
    assert channel["last_delivery"] is None


async def test_failed_test_message_is_reported_but_channel_is_created(
    client: AsyncClient, fake_telegram: FakeTelegram
) -> None:
    await connect(client)
    fake_telegram.kicked_from.add(-100)

    channel = await add_channel(client, chat_id=-100)

    assert channel["test_message_error"] == "Forbidden: bot was kicked"
    [listed] = (await client.get("/api/channels")).json()
    assert listed["id"] == channel["id"]
    assert listed["last_delivery"] is None


async def test_channel_name_is_html_escaped_in_test_message(
    client: AsyncClient, fake_telegram: FakeTelegram
) -> None:
    await connect(client)

    await client.post("/api/channels", json={"name": "<b>ops</b>", "telegram_chat_id": -100})

    [(_, text)] = fake_telegram.sent
    assert "&lt;b&gt;ops&lt;/b&gt;" in text


async def test_same_chat_cannot_be_connected_twice(
    client: AsyncClient, fake_telegram: FakeTelegram
) -> None:
    await connect(client)
    await add_channel(client, chat_id=-100)

    response = await client.post("/api/channels", json={"name": "again", "telegram_chat_id": -100})

    assert response.status_code == 422
    [error] = response.json()["detail"]
    assert (error["loc"][-1], error["type"]) == ("telegram_chat_id", "duplicate_channel")


async def test_channel_requires_telegram_connection(
    client: AsyncClient, fake_telegram: FakeTelegram
) -> None:
    response = await client.post("/api/channels", json={"name": "ops", "telegram_chat_id": -100})

    assert response.status_code == 409


async def test_list_counts_linked_monitors(
    client: AsyncClient, fake_telegram: FakeTelegram
) -> None:
    await connect(client)
    used = await add_channel(client, chat_id=-100)
    await add_channel(client, chat_id=-200)
    await create_monitor(client, channel_ids=[used["id"]])
    await create_monitor(client, channel_ids=[used["id"]])

    counts = {
        c["telegram_chat_id"]: c["monitors_count"]
        for c in (await client.get("/api/channels")).json()
    }

    assert counts == {-100: 2, -200: 0}


async def test_deleted_channel_is_unlinked_from_monitors(
    client: AsyncClient, fake_telegram: FakeTelegram
) -> None:
    await connect(client)
    channel = await add_channel(client, chat_id=-100)
    monitor = await create_monitor(client, channel_ids=[channel["id"]])

    assert (await client.delete(f"/api/channels/{channel['id']}")).status_code == 204

    reloaded = (await client.get(f"/api/monitors/{monitor['id']}")).json()
    assert reloaded["channel_ids"] == []


async def test_rename_channel(client: AsyncClient, fake_telegram: FakeTelegram) -> None:
    await connect(client)
    channel = await add_channel(client, chat_id=-100)

    response = await client.patch(f"/api/channels/{channel['id']}", json={"name": "  Ops  "})

    assert response.json()["name"] == "Ops"


async def test_test_message_on_demand(client: AsyncClient, fake_telegram: FakeTelegram) -> None:
    await connect(client)
    channel = await add_channel(client, chat_id=-100)
    fake_telegram.kicked_from.add(-100)

    response = await client.post(f"/api/channels/{channel['id']}/test")

    assert response.status_code == 502
    assert response.json()["detail"] == {
        "code": "telegram_error",
        "message": "Forbidden: bot was kicked",
    }
    [listed] = (await client.get("/api/channels")).json()
    assert listed["last_delivery"] is None


async def test_successful_test_message(client: AsyncClient, fake_telegram: FakeTelegram) -> None:
    await connect(client)
    channel = await add_channel(client, chat_id=-100)

    response = await client.post(f"/api/channels/{channel['id']}/test")

    assert response.status_code == 200
    assert fake_telegram.sent[-1] == (-100, "🔔 Тестовое сообщение Healthchecker")
