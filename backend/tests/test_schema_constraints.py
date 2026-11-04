"""The messages CHECK constraints must agree across schema, migration and code.

Two columns that feed safety-critical rendering were free text: `messages.role`
and `messages.triage_level`. Both are now constrained, and the constraint only
works if the values match what the code actually writes.

The trap this file exists to prevent: the API contract for `role` is lowercase,
so the obvious constraint (`role IN ('user','assistant')`) aborts on the first
row of a real database, because every row the enum produces is UPPERCASE.
Postgres validates existing rows when ADD CONSTRAINT runs, so that mistake only
shows up against live data, never in a fresh test database.

Keeping the three artifacts in step is manual, so these assertions stand in for
the review that would otherwise catch the drift.
"""

import os
from collections.abc import AsyncGenerator
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import CheckConstraint, MetaData
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.models import Conversation, Message, User

BACKEND = Path(__file__).resolve().parents[1]
SCHEMA_SQL = BACKEND / "db" / "init" / "01_schema.sql"
MIGRATIONS = BACKEND / "db" / "migrations"
CONSTRAINT_MIGRATION = MIGRATIONS / "03_constrain_message_role_and_triage_level.sql"

# What the code actually writes. app/core/enums.py:
#   MessageRole  = USER | ASSISTANT | SYSTEM
#   TriageLevel  = LOW | MODERATE | EMERGENCY
WRITABLE_ROLES = {"USER", "ASSISTANT"}
WRITABLE_TRIAGE_LEVELS = {"LOW", "MODERATE", "EMERGENCY"}


async def _seed_conversation(session) -> int:
    user = User(email=f"constraint-{uuid4().hex[:10]}@example.com", password_hash="x")  # noqa: S106
    session.add(user)
    await session.commit()
    await session.refresh(user)

    conversation = Conversation(user_id=user.id, status="ACTIVE")
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    return conversation.id


def _sqlite_metadata() -> MetaData:
    """users/conversations/messages, as the models declare them.

    The JSON columns are JSONB on Postgres and plain JSON on SQLite, so both
    dialects compile the real table definitions, constraints included.
    """
    metadata = MetaData()
    for table in (User.__table__, Conversation.__table__, Message.__table__):
        table.to_metadata(metadata)
    return metadata


@pytest_asyncio.fixture
async def message_session() -> AsyncGenerator[AsyncSession, None]:
    url = os.environ.get("TEST_DATABASE_URL", "")
    is_postgres = url.startswith("postgresql")
    engine = (
        create_async_engine(url, future=True)
        if is_postgres
        else create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    )
    async with engine.begin() as conn:
        await conn.run_sync(
            (lambda c: User.metadata.create_all(c))
            if is_postgres
            else _sqlite_metadata().create_all
        )

    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


def test_migration_file_exists() -> None:
    assert CONSTRAINT_MIGRATION.is_file(), (
        "the constraint migration is missing; without it an existing database "
        "stays unconstrained while a fresh one is guarded"
    )


@pytest.mark.parametrize(
    "path",
    [SCHEMA_SQL, CONSTRAINT_MIGRATION],
    ids=["01_schema.sql", "03_migration"],
)
def test_role_constraint_is_uppercase_and_excludes_system(path: Path) -> None:
    """Lowercase here is not a style choice, it is a migration that aborts."""
    text = path.read_text(encoding="utf-8")

    assert "messages_role_check" in text, f"{path.name} never creates messages_role_check"

    for role in WRITABLE_ROLES:
        assert f"'{role}'" in text, f"{path.name} must allow {role!r}, which chat.py writes"

    for written in WRITABLE_ROLES:
        assert f"'{written.lower()}'" not in text, (
            f"{path.name} constrains role with the lowercase API spelling; every "
            "real row is uppercase and ADD CONSTRAINT would abort"
        )

    assert "'SYSTEM'" not in text, (
        "SYSTEM must stay out of the constraint: nothing writes it and the "
        "frontend union has no 'system', so it would render with no safety banner"
    )


@pytest.mark.parametrize(
    "path",
    [SCHEMA_SQL, CONSTRAINT_MIGRATION],
    ids=["01_schema.sql", "03_migration"],
)
def test_triage_level_constraint_matches_the_enum(path: Path) -> None:
    text = path.read_text(encoding="utf-8")

    assert "messages_triage_level_check" in text, (
        f"{path.name} never creates messages_triage_level_check"
    )

    for level in WRITABLE_TRIAGE_LEVELS:
        assert f"'{level}'" in text, f"{path.name} must allow {level!r}, which triage.py emits"

    assert "IS NULL" in text, (
        f"{path.name} must let triage_level stay NULL; a turn that asked a "
        "follow-up question has no verdict to store"
    )


