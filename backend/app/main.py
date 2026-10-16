import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    allergies,
    auth,
    chat,
    conversations,
    dev_settings,
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


def _scrub(value: Any) -> Any:
    """Strip submitted values out of a validation error.

    FastAPI echoes the offending input back in `input` and sometimes in `ctx`.
    For the dev-settings route that input *is* the API key, so the default 422
    would hand the secret straight back to whoever posted it — bypassing the
    404 that hides the route everywhere the flag is off.
    """
    if isinstance(value, dict):
        return {
            k: ("<redacted>" if k in ("input", "api_key") else _scrub(v)) for k, v in value.items()
        }
    if isinstance(value, list):
        return [_scrub(v) for v in value]
    return "<redacted>"


@app.exception_handler(RequestValidationError)
async def redact_validation_errors(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "detail": [
                {"type": e.get("type"), "loc": e.get("loc"), "msg": e.get("msg")}
                for e in exc.errors()
            ]
        },
    )


app.include_router(health.router)
app.include_router(environment.router)
app.include_router(triage.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(allergies.router)
app.include_router(chat.router)
app.include_router(conversations.router)
app.include_router(hospitals.router)
app.include_router(notifications.router)

# Dark by default: registering this router is harmless while the flag is off,
# because every route 404s until `dev_settings_enabled` is true — which only
# ever happens in a gitignored local .env.
app.include_router(dev_settings.router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": settings.app_name, "docs": "/docs"}
