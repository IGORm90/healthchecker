from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Check
from app.monitoring.retention import next_prune_at, prune_checks

SessionFactory = async_sessionmaker[AsyncSession]

NOW = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)


async def create_monitor(client: AsyncClient) -> int:
    response = await client.post(
        "/api/monitors", json={"name": "Example", "url": "https://example.com/health"}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def add_checks(
    session_factory: SessionFactory, monitor_id: int, *started_at: datetime
) -> None:
    async with session_factory() as session:
        for moment in started_at:
            session.add(
                Check(
                    monitor_id=monitor_id,
                    started_at=moment,
                    duration_ms=1,
                    status_code=200,
                    success=True,
                )
            )
        await session.commit()


async def history(client: AsyncClient, monitor_id: int) -> list[datetime]:
    response = await client.get(f"/api/monitors/{monitor_id}/checks", params={"limit": 500})
    return [datetime.fromisoformat(c["started_at"]) for c in response.json()]


async def test_checks_older_than_three_days_are_pruned(
    client: AsyncClient, session_factory: SessionFactory
) -> None:
    first = await create_monitor(client)
    second = await create_monitor(client)
    boundary = NOW - timedelta(days=3)
    stale = boundary - timedelta(seconds=1)
    fresh = NOW - timedelta(hours=1)
    await add_checks(session_factory, first, stale, boundary, fresh)
    await add_checks(session_factory, second, stale, fresh)

    await prune_checks(session_factory, NOW)

    assert await history(client, first) == [fresh, boundary]
    assert await history(client, second) == [fresh]


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (datetime(2026, 11, 15, 1, 30, tzinfo=UTC), datetime(2026, 11, 15, 3, 0, tzinfo=UTC)),
        (datetime(2026, 11, 15, 3, 0, tzinfo=UTC), datetime(2026, 11, 16, 3, 0, tzinfo=UTC)),
        (datetime(2026, 11, 15, 12, 0, tzinfo=UTC), datetime(2026, 11, 16, 3, 0, tzinfo=UTC)),
        (datetime(2026, 11, 30, 23, 59, tzinfo=UTC), datetime(2026, 12, 1, 3, 0, tzinfo=UTC)),
    ],
)
def test_next_prune_is_at_three_utc_strictly_after_now(now: datetime, expected: datetime) -> None:
    assert next_prune_at(now) == expected
