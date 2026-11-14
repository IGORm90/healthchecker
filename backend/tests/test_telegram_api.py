from typing import Any

from httpx import AsyncClient

from tests.conftest import FakeTelegram


async def connect(client: AsyncClient, token: str = "token-alpha", **extra: Any) -> Any:
    return await client.put("/api/telegram", json={"token": token, **extra})


async def add_channel(client: AsyncClient, chat_id: int) -> dict[str, Any]:
    response = await client.post(
        "/api/channels", json={"name": f"chat {chat_id}", "telegram_chat_id": chat_id}
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_not_connected_by_default(client: AsyncClient) -> None:
    response = await client.get("/api/telegram")

    assert response.json() == {"connected": False, "bot_username": None}


async def test_connect_with_valid_token(client: AsyncClient, fake_telegram: FakeTelegram) -> None:
    response = await connect(client)

    assert response.status_code == 200
    assert response.json() == {"connected": True, "bot_username": "alpha_bot"}
    assert (await client.get("/api/telegram")).json()["bot_username"] == "alpha_bot"


async def test_rejected_token_is_a_field_error(
    client: AsyncClient, fake_telegram: FakeTelegram
) -> None:
    response = await connect(client, token="wrong")

    assert response.status_code == 422
    [error] = response.json()["detail"]
    assert (error["loc"][-1], error["type"]) == ("token", "invalid_token")
    assert "Unauthorized" in error["msg"]
    assert "wrong" not in error["msg"]


async def test_reconnecting_same_bot_keeps_channels(
    client: AsyncClient, fake_telegram: FakeTelegram
) -> None:
    await connect(client)
    await add_channel(client, chat_id=-100)

    response = await connect(client)

    assert response.status_code == 200
    assert len((await client.get("/api/channels")).json()) == 1


async def test_switching_bot_requires_confirmation_when_channels_exist(
    client: AsyncClient, fake_telegram: FakeTelegram
) -> None:
    await connect(client)
    await add_channel(client, chat_id=-100)
    await add_channel(client, chat_id=-200)

    response = await connect(client, token="token-beta")

    assert response.status_code == 409
    assert response.json()["detail"]["channels_count"] == 2
    assert (await client.get("/api/telegram")).json()["bot_username"] == "alpha_bot"


async def test_confirmed_bot_switch_removes_channels(
    client: AsyncClient, fake_telegram: FakeTelegram
) -> None:
    await connect(client)
    await add_channel(client, chat_id=-100)

    response = await connect(client, token="token-beta", confirm_replace=True)

    assert response.json() == {"connected": True, "bot_username": "beta_bot"}
    assert (await client.get("/api/channels")).json() == []


async def test_disconnect_removes_connection_and_channels(
    client: AsyncClient, fake_telegram: FakeTelegram
) -> None:
    await connect(client)
    await add_channel(client, chat_id=-100)

    assert (await client.delete("/api/telegram")).status_code == 204

    assert (await client.get("/api/telegram")).json()["connected"] is False
    assert (await client.get("/api/channels")).json() == []


def chat_member_update(update_id: int, chat: dict[str, Any], status: str) -> dict[str, Any]:
    return {
        "update_id": update_id,
        "my_chat_member": {"chat": chat, "new_chat_member": {"status": status}},
    }


GROUP = {"id": -100, "title": "Ops", "type": "group"}
SUPERGROUP = {"id": -200, "title": "Alerts", "type": "supergroup"}
PRIVATE = {"id": 42, "first_name": "Igor", "type": "private"}


async def test_discover_finds_chats_the_bot_is_in(
    client: AsyncClient, fake_telegram: FakeTelegram
) -> None:
    await connect(client)
    fake_telegram.updates = [
        chat_member_update(1, GROUP, "member"),
        chat_member_update(2, SUPERGROUP, "administrator"),
        chat_member_update(3, SUPERGROUP, "left"),
        {"update_id": 4, "message": {"chat": PRIVATE, "text": "/start"}},
    ]

    response = await client.post("/api/telegram/discover")

    assert response.status_code == 200
    assert response.json() == [
        {"chat_id": -100, "title": "Ops", "type": "group", "connected": False},
        {"chat_id": 42, "title": "Igor", "type": "private", "connected": False},
    ]


async def test_discover_marks_connected_chats(
    client: AsyncClient, fake_telegram: FakeTelegram
) -> None:
    await connect(client)
    await add_channel(client, chat_id=-100)
    fake_telegram.updates = [chat_member_update(1, GROUP, "member")]

    [chat] = (await client.post("/api/telegram/discover")).json()

    assert chat["connected"] is True


async def test_discover_does_not_repeat_read_updates(
    client: AsyncClient, fake_telegram: FakeTelegram
) -> None:
    await connect(client)
    fake_telegram.updates = [chat_member_update(1, GROUP, "member")]
    await client.post("/api/telegram/discover")

    response = await client.post("/api/telegram/discover")

    assert response.json() == []


async def test_discover_requires_connection(
    client: AsyncClient, fake_telegram: FakeTelegram
) -> None:
    response = await client.post("/api/telegram/discover")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "telegram_not_connected"
