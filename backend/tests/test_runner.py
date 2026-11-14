import asyncio
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx
import pytest

from app.models import HttpMethod, Monitor
from app.monitoring import runner
from app.monitoring.runner import run_check

Handler = Callable[[httpx.Request], httpx.Response]


def make_monitor(**overrides: Any) -> Monitor:
    fields: dict[str, Any] = {
        "name": "Example",
        "url": "https://example.com/health",
        "method": HttpMethod.GET,
        "headers": [],
        "body": None,
        "expected_status": 200,
        "expected_body": None,
    }
    return Monitor(**(fields | overrides))


def client(handler: Handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False)


async def test_expected_response_is_success() -> None:
    async with client(lambda _: httpx.Response(200, text="ok")) as http:
        result = await run_check(http, make_monitor())

    assert result.success is True
    assert result.status_code == 200
    assert result.failure_reason is None
    assert result.duration_ms >= 0


async def test_unexpected_status_fails_with_reason() -> None:
    async with client(lambda _: httpx.Response(503)) as http:
        result = await run_check(http, make_monitor())

    assert (result.success, result.status_code) == (False, 503)
    assert result.failure_reason == "ожидался 200, получен 503"


async def test_body_without_expected_substring_fails() -> None:
    async with client(lambda _: httpx.Response(200, text="maintenance")) as http:
        result = await run_check(http, make_monitor(expected_body="ok"))

    assert result.success is False
    assert result.failure_reason == "тело не содержит «ok»"


async def test_redirect_is_not_followed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/health", "редирект не должен выполняться"
        return httpx.Response(301, headers={"Location": "https://example.com/other"})

    async with client(handler) as http:
        result = await run_check(http, make_monitor())

    assert result.status_code == 301
    assert result.failure_reason == "ожидался 200, получен 301"


async def test_timeout_fails_without_status_code() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    async with client(handler) as http:
        result = await run_check(http, make_monitor())

    assert (result.success, result.status_code) == (False, None)
    assert result.failure_reason == "таймаут 10 с"


async def test_connection_error_fails_with_reason() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    async with client(handler) as http:
        result = await run_check(http, make_monitor())

    assert result.failure_reason == "ошибка соединения: connection refused"


async def test_request_uses_monitor_method_headers_and_body() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200)

    monitor = make_monitor(
        method=HttpMethod.POST, headers=[["X-Token", "secret"]], body='{"ping": 1}'
    )
    async with client(handler) as http:
        await run_check(http, monitor)

    [request] = seen
    assert request.method == "POST"
    assert request.headers["X-Token"] == "secret"
    assert request.content == b'{"ping": 1}'


async def test_forbidden_target_fails_without_request(fake_dns: dict[str, list[str]]) -> None:
    fake_dns["internal.example.com"] = ["10.0.0.5"]

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("запрос к запрещённому адресу")

    async with client(handler) as http:
        result = await run_check(http, make_monitor(url="https://internal.example.com/"))

    assert result.success is False
    assert result.failure_reason is not None
    assert result.failure_reason.startswith("адрес запрещён: internal.example.com")


async def test_timeout_covers_the_whole_check(monkeypatch: pytest.MonkeyPatch) -> None:
    # Каждая фаза укладывается в таймаут httpx, но Проверка целиком — нет.
    monkeypatch.setattr(runner, "TIMEOUT_SECONDS", 0.05)

    async def slow_body() -> AsyncIterator[bytes]:
        for _ in range(10):
            await asyncio.sleep(0.02)
            yield b"."

    async with client(lambda _: httpx.Response(200, content=slow_body())) as http:
        result = await run_check(http, make_monitor())

    assert result.success is False
    assert result.failure_reason == "таймаут 0.05 с"
