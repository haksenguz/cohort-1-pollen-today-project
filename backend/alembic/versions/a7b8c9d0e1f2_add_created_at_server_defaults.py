"""give created_at a server default of now()

Revision ID: a7b8c9d0e1f2
Revises: f2a3b4c5d6e7
Create Date: 2026-11-17

db/init/01_schema.sql and db/migrations/04_created_at_defaults.sql both give
created_at DEFAULT now(). The alembic history never did, so a database built by
`alembic upgrade head` (the only path a fresh deploy takes now that the init
mount is gone) had no default on any created_at column.

updated_at is deliberately left alone. A default there is written once at INSERT
and never moves, because nothing maintains it. See 04_created_at_defaults.sql.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: str | Sequence[str] | None = "f2a3b4c5d6e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Every table in 01_schema.sql that has a created_at column.
TABLES = (
    "users",
    "user_allergies",
    "conversations",
    "messages",
    "symptom_events",
    "triage_results",
    "alerts",
    "notification_preferences",
    "hospital_searches",
    "hospital_results",
)


def upgrade() -> None:
    for table in TABLES:
        op.alter_column(table, "created_at", server_default=sa.text("now()"))


def downgrade() -> None:
    for table in TABLES:
        op.alter_column(table, "created_at", server_default=None)
