from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import health
from app.db.session import engine


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Здесь появится фоновый исполнитель проверок.
    yield
    await engine.dispose()


app = FastAPI(title="Healthchecker", lifespan=lifespan)
app.include_router(health.router)
