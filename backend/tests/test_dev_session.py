import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.auth.dev_session import NotDevBuild, UserBlocked, create_dev_session
from app.core.config import settings
from app.db.types import utcnow
from app.models import User, UserSession
from tests.conftest import SessionFactory, add_user


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def me(client: AsyncClient, token: str) -> dict[str, object]:
    response = await client.get("/api/auth/me", headers=bearer(token))
    assert response.status_code == 200, response.text
    return response.json()


async def test_session_for_new_user_signs_in_as_superadmin(
    anonymous_client: AsyncClient, session_factory: SessionFactory
) -> None:
    token = await create_dev_session(session_factory, 4242, superadmin=True)

    user = await me(anonymous_client, token)

    assert (user["telegram_id"], user["is_superadmin"]) == (4242, True)
    assert (
        await anonymous_client.get("/api/admin/users", headers=bearer(token))
    ).status_code == 200


async def test_session_for_existing_user_keeps_their_profile(
    anonymous_client: AsyncClient, session_factory: SessionFactory
) -> None:
    existing = await add_user(session_factory, 4242)

    token = await create_dev_session(session_factory, 4242, superadmin=False)

    user = await me(anonymous_client, token)
    assert (user["id"], user["name"], user["is_superadmin"]) == (
        existing.id,
        "User 4242",
        False,
    )


async def test_blocked_user_gets_no_session(session_factory: SessionFactory) -> None:
    await add_user(session_factory, 4242, blocked_at=utcnow())

    with pytest.raises(UserBlocked):
        await create_dev_session(session_factory, 4242, superadmin=True)


async def test_deployed_build_refuses_to_create_anything(
    session_factory: SessionFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    # В образе BUILD_ID — идентификатор сборки: команда не должна работать с прод-базой.
    monkeypatch.setattr(settings, "build_id", "3f2c9a1e")

    with pytest.raises(NotDevBuild):
        await create_dev_session(session_factory, 4242, superadmin=True)

    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(User)) == 0
        assert await session.scalar(select(func.count()).select_from(UserSession)) == 0
