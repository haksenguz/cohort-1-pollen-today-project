"""The migration history must produce the schema the app actually runs.

The trap this file exists for: `init_db()` calls
`SQLModel.metadata.create_all`, which creates a table that is missing and does
nothing to a table that already exists. So the *only* thing that can bring a
deployed database up to date is the migration history — and if the models have
drifted from it, the app writes columns the database does not have, in
production, while every test passes.

Tests build from SQLModel metadata. They never build from the migrations. That
is exactly why this drift survived for six weeks.

Three layers, cheapest first:

1. every model column appears somewhere in the migration history (static, runs
   on SQLite too);
2. every model CHECK constraint appears in the migration history (static);
3. the migrations are actually *run* against an empty scratch schema and the
   result compared to every model, column and constraint (Postgres only).

Layer 3 is the one that matters and the one that was missing. Comparing the
migration history to the models by reading the files proves only that the text
mentions the right names; it cannot tell you the migration fails to apply, or
that `create_table` never ran. Layer 3 applies them.
"""

import ast
import os
import re
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command
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

BACKEND = Path(__file__).resolve().parents[1]
VERSIONS = BACKEND / "alembic" / "versions"

ALL_MODELS = [
    User,
    UserAllergy,
    Conversation,
    Message,
    SymptomEvent,
    TriageResult,
    EnvironmentSnapshot,
    Alert,
    NotificationPreference,
    HospitalSearch,
    HospitalResult,
]

SCRATCH_SCHEMA = "migration_drift_scratch"


def _migration_files() -> list[Path]:
    return sorted(p for p in VERSIONS.glob("*.py") if p.name != "__init__.py")


def _columns_in_migrations() -> dict[str, set[str]]:
    """Every column the history creates, by table."""
    tables: dict[str, set[str]] = {}
    for path in _migration_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            op_name = getattr(node.func, "attr", None)

            if op_name == "create_table" and node.args:
                first = node.args[0]
                if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
                    continue
                cols = tables.setdefault(first.value, set())
                for arg in node.args[1:]:
                    if (
                        isinstance(arg, ast.Call)
                        and getattr(arg.func, "attr", None) == "Column"
                        and arg.args
                        and isinstance(arg.args[0], ast.Constant)
                    ):
                        cols.add(str(arg.args[0].value))

            elif op_name == "add_column" and len(node.args) >= 2:
                table, column = node.args[0], node.args[1]
                if isinstance(table, ast.Constant) and isinstance(column, ast.Call):
                    col_arg = column.args[0] if column.args else None
                    if isinstance(col_arg, ast.Constant):
                        tables.setdefault(str(table.value), set()).add(str(col_arg.value))
    return tables


def _constraint_names_in_migrations() -> set[str]:
    """Names passed to op.create_check_constraint / op.create_unique_constraint."""
    names: set[str] = set()
    for path in _migration_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            op_name = getattr(node.func, "attr", None)
            if op_name not in ("create_check_constraint", "create_unique_constraint"):
                continue
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    names.add(arg.value)
    return names


@pytest.mark.parametrize("model", ALL_MODELS, ids=lambda m: m.__tablename__)
def test_every_model_column_exists_in_the_migration_history(model) -> None:
    """A model column with no migration is a production-only crash."""
    in_migrations = _columns_in_migrations().get(model.__tablename__, set())
    model_columns = {c.name for c in model.__table__.columns}
    missing = sorted(model_columns - in_migrations)

    assert not missing, (
        f"{model.__tablename__} has columns the migrations never create: {missing}. "
        "create_all does not alter existing tables, so a deployed database will "
        "not have them and the app will fail on first write."
    )


def test_every_model_check_constraint_exists_in_the_migration_history() -> None:
    """A CHECK in `__table_args__` that no migration creates is not enforced in prod.

    This is the quieter half of the same bug: the two constraints on `messages`
    were declared on the model and in the generated SQL, and in no migration, so
    a database built the documented way enforced neither.
    """
    in_migrations = _constraint_names_in_migrations()
    declared: set[str] = set()
    for model in ALL_MODELS:
        for constraint in model.__table__.constraints:
            name = getattr(constraint, "name", None)
            if name:
                declared.add(name)

    missing = sorted(n for n in declared if n.endswith("_check") and n not in in_migrations)
    assert not missing, (
        f"CHECK constraints declared on a model but created by no migration: {missing}. "
        "They hold in tests and in generated SQL, and nowhere else."
    )


