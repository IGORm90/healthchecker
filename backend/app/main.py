import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

import httpx
from fastapi import FastAPI

from app.api import channels, health, monitors, telegram
from app.db.session import SessionLocal, engine
from app.monitoring.retention import run_retention
from app.monitoring.runner import create_http_client
from app.monitoring.scheduler import Alert, Scheduler
from app.notifications.alerts import send_alert
from app.notifications.telegram import TelegramClient


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Клиенты разные: мониторы не следуют редиректам и проходят SSRF-фильтр,
    # а Telegram — доверенный адрес.
    async with create_http_client() as checks_http, httpx.AsyncClient() as telegram_http:
        app.state.telegram = TelegramClient(telegram_http)

        async def notify(alert: Alert) -> None:
            await send_alert(SessionLocal, app.state.telegram, alert)

        tasks = [
            asyncio.create_task(Scheduler(SessionLocal, checks_http, notify).run()),
            asyncio.create_task(run_retention(SessionLocal)),
        ]
        yield
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task
    await engine.dispose()


app = FastAPI(title="Healthchecker", lifespan=lifespan)
app.include_router(health.router)
app.include_router(monitors.router)
app.include_router(telegram.router)
app.include_router(channels.router)
