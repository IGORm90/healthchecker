from collections.abc import AsyncIterator
from datetime import timedelta

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.types import utcnow
from app.models import Monitor, MonitorState, User
from app.monitoring.scheduler import Alert, Scheduler
from tests.conftest import default_user_id

SessionFactory = async_sessionmaker[AsyncSession]


async def ignore(_alert: Alert) -> None:
    pass


@pytest.fixture
async def scheduler(session_factory: SessionFactory, user: User) -> AsyncIterator[Scheduler]:
    async with httpx.AsyncClient() as http:
        yield Scheduler(session_factory, http, ignore)


async def add_monitor(session_factory: SessionFactory, **overrides: object) -> int:
    fields: dict[str, object] = {
        "user_id": await default_user_id(session_factory),
        "name": "Example",
        "url": "https://example.com",
        "interval_seconds": 60,
        "next_check_at": utcnow() - timedelta(seconds=1),
    }
    async with session_factory() as session:
        monitor = Monitor(**(fields | overrides))
        session.add(monitor)
        await session.commit()
        return monitor.id


async def test_due_monitor_is_taken_once_and_rescheduled(
    scheduler: Scheduler, session_factory: SessionFactory
) -> None:
    monitor_id = await add_monitor(session_factory)

    [taken] = await scheduler.take_due_monitors()

    assert taken.id == monitor_id
    assert await scheduler.take_due_monitors() == []
    async with session_factory() as session:
        monitor = await session.get(Monitor, monitor_id)
        assert monitor is not None and monitor.next_check_at is not None
        assert monitor.next_check_at - utcnow() > timedelta(seconds=55)


async def test_future_and_paused_monitors_are_not_taken(
    scheduler: Scheduler, session_factory: SessionFactory
) -> None:
    await add_monitor(session_factory, next_check_at=utcnow() + timedelta(minutes=1))
    await add_monitor(session_factory, state=MonitorState.PAUSED, next_check_at=None)

    assert await scheduler.take_due_monitors() == []


async def test_pause_between_select_and_reschedule_wins(
    scheduler: Scheduler, session_factory: SessionFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monitor_id = await add_monitor(session_factory)
    select_due = scheduler._select_due

    async def select_then_pause(session: AsyncSession) -> list[Monitor]:
        # Пауза приходит из API, пока планировщик между чтением и записью.
        due = await select_due(session)
        async with session_factory() as other:
            monitor = await other.get(Monitor, monitor_id)
            assert monitor is not None
            monitor.state = MonitorState.PAUSED
            monitor.next_check_at = None
            await other.commit()
        return due

    monkeypatch.setattr(scheduler, "_select_due", select_then_pause)

    assert await scheduler.take_due_monitors() == []
    async with session_factory() as session:
        monitor = await session.get(Monitor, monitor_id)
        assert monitor is not None
        assert (monitor.state, monitor.next_check_at) == (MonitorState.PAUSED, None)
