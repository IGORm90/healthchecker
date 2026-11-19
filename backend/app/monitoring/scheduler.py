"""Планировщик: раз в секунду запускает Проверки мониторов, у которых наступил next_check_at.

После каждой записанной Проверки повторяет недоставленные Оповещения монитора (план 0006).

Работает в единственном экземпляре в lifespan, поэтому backend запускается одним процессом.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import timedelta

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.db.types import utcnow
from app.models import Alert, AlertDelivery, AlertKind, Check, Monitor, MonitorState, User
from app.monitoring.runner import CheckResult, run_check
from app.monitoring.state import transition
from app.notifications.alerts import cancel_pending

logger = logging.getLogger(__name__)

TICK_SECONDS = 1
MAX_PARALLEL_CHECKS = 20

# Отправляет недоставленные Оповещения монитора по его id.
Notify = Callable[[int], Awaitable[None]]


class Scheduler:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        http: httpx.AsyncClient,
        notify: Notify,
    ) -> None:
        self._session_factory = session_factory
        self._http = http
        self._notify = notify
        self._semaphore = asyncio.Semaphore(MAX_PARALLEL_CHECKS)
        # id мониторов, чья проверка запущена и ещё не записана.
        self._in_flight: set[int] = set()

    async def run(self) -> None:
        async with asyncio.TaskGroup() as group:
            while True:
                try:
                    for monitor in await self.take_due_monitors():
                        self._in_flight.add(monitor.id)
                        group.create_task(self.check(monitor))
                except Exception:
                    logger.exception("Не удалось выбрать мониторы для проверки")
                await asyncio.sleep(TICK_SECONDS)

    async def take_due_monitors(self) -> list[Monitor]:
        """Мониторы с наступившей проверкой; их next_check_at сразу сдвигается.

        Так следующий тик не возьмёт их повторно, а просроченный после рестарта монитор
        проверяется один раз, без «догоняющей» серии. Отсчёт — от старта проверки.
        Мониторы, чья проверка ещё идёт, пропускаются: проверки одного монитора не
        накладываются.
        """
        now = utcnow()
        taken = []
        async with self._session_factory() as session:
            for monitor in await self._select_due(session):
                # Сдвиг условный: если между чтением и записью монитор поставили на паузу
                # или изменили (API сам выставил next_check_at), побеждает API.
                result = await session.execute(
                    update(Monitor)
                    .where(
                        Monitor.id == monitor.id,
                        Monitor.next_check_at == monitor.next_check_at,
                        Monitor.state != MonitorState.PAUSED,
                    )
                    .values(next_check_at=now + timedelta(seconds=monitor.interval_seconds))
                    .execution_options(synchronize_session=False)
                )
                if result.rowcount == 1:
                    taken.append(monitor)
            await session.commit()
        return taken

    async def _select_due(self, session: AsyncSession) -> list[Monitor]:
        return list(
            await session.scalars(
                select(Monitor)
                # Мониторы заблокированных Пользователей не проверяются; их next_check_at
                # остаётся в прошлом, и после разблокировки они проверяются в ближайший тик.
                .join(User, User.id == Monitor.user_id)
                .where(
                    Monitor.next_check_at <= utcnow(),
                    Monitor.id.not_in(self._in_flight),
                    User.blocked_at.is_(None),
                )
                .order_by(Monitor.id)
            )
        )

    async def check(self, snapshot: Monitor) -> None:
        """Проверяет монитор, записывает результат и повторяет недоставленные Оповещения."""
        try:
            async with self._semaphore:
                result = await run_check(self._http, snapshot)
            if await self._record(snapshot, result):
                await self._notify(snapshot.id)
        except Exception:
            logger.exception("Сбой проверки монитора %s", snapshot.id)
        finally:
            self._in_flight.discard(snapshot.id)

    async def _record(self, snapshot: Monitor, result: CheckResult) -> bool:
        """Записывает проверку и Оповещение о смене Состояния; False — результат устарел."""
        async with self._session_factory() as session:
            monitor = await session.get(
                Monitor, snapshot.id, options=[selectinload(Monitor.channels)]
            )
            # Пока шла проверка, монитор удалили, поставили на паузу или изменили то, что
            # проверяется: каждое из этих действий меняет state_changed_at. Результат устарел.
            if monitor is None or monitor.state_changed_at != snapshot.state_changed_at:
                return False

            check = Check(
                monitor_id=monitor.id,
                started_at=result.started_at,
                duration_ms=result.duration_ms,
                status_code=result.status_code,
                success=result.success,
                failure_reason=result.failure_reason,
            )
            session.add(check)
            previous_change = monitor.state_changed_at
            new_state, alert_kind = transition(monitor.state, result.success)
            if new_state != monitor.state:
                monitor.state = new_state
                monitor.state_changed_at = result.started_at

            if alert_kind is not None:
                # Новое Оповещение вытесняет недоставленные прежние.
                await cancel_pending(session, monitor.id)
                if monitor.channels:
                    session.add(
                        Alert(
                            monitor_id=monitor.id,
                            check=check,
                            kind=alert_kind,
                            reason=result.failure_reason,
                            down_since=previous_change
                            if alert_kind is AlertKind.RECOVERED
                            else result.started_at,
                            created_at=result.started_at,
                            deliveries=[AlertDelivery(channel_id=c.id) for c in monitor.channels],
                        )
                    )
            await session.commit()
        return True
