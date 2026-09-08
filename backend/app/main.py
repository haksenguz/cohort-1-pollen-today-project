import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import allergies, auth, environment, health, triage, users
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


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
    yield


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


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": settings.app_name, "docs": "/docs"}
