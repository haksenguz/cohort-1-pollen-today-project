"""The local test schema must not be a smaller thing than production.

The suite used to build a reduced schema on SQLite: every table carrying a
JSONB column was left out, because SQLite could not compile JSONB. That was
never only a convenience. The privacy export and delete paths query exactly
those tables, so on SQLite they raised "no such table", their tests failed or
were skipped, and the code paths a user actually exercises with their data
were covered only by the Postgres run in CI.

CI being green did not make the gap harmless. It hid it. A local run is the
gate most of the work is done against, and a gate that skips the privacy
paths is a gate that cannot catch a bug in them.

These two tests pin the properties that closed the gap:

- the schema the fixture builds on SQLite holds every table the ORM declares;
- the JSON columns still render as JSONB on Postgres, because the ERD and the
  generated DDL say JSONB and a SQLite compatibility shim must not change what
  production runs.
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable
from sqlmodel import SQLModel

from app.models import Message, SymptomEvent


@pytest.mark.anyio
async def test_the_local_schema_holds_every_table_the_orm_declares() -> None:
    """Build the schema the way the fixture builds it and count the tables.

    The fixture creates the schema from SQLModel metadata, so "every table" is
    every table in that metadata. A subset is the bug this file exists for.
    """
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import StaticPool

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        created = set(await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names()))
    await engine.dispose()

    declared = set(SQLModel.metadata.tables)
    missing = sorted(declared - created)
    assert not missing, f"the local test schema is missing tables: {missing}"


def test_the_json_columns_still_render_as_jsonb_on_postgres() -> None:
    """The SQLite fallback must not change what production runs.

    `JSON().with_variant(JSONB, "postgresql")` is JSONB on Postgres and plain
    JSON on SQLite. If the variant is ever dropped or reversed, the deployed
    schema stops matching the ERD and the generated DDL, and nothing else in
    the suite would notice.
    """
    for table in (Message.__table__, SymptomEvent.__table__):
        ddl = str(CreateTable(table).compile(dialect=postgresql.dialect()))
        assert "JSONB" in ddl, f"{table.name} no longer renders JSONB on Postgres:\n{ddl}"


def test_the_json_columns_render_as_text_on_sqlite() -> None:
    """The other half of the variant, and the reason it exists."""
    for table in (Message.__table__, SymptomEvent.__table__):
        ddl = str(CreateTable(table).compile(dialect=postgresql.dialect()))
        assert "JSONB" in ddl

    from sqlalchemy.dialects import sqlite as sqlite_dialect

    for table in (Message.__table__, SymptomEvent.__table__):
        ddl = str(CreateTable(table).compile(dialect=sqlite_dialect.dialect()))
        assert "JSONB" not in ddl, f"{table.name} still asks SQLite for JSONB:\n{ddl}"
