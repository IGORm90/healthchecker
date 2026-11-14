from datetime import datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.errors import validation_error
from app.auth.deps import Auth, CurrentUser
from app.core.config import settings
from app.db.session import get_session
from app.db.types import utcnow
from app.models import Check, Monitor, MonitorState, NotificationChannel
from app.monitoring.ssrf import ForbiddenTarget, ensure_target_allowed
from app.schemas.monitors import CheckOut, Header, MonitorIn, MonitorOut

router = APIRouter(prefix="/api/monitors", tags=["monitors"])

Session = Annotated[AsyncSession, Depends(get_session)]

# Поля, правка которых меняет смысл проверки: прежнее состояние монитора к ней не относится.
CHECK_DEFINING_FIELDS = ("url", "method", "headers", "body", "expected_status", "expected_body")

_last_check_at = (
    select(func.max(Check.started_at))
    .where(Check.monitor_id == Monitor.id)
    .correlate(Monitor)
    .scalar_subquery()
)


def _to_out(monitor: Monitor, last_check_at: datetime | None) -> MonitorOut:
    return MonitorOut(
        id=monitor.id,
        user_id=monitor.user_id,
        name=monitor.name,
        url=monitor.url,
        method=monitor.method,
        headers=[Header(name=n, value=v) for n, v in monitor.headers],
        body=monitor.body,
        expected_status=monitor.expected_status,
        expected_body=monitor.expected_body,
        interval_seconds=monitor.interval_seconds,
        channel_ids=sorted(c.id for c in monitor.channels),
        state=monitor.state,
        state_changed_at=monitor.state_changed_at,
        next_check_at=monitor.next_check_at,
        last_check_at=last_check_at,
    )


async def _get_monitor(
    session: AsyncSession, monitor_id: int, current: CurrentUser, *, owner_only: bool
) -> Monitor:
    """Монитор, доступный текущему Пользователю.

    owner_only — правка и удаление: только владельцу. Иначе — владельцу или Суперадмину.
    Чужой монитор неотличим от несуществующего.
    """
    monitor = await session.get(Monitor, monitor_id, options=[selectinload(Monitor.channels)])
    allowed = monitor is not None and (
        monitor.user_id == current.id if owner_only else current.can_manage(monitor.user_id)
    )
    if not allowed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Монитор не найден")
    return monitor


async def _monitor_out(session: AsyncSession, monitor: Monitor) -> MonitorOut:
    last_check_at = await session.scalar(
        select(func.max(Check.started_at)).where(Check.monitor_id == monitor.id)
    )
    return _to_out(monitor, last_check_at)


async def _validated_fields(session: AsyncSession, data: MonitorIn, user_id: int) -> dict[str, Any]:
    """Поля модели из запроса после проверок, которым нужны БД и DNS."""
    url = str(data.url)
    try:
        await ensure_target_allowed(url, allow_private=settings.allow_private_targets)
    except ForbiddenTarget as exc:
        raise validation_error("url", str(exc), "forbidden_target") from exc

    channels = list(
        await session.scalars(
            select(NotificationChannel).where(
                NotificationChannel.id.in_(data.channel_ids),
                NotificationChannel.user_id == user_id,
            )
        )
    )
    missing = set(data.channel_ids) - {c.id for c in channels}
    if missing:
        ids = ", ".join(map(str, sorted(missing)))
        raise validation_error(
            "channel_ids", f"Каналы оповещения не найдены: {ids}", "unknown_channel"
        )

    return {
        "name": data.name,
        "url": url,
        "method": data.method,
        "headers": [[h.name, h.value] for h in data.headers],
        "body": data.body,
        "expected_status": data.expected_status,
        "expected_body": data.expected_body,
        "interval_seconds": int(data.interval_seconds),
        "channels": channels,
    }


@router.get("")
async def list_monitors(current: Auth, session: Session) -> list[MonitorOut]:
    return await user_monitors(session, current.id)


async def user_monitors(session: AsyncSession, user_id: int) -> list[MonitorOut]:
    rows = await session.execute(
        select(Monitor, _last_check_at)
        .where(Monitor.user_id == user_id)
        .options(selectinload(Monitor.channels))
        .order_by(Monitor.name, Monitor.id)
    )
    return [_to_out(monitor, last_check_at) for monitor, last_check_at in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_monitor(data: MonitorIn, current: Auth, session: Session) -> MonitorOut:
    now = utcnow()
    monitor = Monitor(
        **await _validated_fields(session, data, current.id),
        user_id=current.id,
        state=MonitorState.UNKNOWN,
        state_changed_at=now,
        next_check_at=now,
    )
    session.add(monitor)
    await session.commit()
    return _to_out(monitor, None)


@router.get("/{monitor_id}")
async def get_monitor(monitor_id: int, current: Auth, session: Session) -> MonitorOut:
    monitor = await _get_monitor(session, monitor_id, current, owner_only=False)
    return await _monitor_out(session, monitor)


@router.put("/{monitor_id}")
async def update_monitor(
    monitor_id: int, data: MonitorIn, current: Auth, session: Session
) -> MonitorOut:
    monitor = await _get_monitor(session, monitor_id, current, owner_only=True)
    fields = await _validated_fields(session, data, current.id)
    now = utcnow()

    redefined = any(getattr(monitor, f) != fields[f] for f in CHECK_DEFINING_FIELDS)
    interval_changed = monitor.interval_seconds != fields["interval_seconds"]
    for name, value in fields.items():
        setattr(monitor, name, value)

    if monitor.state != MonitorState.PAUSED:
        if redefined:
            monitor.state = MonitorState.UNKNOWN
            monitor.state_changed_at = now
            monitor.next_check_at = now
        elif interval_changed and monitor.next_check_at is not None:
            # Не ждать до часа ради старого интервала, если новый короче.
            monitor.next_check_at = min(
                monitor.next_check_at, now + timedelta(seconds=monitor.interval_seconds)
            )

    await session.commit()
    return await _monitor_out(session, monitor)


@router.delete("/{monitor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_monitor(monitor_id: int, current: Auth, session: Session) -> None:
    monitor = await _get_monitor(session, monitor_id, current, owner_only=True)
    await session.delete(monitor)
    await session.commit()


@router.post("/{monitor_id}/pause")
async def pause_monitor(monitor_id: int, current: Auth, session: Session) -> MonitorOut:
    monitor = await _get_monitor(session, monitor_id, current, owner_only=False)
    if monitor.state != MonitorState.PAUSED:
        monitor.state = MonitorState.PAUSED
        monitor.state_changed_at = utcnow()
        monitor.next_check_at = None
        await session.commit()
    return await _monitor_out(session, monitor)


@router.post("/{monitor_id}/resume")
async def resume_monitor(monitor_id: int, current: Auth, session: Session) -> MonitorOut:
    monitor = await _get_monitor(session, monitor_id, current, owner_only=False)
    if monitor.state == MonitorState.PAUSED:
        now = utcnow()
        monitor.state = MonitorState.UNKNOWN
        monitor.state_changed_at = now
        monitor.next_check_at = now
        await session.commit()
    return await _monitor_out(session, monitor)


@router.get("/{monitor_id}/checks")
async def list_checks(
    monitor_id: int,
    current: Auth,
    session: Session,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> list[CheckOut]:
    await _get_monitor(session, monitor_id, current, owner_only=False)
    checks = await session.scalars(
        select(Check)
        .where(Check.monitor_id == monitor_id)
        .order_by(Check.started_at.desc(), Check.id.desc())
        .limit(limit)
    )
    return [CheckOut.model_validate(c) for c in checks]
