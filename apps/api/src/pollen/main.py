"""FastAPI application.

Infrastructure only. Every feature arrives through ``components.registry``, so
this file changes when the platform changes — not when someone adds a component.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from ariadne.asgi import GraphQL
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from pollen.components.alerts.jobs.daily_alert import DAILY_ALERT_JOB
from pollen.container import build_container
from pollen.db import connect
from pollen.graphql_app import build_schema, format_error
from pollen.libs.kst import KST
from pollen.sign import SIGN_HTML

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


class Health(BaseModel):
    """Declared as a return type so FastAPI validates and documents it."""

    ok: bool
    service: str


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    container = build_container()
    client = await connect(container.settings.mongodb_uri)

    # MUST be a coroutine FUNCTION, not a lambda that returns a coroutine.
    # APScheduler inspects the callable: a lambda is not a coroutine function,
    # so it gets called, returns an un-awaited coroutine, and the job silently
    # does nothing — no error, no failed JobRun, just a scheduler that appears
    # to work. Verified: see tests/test_scheduler_wiring.py.
    async def run_daily_alert() -> None:
        await container.runner.run(DAILY_ALERT_JOB, container.daily_alert.execute)

    scheduler = AsyncIOScheduler(timezone=KST)
    scheduler.add_job(
        run_daily_alert,
        CronTrigger(hour=7, minute=0, timezone=KST),
        id=DAILY_ALERT_JOB,
        replace_existing=True,
    )
    scheduler.start()
    log.info("scheduler started — %s at 07:00 KST", DAILY_ALERT_JOB)

    app.state.container = container
    yield

    scheduler.shutdown(wait=False)
    await client.close()


def create_app() -> FastAPI:
    app = FastAPI(title="Pollen Today API", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    graphql_app = GraphQL(
        build_schema(),
        error_formatter=format_error,
        context_value=lambda request, _data: {
            "request": request,
            "container": request.app.state.container,
        },
    )
    app.mount("/graphql", graphql_app)

    @app.get("/api/health")
    async def health() -> Health:
        """Machine-readable. This is what the probe hits.

        Stays REST on purpose: uptime monitors and container probes speak HTTP
        status codes. A GraphQL health query returns 200 even when the resolver
        raises, which makes it useless as a liveness probe.
        """
        return Health(ok=True, service="pollen-today-api")

    @app.get("/", response_class=HTMLResponse)
    async def sign() -> str:
        return SIGN_HTML

    return app


app = create_app()