# ---------------------------------------------------------------------------
# created_at gets a default; updated_at deliberately does not.
# ---------------------------------------------------------------------------

CREATED_AT_MIGRATION = MIGRATIONS / "04_created_at_defaults.sql"


def test_created_at_default_migration_exists() -> None:
    assert CREATED_AT_MIGRATION.is_file(), (
        "gen_dmm.py emits DEFAULT now() for created_at but the live database "
        "never got it, so production and a fresh install are different shapes"
    )


def test_created_at_migration_does_not_touch_updated_at() -> None:
    """The trap, pinned so it cannot be undone by a well-meaning edit.

    `created_at` is written once at INSERT, so a default is simply correct.
    `updated_at` is not: a default is written at INSERT and then never moves,
    because there is no trigger. Every subsequent UPDATE would leave the row
    carrying a stale timestamp that is still NOT NULL, still plausible, and
    still passes every check that exists. Nothing errors - the column would
    look maintained and would not be.

    That is not hypothetical: conversation_service.list_conversations orders
    the history list by conversations.updated_at, so a stale value puts the
    list in the wrong order and produces no error anywhere.
    """
    text = CREATED_AT_MIGRATION.read_text(encoding="utf-8")

    assert "created_at" in text, "the migration must still set the created_at default"

    # The column may be named in prose explaining the decision, but it must
    # never appear in a statement that alters it.
    for statement in text.split(";"):
        if "updated_at" in statement and "ALTER" in statement.upper():
            pytest.fail(
                "04 must never ALTER updated_at. Either add a BEFORE UPDATE "
                "trigger so the column maintains itself, or keep the value "
                "explicit and correct gen_dmm.py - never a default that lies."
            )


# ---------------------------------------------------------------------------
# The model and the generator declare the same constraint.
# ---------------------------------------------------------------------------


def _declared_checks() -> dict[str, str]:
    return {
        c.name: str(c.sqltext)
        for c in Message.__table__.constraints
        if isinstance(c, CheckConstraint)
    }


def test_model_declares_the_constraints_too() -> None:
    """Not only the generated SQL.

    The test schema is built from SQLModel metadata and CI never applies
    db/migrations/*.sql, so a constraint living only in `01_schema.sql` exists in
    production and in no test database - while the assertions above, which read
    file text, would still pass. Declaring it on the model is what makes it
    real everywhere.
    """
    declared = _declared_checks()

    assert declared, (
        "Message declares no CheckConstraint, so create_all builds a messages "
        "table with no constraint at all and every test database is unguarded"
    )

    role = declared["messages_role_check"]
    for value in WRITABLE_ROLES:
        assert f"'{value}'" in role
    assert "'SYSTEM'" not in role
    assert "'user'" not in role, "the lowercase spelling rejects every real row"

    triage = declared["messages_triage_level_check"]
    for level in WRITABLE_TRIAGE_LEVELS:
        assert f"'{level}'" in triage
    assert "IS NULL" in triage


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_role", ["user", "User", "SYSTEM", "assistant"])
async def test_the_model_constraint_rejects_a_bad_role_for_real(
    message_session, bad_role: str
) -> None:
    """Behaviour, not file content: write a row the application would never write.

    Runs on both engines. The JSON columns compile on SQLite as well as on
    Postgres, and SQLite enforces CHECK, so this is real coverage locally as
    well as on the Postgres 17 service in CI.
    """
    conversation_id = await _seed_conversation(message_session)

    with pytest.raises(IntegrityError):
        message_session.add(Message(conversation_id=conversation_id, role=bad_role, content="hi"))
        await message_session.commit()
    await message_session.rollback()


@pytest.mark.asyncio
@pytest.mark.parametrize("good_role", sorted(WRITABLE_ROLES))
async def test_the_model_constraint_accepts_what_the_app_writes(
    message_session, good_role: str
) -> None:
    """A constraint that rejected everything would pass the test above too."""
    conversation_id = await _seed_conversation(message_session)

    message_session.add(Message(conversation_id=conversation_id, role=good_role, content="hi"))
    await message_session.commit()
    await message_session.rollback()
