from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import HttpMethod, Monitor
from app.monitoring.scheduler import Alert
from app.monitoring.state import AlertKind
from app.notifications.alerts import alert_text, send_alert
from app.notifications.telegram import TelegramClient
from tests.conftest import FakeTelegram
from tests.test_telegram_api import add_channel, connect

DOWN_AT = datetime(2026, 11, 14, 9, 30, 5, tzinfo=UTC)


def monitor(**overrides: object) -> Monitor:
    fields = {"name": "API", "url": "https://example.com/health", "method": HttpMethod.HEAD}
    return Monitor(**(fields | overrides))


def test_down_alert_names_monitor_request_reason_and_time() -> None:
    text = alert_text(
        Alert(monitor(), AlertKind.DOWN, "ожидался 200, получен 503", DOWN_AT), DOWN_AT
    )

    assert text == (
        "🔴 <b>API</b> упал\n"
        "HEAD https://example.com/health\n"
        "Причина: ожидался 200, получен 503\n"
        "Время: 14.11.2026 09:30:05 UTC"
    )


def test_recovery_alert_shows_downtime() -> None:
    now = DOWN_AT + timedelta(hours=1, minutes=5, seconds=12)

    text = alert_text(Alert(monitor(), AlertKind.RECOVERED, None, DOWN_AT), now)

    assert text == "🟢 <b>API</b> восстановился\nhttps://example.com/health\nПростой: 1 ч 5 мин"


def test_user_text_is_html_escaped() -> None:
    alert = Alert(
        monitor(name="<API>", url="https://example.com/?a=1&b=2"), AlertKind.DOWN, "<x>", DOWN_AT
    )

    text = alert_text(alert, DOWN_AT)

    assert "&lt;API&gt;" in text
    assert "a=1&amp;b=2" in text
    assert "&lt;x&gt;" in text


async def test_alert_goes_to_every_monitor_channel_and_records_failures(
    client: AsyncClient,
    fake_telegram: FakeTelegram,
    telegram_client: TelegramClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await connect(client)
    ok = await add_channel(client, chat_id=-100)
    kicked = await add_channel(client, chat_id=-200)
    await add_channel(client, chat_id=-300)
    created = await client.post(
        "/api/monitors",
        json={"name": "API", "url": "https://example.com", "channel_ids": [ok["id"], kicked["id"]]},
    )
    fake_telegram.sent.clear()
    fake_telegram.kicked_from.add(-200)

    async with session_factory() as session:
        target = await session.get(Monitor, created.json()["id"])
    assert target is not None
    await send_alert(
        session_factory, telegram_client, Alert(target, AlertKind.DOWN, "таймаут 10 с", DOWN_AT)
    )

    assert [chat_id for chat_id, _ in fake_telegram.sent] == [-100]
    errors = {
        c["telegram_chat_id"]: c["last_delivery_error"]
        for c in (await client.get("/api/channels")).json()
    }
    assert errors == {-100: None, -200: "Forbidden: bot was kicked", -300: None}
