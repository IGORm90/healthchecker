"""Защита от SSRF: монитор не должен ходить во внутренние сервисы.

Хост проверяется при сохранении монитора и перед каждой проверкой. Остаточный риск
DNS-rebinding между этой проверкой и соединением HTTP-клиента принят (план 0002, шаг 2).
"""

import asyncio
import socket
from ipaddress import IPv4Address, IPv6Address, ip_address
from urllib.parse import urlsplit


class ForbiddenTarget(Exception):
    """Адрес цели запрещён политикой SSRF; текст исключения — причина для пользователя."""


async def resolve_host(host: str) -> list[str]:
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    return [info[4][0] for info in infos]


def _forbidden_reason(address: IPv4Address | IPv6Address, *, allow_private: bool) -> str | None:
    if isinstance(address, IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    if address.is_loopback:
        return "loopback"
    if address.is_link_local:
        return "link-local"
    if address.is_unspecified:
        return "неопределённый адрес"
    if address.is_multicast:
        return "multicast"
    if address.is_private and not allow_private:
        return "приватная сеть"
    return None


async def ensure_target_allowed(url: str, *, allow_private: bool) -> None:
    """Бросает ForbiddenTarget, если хотя бы один адрес хоста запрещён.

    Имя, которое не резолвится, не считается запрещённым: проверка упадёт с ошибкой
    соединения, а у пользователя будет понятная причина.
    """
    host = urlsplit(url).hostname
    if not host:
        raise ForbiddenTarget("в URL нет хоста")

    try:
        addresses = [ip_address(host)]
    except ValueError:
        # Однокомпонентные имена — это localhost и сервисы Docker-сети вроде backend.
        if "." not in host.rstrip("."):
            raise ForbiddenTarget(f"адрес запрещён: {host} — внутреннее имя") from None
        try:
            addresses = [ip_address(a) for a in await resolve_host(host)]
        except socket.gaierror:
            return

    for address in addresses:
        reason = _forbidden_reason(address, allow_private=allow_private)
        if reason is not None:
            raise ForbiddenTarget(f"адрес запрещён: {host} → {address} ({reason})")
