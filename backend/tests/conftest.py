"""Shared test fixtures.

Default: an in-memory SQLite DB standing in for Postgres. Set
``TEST_DATABASE_URL`` (any ``postgresql+...`` URL) to run the same suite
against a real Postgres, the way CI does. This is the only way to catch
dialect-specific bugs like the TIMESTAMPTZ one that reached ``main``.

Only the tables auth/users/allergies/notifications touch are created on
SQLite — ``symptom_events`` uses a Postgres-only JSONB column that
SQLite's dialect can't compile, and this suite has no business creating
tables outside its own scope.
"""

import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

from app.core.db import get_session
from app.main import app
from app.models import (
    Alert,
    Conversation,
    EnvironmentSnapshot,
    HospitalResult,
    HospitalSearch,
    Message,
    NotificationPreference,
    SymptomEvent,
    TriageResult,
    User,
    UserAllergy,
)

# Full table list in FK-safe delete order: children first, then parents.
# This list is *tested* by tests/test_conftest_wipe_order.py — if you
# add a new FK, run the test suite against Postgres (`TEST_DATABASE_URL`)
# to see the order violation before the gate does.
_ALL_TABLES = [
    # children with their own children
    TriageResult.__table__,  # -> symptom_events
    # children of Conversation
    Message.__table__,  # -> conversations
    SymptomEvent.__table__,  # -> conversations
    Conversation.__table__,  # -> users
    # children of HospitalSearch
    HospitalResult.__table__,  # -> hospital_searches
    HospitalSearch.__table__,  # -> users
    # children of User (no grandchildren)
    Alert.__table__,  # -> users, environment_snapshots
    UserAllergy.__table__,  # -> users
    NotificationPreference.__table__,  # -> users
    # independent
    EnvironmentSnapshot.__table__,
    # parents last
    User.__table__,
]

# Tables the SQLite in-memory engine can compile (no JSONB).
_SQLITE_TABLES = [
    User.__table__,
    UserAllergy.__table__,
    EnvironmentSnapshot.__table__,
    Alert.__table__,
    NotificationPreference.__table__,
]


def _is_postgres(url: str) -> bool:
    return url.startswith("postgresql")


def _build_test_engine():
    url = os.environ.get("TEST_DATABASE_URL", "")
    if _is_postgres(url):
        return create_async_engine(url, future=True)
    return create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


@pytest_asyncio.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    engine = _build_test_engine()
    tables = None if _is_postgres(str(engine.url)) else _SQLITE_TABLES
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: SQLModel.metadata.create_all(sync_conn, tables=tables)
        )

    # Postgres tests share a real DB across cases, so wipe before each
    # test to start from a known state. SQLite in-memory starts fresh.
    if _is_postgres(str(engine.url)):
        async with engine.begin() as conn:
            for tbl in _ALL_TABLES:
                await conn.execute(tbl.delete())

    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


@pytest_asyncio.fixture
async def client(session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def _get_session_override() -> AsyncGenerator[AsyncSession, None]:
        yield session

    app.dependency_overrides[get_session] = _get_session_override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
def registered_user_payload() -> dict:
    return {"email": "a@example.com", "password": "correcthorse123"}
