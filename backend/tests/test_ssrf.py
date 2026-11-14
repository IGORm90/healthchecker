import socket

import pytest

from app.monitoring import ssrf
from app.monitoring.ssrf import ForbiddenTarget, ensure_target_allowed


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://[::1]/",
        "http://[::ffff:127.0.0.1]/",
        "http://169.254.169.254/latest/meta-data/",
        "http://0.0.0.0/",
        "http://224.0.0.1/",
        "http://localhost:8080/",
        "http://backend:8000/api/health",
    ],
)
async def test_always_forbidden(url: str) -> None:
    with pytest.raises(ForbiddenTarget):
        await ensure_target_allowed(url, allow_private=True)


@pytest.mark.parametrize(
    "url", ["http://10.0.0.5/", "http://172.16.1.1/", "http://192.168.1.1/", "http://[fd00::1]/"]
)
async def test_private_networks_depend_on_flag(url: str) -> None:
    with pytest.raises(ForbiddenTarget, match="приватная сеть"):
        await ensure_target_allowed(url, allow_private=False)

    await ensure_target_allowed(url, allow_private=True)


async def test_public_name_is_allowed() -> None:
    await ensure_target_allowed("https://example.com/", allow_private=False)


async def test_forbidden_if_any_resolved_address_is_forbidden(
    fake_dns: dict[str, list[str]],
) -> None:
    fake_dns["mixed.example.com"] = ["93.184.215.14", "127.0.0.1"]

    with pytest.raises(ForbiddenTarget, match="127.0.0.1"):
        await ensure_target_allowed("https://mixed.example.com/", allow_private=True)


async def test_name_resolving_to_metadata_address_is_forbidden(
    fake_dns: dict[str, list[str]],
) -> None:
    fake_dns["metadata.example.com"] = ["169.254.169.254"]

    with pytest.raises(ForbiddenTarget, match="link-local"):
        await ensure_target_allowed("http://metadata.example.com/", allow_private=True)


async def test_unresolvable_name_is_not_forbidden(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fail(host: str) -> list[str]:
        raise socket.gaierror(socket.EAI_NONAME, "Name or service not known")

    monkeypatch.setattr(ssrf, "resolve_host", fail)

    await ensure_target_allowed("https://no-such-host.example/", allow_private=False)