def test_the_migration_graph_has_a_single_head() -> None:
    """Two heads means `alembic upgrade head` is ambiguous and does nothing."""
    revisions: dict[str, str | None] = {}
    for path in _migration_files():
        source = path.read_text(encoding="utf-8")
        rev = re.search(r"^revision: str = '([^']+)'", source, re.M)
        down = re.search(r"^down_revision:.*= (.+)$", source, re.M)
        if rev:
            revisions[rev.group(1)] = (
                down.group(1).strip().strip("'\"") if down and "None" not in down.group(1) else None
            )

    assert len(revisions) >= 2, "expected the initial schema plus at least one follow-up"
    parents = [p for p in revisions.values() if p]
    assert len(parents) == len(set(parents)), (
        f"more than one revision revises the same parent: {parents}"
    )
    assert None in revisions.values(), "no revision is a head; the graph is a cycle"


def _alembic_config() -> Config:
    return Config(str(BACKEND / "alembic.ini"))


@pytest.mark.asyncio
async def test_applying_the_migrations_reproduces_the_model_schema() -> None:
    """Run every migration against an empty schema and diff against the models.

    Postgres only: the migrations use JSONB and real CHECK constraints, neither of
    which SQLite compiles. Isolated in its own schema, because the suite's
    fixture builds `public` from SQLModel metadata — inspecting that would only
    compare the models with themselves, which is the mistake this test replaces.
    """
    url = os.environ.get("TEST_DATABASE_URL", "")
    if not url.startswith("postgresql"):
        pytest.skip("needs real Postgres: the migrations use JSONB and CHECK constraints")

    engine = create_async_engine(url, future=True)
    try:
        async with engine.connect() as conn:
            await conn.execution_options(isolation_level="AUTOCOMMIT")
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{SCRATCH_SCHEMA}" CASCADE'))
            await conn.execute(text(f'CREATE SCHEMA "{SCRATCH_SCHEMA}"'))

        async with engine.connect() as conn:
            await conn.execute(text(f'SET search_path TO "{SCRATCH_SCHEMA}"'))

            def _apply_and_inspect(sync_conn):
                config = _alembic_config()
                config.attributes["connection"] = sync_conn
                command.upgrade(config, "head")

                inspector = inspect(sync_conn)
                tables = set(inspector.get_table_names())
                return {
                    model.__tablename__: {
                        "present": model.__tablename__ in tables,
                        "cols": {c["name"] for c in inspector.get_columns(model.__tablename__)}
                        if model.__tablename__ in tables
                        else set(),
                        "checks": {
                            f"{ck.get('name')} {ck.get('sqltext')}"
                            for ck in inspector.get_check_constraints(model.__tablename__)
                        }
                        if model.__tablename__ in tables
                        else set(),
                    }
                    for model in ALL_MODELS
                }

            migrated = await conn.run_sync(_apply_and_inspect)

        problems: list[str] = []
        for model in ALL_MODELS:
            name = model.__tablename__
            got = migrated[name]
            if not got["present"]:
                problems.append(f"{name}: migration never created this table")
                continue

            expected = {c.name for c in model.__table__.columns}
            if missing := sorted(expected - got["cols"]):
                problems.append(f"{name}: migration did not create columns {missing}")

            for constraint in model.__table__.constraints:
                cname = getattr(constraint, "name", None)
                if cname and cname.endswith("_check"):
                    if not any(cname in text for text in got["checks"]):
                        problems.append(f"{name}: migration did not create {cname}")

        assert not problems, (
            "the migrations do not produce the schema the models describe:\n  - "
            + "\n  - ".join(problems)
        )
    finally:
        async with engine.connect() as conn:
            await conn.execution_options(isolation_level="AUTOCOMMIT")
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{SCRATCH_SCHEMA}" CASCADE'))
        await engine.dispose()
