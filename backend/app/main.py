import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from app.api import health, monitors
from app.db.session import SessionLocal, engine
from app.monitoring.runner import create_http_client
from app.monitoring.scheduler import Alert, Scheduler

logger = logging.getLogger(__name__)


async def notify(alert: Alert) -> None:
    # Заглушка до шага 4 плана 0002: отправка Оповещений в Telegram.
    logger.warning("Оповещение %s о мониторе %s", alert.kind, alert.monitor.id)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    async with create_http_client() as checks_http:
        scheduler = asyncio.create_task(Scheduler(SessionLocal, checks_http, notify).run())
        yield
        scheduler.cancel()
        with suppress(asyncio.CancelledError):
            await scheduler
    await engine.dispose()


app = FastAPI(title="Healthchecker", lifespan=lifespan)
app.include_router(health.router)
app.include_router(monitors.router)
