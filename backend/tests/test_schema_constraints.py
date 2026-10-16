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

from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
SCHEMA_SQL = BACKEND / "db" / "init" / "01_schema.sql"
MIGRATIONS = BACKEND / "db" / "migrations"
CONSTRAINT_MIGRATION = MIGRATIONS / "03_constrain_message_role_and_triage_level.sql"

# What the code actually writes. app/core/enums.py:
#   MessageRole  = USER | ASSISTANT | SYSTEM
#   TriageLevel  = LOW | MODERATE | EMERGENCY
WRITABLE_ROLES = {"USER", "ASSISTANT"}
WRITABLE_TRIAGE_LEVELS = {"LOW", "MODERATE", "EMERGENCY"}


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
