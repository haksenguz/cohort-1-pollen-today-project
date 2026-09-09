import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    allergies,
    auth,
    chat,
    environment,
    health,
    hospitals,
    notifications,
    triage,
    users,
)
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


def _scheduler_disabled() -> bool:
    # Never let the background scheduler fire during tests, no matter how
    # the test suite drives the app's lifespan.
    return os.environ.get("PYTEST_CURRENT_TEST") is not None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Tables are created by db/init/01_schema.sql in docker; init_db() is a
    # convenience for local runs without the SQL init. Import lazily so the app
    # still imports when no database is reachable (e.g. unit tests). Any
    # failure here (unreachable DB, bad creds, ...) is non-fatal by design.
    try:
        from app.core.db import init_db

        await init_db()
    except Exception:  # dev convenience only, must never block startup
        logger.warning("init_db() skipped: could not initialize database", exc_info=True)

    # Same non-fatal spirit for the notification scheduler: a broken
    # scheduler must never stop the API from serving requests.
    scheduler = None
    if not _scheduler_disabled():
        try:
            from app.services.notification_service import start_scheduler

            scheduler = start_scheduler()
        except Exception:
            logger.warning("notification scheduler failed to start", exc_info=True)

    yield

    if scheduler is not None:
        try:
            scheduler.shutdown(wait=False)
        except Exception:
            logger.warning("notification scheduler failed to shut down cleanly", exc_info=True)


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(environment.router)
app.include_router(triage.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(allergies.router)
app.include_router(chat.router)
app.include_router(hospitals.router)
app.include_router(notifications.router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": settings.app_name, "docs": "/docs"}
