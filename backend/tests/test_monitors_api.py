from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Check, Monitor, MonitorState, NotificationChannel

SessionFactory = async_sessionmaker[AsyncSession]


def monitor_payload(**overrides: Any) -> dict[str, Any]:
    return {"name": "Example", "url": "https://example.com/health", **overrides}


async def create_monitor(client: AsyncClient, **overrides: Any) -> dict[str, Any]:
    response = await client.post("/api/monitors", json=monitor_payload(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


async def add_channel(session_factory: SessionFactory, chat_id: int) -> int:
    async with session_factory() as session:
        channel = NotificationChannel(name=f"chat {chat_id}", telegram_chat_id=chat_id)
        session.add(channel)
        await session.commit()
        return channel.id


async def set_state(session_factory: SessionFactory, monitor_id: int, state: MonitorState) -> None:
    async with session_factory() as session:
        monitor = await session.get(Monitor, monitor_id)
        assert monitor is not None
        monitor.state = state
        await session.commit()


def error_types(response: Any) -> set[tuple[str, str]]:
    return {(e["loc"][-1], e["type"]) for e in response.json()["detail"]}


async def test_create_applies_defaults(client: AsyncClient) -> None:
    monitor = await create_monitor(client)

    assert monitor["method"] == "GET"
    assert monitor["headers"] == []
    assert monitor["expected_status"] == 200
    assert monitor["expected_body"] is None
    assert monitor["interval_seconds"] == 300
    assert monitor["channel_ids"] == []
    assert monitor["state"] == "unknown"
    assert monitor["next_check_at"] is not None
    assert monitor["last_check_at"] is None


async def test_create_round_trips_request_fields(client: AsyncClient) -> None:
    created = await create_monitor(
        client,
        method="POST",
        headers=[{"name": "Authorization", "value": "Bearer x"}, {"name": "X-A", "value": ""}],
        body='{"ping": true}',
        expected_status=204,
        expected_body="ok",
        interval_seconds=30,
    )

    fetched = (await client.get(f"/api/monitors/{created['id']}")).json()

    assert fetched == created
    assert fetched["headers"][0] == {"name": "Authorization", "value": "Bearer x"}
    assert fetched["body"] == '{"ping": true}'


@pytest.mark.parametrize("method", ["GET", "HEAD"])
async def test_body_is_dropped_for_bodyless_methods(client: AsyncClient, method: str) -> None:
    monitor = await create_monitor(client, method=method, body="ignored")

    assert monitor["body"] is None


async def test_empty_strings_mean_no_body_and_no_body_expectation(client: AsyncClient) -> None:
    monitor = await create_monitor(client, method="POST", body="", expected_body="")

    assert monitor["body"] is None
    assert monitor["expected_body"] is None


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"url": "ftp://example.com/"}, "url"),
        ({"url": "example.com"}, "url"),
        ({"name": "   "}, "name"),
        ({"method": "TRACE"}, "method"),
        ({"interval_seconds": 120}, "interval_seconds"),
        ({"expected_status": 99}, "expected_status"),
        ({"expected_status": 600}, "expected_status"),
        ({"headers": [{"name": "Bad Name", "value": "x"}]}, "name"),
        ({"headers": [{"name": "X-Inject", "value": "a\r\nHost: evil"}]}, "value"),
    ],
)
async def test_create_rejects_invalid_fields(
    client: AsyncClient, overrides: dict[str, Any], field: str
) -> None:
    response = await client.post("/api/monitors", json=monitor_payload(**overrides))

    assert response.status_code == 422
    assert field in {loc for loc, _ in error_types(response)}


async def test_create_rejects_forbidden_target(client: AsyncClient) -> None:
    response = await client.post(
        "/api/monitors", json=monitor_payload(url="http://169.254.169.254/latest/")
    )

    assert response.status_code == 422
    assert error_types(response) == {("url", "forbidden_target")}


async def test_private_target_is_allowed_only_with_flag(
    client: AsyncClient, allow_private_targets: Callable[[bool], None]
) -> None:
    payload = monitor_payload(url="http://192.168.1.10/health")

    assert (await client.post("/api/monitors", json=payload)).status_code == 422

    allow_private_targets(True)
    assert (await client.post("/api/monitors", json=payload)).status_code == 201


async def test_create_links_channels(client: AsyncClient, session_factory: SessionFactory) -> None:
    first = await add_channel(session_factory, -1001)
    second = await add_channel(session_factory, -1002)

    monitor = await create_monitor(client, channel_ids=[second, first, second])

    assert monitor["channel_ids"] == sorted([first, second])


async def test_create_rejects_unknown_channel(client: AsyncClient) -> None:
    response = await client.post("/api/monitors", json=monitor_payload(channel_ids=[42]))

    assert response.status_code == 422
    assert error_types(response) == {("channel_ids", "unknown_channel")}


async def test_list_returns_monitors_with_last_check_time(
    client: AsyncClient, session_factory: SessionFactory
) -> None:
    checked = await create_monitor(client, name="B")
    await create_monitor(client, name="A")
    started_at = datetime(2026, 11, 1, 12, tzinfo=UTC)
    async with session_factory() as session:
        for offset in (0, 30):
            session.add(
                Check(
                    monitor_id=checked["id"],
                    started_at=started_at + timedelta(seconds=offset),
                    duration_ms=10,
                    status_code=200,
                    success=True,
                )
            )
        await session.commit()

    monitors = (await client.get("/api/monitors")).json()

    assert [m["name"] for m in monitors] == ["A", "B"]
    assert monitors[0]["last_check_at"] is None
    assert datetime.fromisoformat(monitors[1]["last_check_at"]) == started_at + timedelta(
        seconds=30
    )


