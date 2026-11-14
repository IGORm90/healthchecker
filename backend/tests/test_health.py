from httpx import AsyncClient


async def test_health_ok(client: AsyncClient) -> None:
    response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_health_reports_error_when_database_unavailable(
    client_without_database: AsyncClient,
) -> None:
    response = await client_without_database.get("/api/health")

    assert response.status_code == 503
    assert response.json() == {"status": "error"}
