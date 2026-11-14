"""Выполнение одной Проверки монитора."""

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime

import httpx

from app.core.config import settings
from app.db.types import utcnow
from app.models import Monitor
from app.monitoring.expectation import Expectation, evaluate
from app.monitoring.ssrf import ForbiddenTarget, ensure_target_allowed

TIMEOUT_SECONDS = 10
# Больше не читаем: подстрока ищется в начале тела, а память контейнера ограничена.
MAX_BODY_BYTES = 1024 * 1024


@dataclass(frozen=True)
class CheckResult:
    started_at: datetime
    duration_ms: int
    status_code: int | None
    success: bool
    failure_reason: str | None


def create_http_client() -> httpx.AsyncClient:
    # Редиректам не следуем: иначе через них можно обойти SSRF-фильтр.
    return httpx.AsyncClient(timeout=TIMEOUT_SECONDS, follow_redirects=False, verify=True)


async def _read_prefix(response: httpx.Response) -> bytes:
    prefix = bytearray()
    async for chunk in response.aiter_bytes():
        prefix += chunk
        if len(prefix) >= MAX_BODY_BYTES:
            break
    return bytes(prefix[:MAX_BODY_BYTES])


async def run_check(client: httpx.AsyncClient, monitor: Monitor) -> CheckResult:
    started_at = utcnow()
    started = time.monotonic()
    status_code: int | None = None

    try:
        # Таймаут httpx действует на каждую фазу отдельно; ограничиваем Проверку целиком,
        # включая DNS в SSRF-фильтре, чтобы медленный ответ не растянул её на минуты.
        async with asyncio.timeout(TIMEOUT_SECONDS):
            await ensure_target_allowed(monitor.url, allow_private=settings.allow_private_targets)
            async with client.stream(
                monitor.method,
                monitor.url,
                headers=[(name, value) for name, value in monitor.headers],
                content=monitor.body,
            ) as response:
                status_code = response.status_code
                body_prefix = await _read_prefix(response)
        failure_reason = evaluate(
            Expectation(status=monitor.expected_status, body=monitor.expected_body),
            status_code,
            body_prefix,
        )
    except ForbiddenTarget as exc:
        failure_reason = str(exc)
    except TimeoutError, httpx.TimeoutException:
        failure_reason = f"таймаут {TIMEOUT_SECONDS} с"
    except httpx.HTTPError as exc:
        failure_reason = f"ошибка соединения: {exc or type(exc).__name__}"

    return CheckResult(
        started_at=started_at,
        duration_ms=round((time.monotonic() - started) * 1000),
        status_code=status_code,
        success=failure_reason is None,
        failure_reason=failure_reason,
    )
