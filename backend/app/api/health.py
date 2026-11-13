from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session

router = APIRouter(prefix="/api")


@router.get("/health")
async def health(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    """Liveness сервиса: API отвечает и база доступна."""
    try:
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "error"}
    return {"status": "ok"}