async def test_get_unknown_monitor_returns_404(client: AsyncClient) -> None:
    assert (await client.get("/api/monitors/999")).status_code == 404


@pytest.mark.parametrize(
    "change",
    [
        {"url": "https://example.com/other"},
        {"method": "POST"},
        {"headers": [{"name": "X-A", "value": "1"}]},
        {"expected_status": 201},
        {"expected_body": "ok"},
    ],
)
async def test_update_of_check_definition_resets_state(
    client: AsyncClient, session_factory: SessionFactory, change: dict[str, Any]
) -> None:
    monitor = await create_monitor(client)
    await set_state(session_factory, monitor["id"], MonitorState.DOWN)

    response = await client.put(f"/api/monitors/{monitor['id']}", json=monitor_payload(**change))

    assert response.status_code == 200
    assert response.json()["state"] == "unknown"


async def test_update_of_name_keeps_state(
    client: AsyncClient, session_factory: SessionFactory
) -> None:
    channel = await add_channel(session_factory, -1001)
    monitor = await create_monitor(client)
    await set_state(session_factory, monitor["id"], MonitorState.DOWN)

    response = await client.put(
        f"/api/monitors/{monitor['id']}",
        json=monitor_payload(name="Renamed", channel_ids=[channel]),
    )

    assert response.json()["state"] == "down"
    assert response.json()["name"] == "Renamed"
    assert response.json()["channel_ids"] == [channel]


async def test_shorter_interval_brings_next_check_closer(
    client: AsyncClient, session_factory: SessionFactory
) -> None:
    monitor = await create_monitor(client, interval_seconds=3600)
    async with session_factory() as session:
        stored = await session.get(Monitor, monitor["id"])
        assert stored is not None
        stored.next_check_at = datetime.now(UTC) + timedelta(hours=1)
        await session.commit()

    before = datetime.now(UTC)
    response = await client.put(
        f"/api/monitors/{monitor['id']}", json=monitor_payload(interval_seconds=30)
    )

    next_check_at = datetime.fromisoformat(response.json()["next_check_at"])
    assert before < next_check_at <= before + timedelta(seconds=31)
    assert response.json()["state"] == "unknown"


async def test_update_keeps_paused_monitor_paused(client: AsyncClient) -> None:
    monitor = await create_monitor(client)
    await client.post(f"/api/monitors/{monitor['id']}/pause")

    response = await client.put(
        f"/api/monitors/{monitor['id']}", json=monitor_payload(url="https://example.com/other")
    )

    assert response.json()["state"] == "paused"
    assert response.json()["next_check_at"] is None


async def test_pause_and_resume(client: AsyncClient) -> None:
    monitor = await create_monitor(client)

    paused = (await client.post(f"/api/monitors/{monitor['id']}/pause")).json()
    assert paused["state"] == "paused"
    assert paused["next_check_at"] is None

    resumed = (await client.post(f"/api/monitors/{monitor['id']}/resume")).json()
    assert resumed["state"] == "unknown"
    assert resumed["next_check_at"] is not None


async def test_resume_of_active_monitor_changes_nothing(
    client: AsyncClient, session_factory: SessionFactory
) -> None:
    monitor = await create_monitor(client)
    await set_state(session_factory, monitor["id"], MonitorState.UP)

    response = await client.post(f"/api/monitors/{monitor['id']}/resume")

    assert response.json()["state"] == "up"


async def test_delete_removes_monitor_and_its_checks(
    client: AsyncClient, session_factory: SessionFactory
) -> None:
    channel = await add_channel(session_factory, -1001)
    monitor = await create_monitor(client, channel_ids=[channel])
    async with session_factory() as session:
        session.add(
            Check(
                monitor_id=monitor["id"],
                started_at=datetime.now(UTC),
                duration_ms=1,
                success=False,
                failure_reason="таймаут 10 с",
            )
        )
        await session.commit()

    assert (await client.delete(f"/api/monitors/{monitor['id']}")).status_code == 204

    assert (await client.get(f"/api/monitors/{monitor['id']}")).status_code == 404
    async with session_factory() as session:
        assert await session.get(NotificationChannel, channel) is not None
        assert (await session.get(Check, 1)) is None


async def test_checks_are_newest_first_and_limited(
    client: AsyncClient, session_factory: SessionFactory
) -> None:
    monitor = await create_monitor(client)
    start = datetime(2026, 11, 1, tzinfo=UTC)
    async with session_factory() as session:
        for i in range(5):
            session.add(
                Check(
                    monitor_id=monitor["id"],
                    started_at=start + timedelta(minutes=i),
                    duration_ms=i,
                    status_code=200,
                    success=True,
                )
            )
        await session.commit()

    response = await client.get(f"/api/monitors/{monitor['id']}/checks", params={"limit": 3})

    assert [c["duration_ms"] for c in response.json()] == [4, 3, 2]


async def test_checks_of_unknown_monitor_return_404(client: AsyncClient) -> None:
    assert (await client.get("/api/monitors/999/checks")).status_code == 404
