"""Доставка оповещений: от проверки монитора до сообщения в Telegram и записи в истории."""

from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Monitor, TelegramConnection
from app.monitoring.scheduler import Scheduler
from app.notifications.alerts import deliver_pending
from app.notifications.telegram import TelegramClient
from tests.conftest import ClientFor, FakeTelegram, add_user
from tests.test_telegram_api import add_channel, connect

SessionFactory = async_sessionmaker[AsyncSession]


class Target:
    """Проверяемый сайт: отвечает заданным кодом."""

    def __init__(self) -> None:
        self.status = 200

    def handle(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(self.status)


@pytest.fixture
async def superadmin_client(client_for: ClientFor, session_factory: SessionFactory) -> AsyncClient:
    return await client_for(await add_user(session_factory, 9009), is_superadmin=True)


@pytest.fixture
def target() -> Target:
    return Target()


@pytest.fixture
async def scheduler(
    session_factory: SessionFactory, telegram_client: TelegramClient, target: Target
) -> AsyncIterator[Scheduler]:
    async def notify(monitor_id: int) -> None:
        await deliver_pending(session_factory, telegram_client, monitor_id)

    async with httpx.AsyncClient(transport=httpx.MockTransport(target.handle)) as http:
        yield Scheduler(session_factory, http, notify)


async def create_monitor(client: AsyncClient, channel_ids: list[int]) -> int:
    response = await client.post(
        "/api/monitors",
        json={"name": "API", "url": "https://example.com/health", "channel_ids": channel_ids},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def check(scheduler: Scheduler, session_factory: SessionFactory, monitor_id: int) -> None:
    """Плановая проверка монитора, как её выполняет планировщик."""
    async with session_factory() as session:
        monitor = await session.get(Monitor, monitor_id)
    assert monitor is not None
    await scheduler.check(monitor)


async def latest_check(client: AsyncClient, monitor_id: int) -> dict[str, Any]:
    return (await client.get(f"/api/monitors/{monitor_id}/checks")).json()[0]


async def test_down_alert_is_delivered_and_shown_at_its_check(
    client: AsyncClient,
    fake_telegram: FakeTelegram,
    scheduler: Scheduler,
    session_factory: SessionFactory,
    target: Target,
) -> None:
    await connect(client)
    channel = await add_channel(client, chat_id=-100)
    monitor_id = await create_monitor(client, [channel["id"]])
    fake_telegram.sent.clear()
    target.status = 503

    await check(scheduler, session_factory, monitor_id)

    [(chat_id, text)] = fake_telegram.sent
    assert chat_id == -100
    assert "упал" in text
    alert = (await latest_check(client, monitor_id))["alert"]
    assert alert["kind"] == "down"
    [delivery] = alert["deliveries"]
    assert delivery["channel_id"] == channel["id"]
    assert delivery["channel_name"] == "chat -100"
    assert delivery["status"] == "delivered"
    assert delivery["attempts"] == 1
    assert delivery["error"] is None


async def test_failed_delivery_is_retried_at_next_check_only_where_it_failed(
    client: AsyncClient,
    fake_telegram: FakeTelegram,
    scheduler: Scheduler,
    session_factory: SessionFactory,
    target: Target,
) -> None:
    await connect(client)
    ok = await add_channel(client, chat_id=-100)
    kicked = await add_channel(client, chat_id=-200)
    monitor_id = await create_monitor(client, [ok["id"], kicked["id"]])
    fake_telegram.sent.clear()
    fake_telegram.kicked_from.add(-200)
    target.status = 503

    await check(scheduler, session_factory, monitor_id)

    assert [chat_id for chat_id, _ in fake_telegram.sent] == [-100]
    deliveries = {
        d["channel_id"]: d for d in (await latest_check(client, monitor_id))["alert"]["deliveries"]
    }
    assert deliveries[ok["id"]]["status"] == "delivered"
    failed = deliveries[kicked["id"]]
    assert failed["status"] == "pending"
    assert (failed["error"], failed["telegram_error_code"]) == ("Forbidden: bot was kicked", 403)
    [pending] = (await client.get(f"/api/monitors/{monitor_id}")).json()["pending_deliveries"]
    assert (pending["channel_id"], pending["alert_kind"]) == (kicked["id"], "down")

    fake_telegram.sent.clear()
    fake_telegram.kicked_from.clear()
    await check(scheduler, session_factory, monitor_id)

    [(chat_id, text)] = fake_telegram.sent
    assert chat_id == -200
    assert "упал" in text and "Повторная попытка" in text
    assert (await client.get(f"/api/monitors/{monitor_id}")).json()["pending_deliveries"] == []
    [_, first_check] = (await client.get(f"/api/monitors/{monitor_id}/checks")).json()
    retried = {d["channel_id"]: d for d in first_check["alert"]["deliveries"]}[kicked["id"]]
    assert (retried["status"], retried["attempts"], retried["error"]) == ("delivered", 2, None)


async def test_undelivered_down_alert_is_superseded_by_recovery(
    client: AsyncClient,
    fake_telegram: FakeTelegram,
    scheduler: Scheduler,
    session_factory: SessionFactory,
    target: Target,
) -> None:
    await connect(client)
    channel = await add_channel(client, chat_id=-100)
    monitor_id = await create_monitor(client, [channel["id"]])
    fake_telegram.kicked_from.add(-100)
    target.status = 503
    await check(scheduler, session_factory, monitor_id)

    fake_telegram.sent.clear()
    fake_telegram.kicked_from.clear()
    target.status = 200
    await check(scheduler, session_factory, monitor_id)

    [(_, text)] = fake_telegram.sent
    assert "восстановился" in text
    recovery, down = (await client.get(f"/api/monitors/{monitor_id}/checks")).json()
    assert [d["status"] for d in down["alert"]["deliveries"]] == ["cancelled"]
    assert [d["status"] for d in recovery["alert"]["deliveries"]] == ["delivered"]


async def test_alert_waits_for_telegram_connection(
    client: AsyncClient,
    fake_telegram: FakeTelegram,
    scheduler: Scheduler,
    session_factory: SessionFactory,
    target: Target,
) -> None:
    await connect(client)
    channel = await add_channel(client, chat_id=-100)
    monitor_id = await create_monitor(client, [channel["id"]])
    # Через API так не выйдет: отключение Telegram удаляет и каналы. Защита на случай
    # рассинхронизации базы — Оповещение не теряется молча.
    async with session_factory() as session:
        await session.execute(delete(TelegramConnection))
        await session.commit()
    fake_telegram.sent.clear()
    target.status = 503

    await check(scheduler, session_factory, monitor_id)

    assert fake_telegram.sent == []
    [pending] = (await client.get(f"/api/monitors/{monitor_id}")).json()["pending_deliveries"]
    assert pending["error"] == "нет Подключения Telegram"

    await connect(client)
    await check(scheduler, session_factory, monitor_id)

    assert [chat_id for chat_id, _ in fake_telegram.sent] == [-100]
    assert (await client.get(f"/api/monitors/{monitor_id}")).json()["pending_deliveries"] == []


async def test_monitor_without_channels_records_no_alert(
    client: AsyncClient,
    fake_telegram: FakeTelegram,
    scheduler: Scheduler,
    session_factory: SessionFactory,
    target: Target,
) -> None:
    monitor_id = await create_monitor(client, [])
    target.status = 503

    await check(scheduler, session_factory, monitor_id)

    assert (await latest_check(client, monitor_id))["alert"] is None


async def failing_to_deliver(
    client: AsyncClient,
    fake_telegram: FakeTelegram,
    scheduler: Scheduler,
    session_factory: SessionFactory,
    target: Target,
    chat_ids: list[int],
) -> tuple[int, list[dict[str, Any]]]:
    """Монитор упал, а «упал» не доставлен ни в один из его каналов."""
    await connect(client)
    channels = [await add_channel(client, chat_id=chat_id) for chat_id in chat_ids]
    monitor_id = await create_monitor(client, [c["id"] for c in channels])
    fake_telegram.kicked_from.update(chat_ids)
    target.status = 503
    await check(scheduler, session_factory, monitor_id)
    return monitor_id, channels


async def delivery_statuses(client: AsyncClient, monitor_id: int) -> dict[int, str]:
    """Статусы Доставок «упал» по id канала; проверка «упал» — самая ранняя в истории."""
    checks = (await client.get(f"/api/monitors/{monitor_id}/checks")).json()
    return {d["channel_id"]: d["status"] for d in checks[-1]["alert"]["deliveries"]}


async def test_pause_cancels_pending_deliveries(
    client: AsyncClient,
    fake_telegram: FakeTelegram,
    scheduler: Scheduler,
    session_factory: SessionFactory,
    target: Target,
) -> None:
    monitor_id, [channel] = await failing_to_deliver(
        client, fake_telegram, scheduler, session_factory, target, [-100]
    )

    paused = (await client.post(f"/api/monitors/{monitor_id}/pause")).json()

    assert paused["pending_deliveries"] == []
    assert await delivery_statuses(client, monitor_id) == {channel["id"]: "cancelled"}


async def test_redefining_monitor_cancels_pending_deliveries(
    client: AsyncClient,
    fake_telegram: FakeTelegram,
    scheduler: Scheduler,
    session_factory: SessionFactory,
    target: Target,
) -> None:
    monitor_id, [channel] = await failing_to_deliver(
        client, fake_telegram, scheduler, session_factory, target, [-100]
    )

    updated = await client.put(
        f"/api/monitors/{monitor_id}",
        json={"name": "API", "url": "https://example.com/v2", "channel_ids": [channel["id"]]},
    )

    assert updated.json()["pending_deliveries"] == []
    assert await delivery_statuses(client, monitor_id) == {channel["id"]: "cancelled"}


async def test_renaming_monitor_keeps_pending_deliveries(
    client: AsyncClient,
    fake_telegram: FakeTelegram,
    scheduler: Scheduler,
    session_factory: SessionFactory,
    target: Target,
) -> None:
    monitor_id, [channel] = await failing_to_deliver(
        client, fake_telegram, scheduler, session_factory, target, [-100]
    )

    updated = await client.put(
        f"/api/monitors/{monitor_id}",
        json={
            "name": "Renamed",
            "url": "https://example.com/health",
            "channel_ids": [channel["id"]],
        },
    )

    assert len(updated.json()["pending_deliveries"]) == 1


async def test_unlinking_channel_cancels_only_its_pending_delivery(
    client: AsyncClient,
    fake_telegram: FakeTelegram,
    scheduler: Scheduler,
    session_factory: SessionFactory,
    target: Target,
) -> None:
    monitor_id, [kept, unlinked] = await failing_to_deliver(
        client, fake_telegram, scheduler, session_factory, target, [-100, -200]
    )

    await client.put(
        f"/api/monitors/{monitor_id}",
        json={"name": "API", "url": "https://example.com/health", "channel_ids": [kept["id"]]},
    )

    assert await delivery_statuses(client, monitor_id) == {
        kept["id"]: "pending",
        unlinked["id"]: "cancelled",
    }


async def test_deleting_channel_stops_its_retries(
    client: AsyncClient,
    fake_telegram: FakeTelegram,
    scheduler: Scheduler,
    session_factory: SessionFactory,
    target: Target,
) -> None:
    monitor_id, [kept, deleted] = await failing_to_deliver(
        client, fake_telegram, scheduler, session_factory, target, [-100, -200]
    )

    await client.delete(f"/api/channels/{deleted['id']}")

    pending = (await client.get(f"/api/monitors/{monitor_id}")).json()["pending_deliveries"]
    assert [d["channel_id"] for d in pending] == [kept["id"]]


async def test_telegram_timeout_is_recorded_and_retried(
    client: AsyncClient,
    fake_telegram: FakeTelegram,
    scheduler: Scheduler,
    session_factory: SessionFactory,
    target: Target,
) -> None:
    await connect(client)
    channel = await add_channel(client, chat_id=-100)
    monitor_id = await create_monitor(client, [channel["id"]])
    fake_telegram.timing_out.add(-100)
    target.status = 503

    await check(scheduler, session_factory, monitor_id)

    [pending] = (await client.get(f"/api/monitors/{monitor_id}")).json()["pending_deliveries"]
    assert (pending["error"], pending["telegram_error_code"]) == (
        "Telegram не ответил вовремя",
        None,
    )
    assert pending["attempts"] == 1


async def test_alert_recorded_before_restart_is_delivered_at_next_check(
    client: AsyncClient,
    fake_telegram: FakeTelegram,
    scheduler: Scheduler,
    session_factory: SessionFactory,
    target: Target,
) -> None:
    await connect(client)
    channel = await add_channel(client, chat_id=-100)
    monitor_id = await create_monitor(client, [channel["id"]])
    fake_telegram.sent.clear()
    target.status = 503

    async def crash(_monitor_id: int) -> None:
        raise RuntimeError("процесс остановлен до отправки")

    async with httpx.AsyncClient(transport=httpx.MockTransport(target.handle)) as http:
        await check(Scheduler(session_factory, http, crash), session_factory, monitor_id)

    [pending] = (await client.get(f"/api/monitors/{monitor_id}")).json()["pending_deliveries"]
    assert (pending["attempts"], pending["error"]) == (0, None)

    await check(scheduler, session_factory, monitor_id)

    [(_, text)] = fake_telegram.sent
    assert "упал" in text and "Повтор" not in text


async def test_channel_deleted_during_delivery_does_not_undo_other_channels(
    client: AsyncClient,
    fake_telegram: FakeTelegram,
    telegram_client: TelegramClient,
    scheduler: Scheduler,
    session_factory: SessionFactory,
    target: Target,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await connect(client)
    kept = await add_channel(client, chat_id=-100)
    deleted = await add_channel(client, chat_id=-200)
    monitor_id = await create_monitor(client, [kept["id"], deleted["id"]])
    fake_telegram.sent.clear()
    target.status = 503
    send_message = telegram_client.send_message

    async def send_while_channel_is_deleted(token: str, chat_id: int, text: str) -> int:
        if chat_id == -200:
            await client.delete(f"/api/channels/{deleted['id']}")
        return await send_message(token, chat_id, text)

    monkeypatch.setattr(telegram_client, "send_message", send_while_channel_is_deleted)

    await check(scheduler, session_factory, monitor_id)
    await check(scheduler, session_factory, monitor_id)

    assert [chat_id for chat_id, _ in fake_telegram.sent].count(-100) == 1
    deliveries = (await client.get(f"/api/monitors/{monitor_id}/checks")).json()[-1]["alert"]
    assert [(d["channel_id"], d["status"]) for d in deliveries["deliveries"]] == [
        (kept["id"], "delivered")
    ]


async def test_superadmin_sees_deliveries_of_others_monitor(
    client: AsyncClient,
    superadmin_client: AsyncClient,
    fake_telegram: FakeTelegram,
    scheduler: Scheduler,
    session_factory: SessionFactory,
    target: Target,
) -> None:
    monitor_id, [channel] = await failing_to_deliver(
        client, fake_telegram, scheduler, session_factory, target, [-100]
    )

    monitor = (await superadmin_client.get(f"/api/monitors/{monitor_id}")).json()
    [check_out] = (await superadmin_client.get(f"/api/monitors/{monitor_id}/checks")).json()

    assert [d["channel_id"] for d in monitor["pending_deliveries"]] == [channel["id"]]
    assert [d["status"] for d in check_out["alert"]["deliveries"]] == ["pending"]
