"""add 민감정보 consent columns to users

Revision ID: e5f6a7b8c9d0
Revises: c1d2e3f4a5b6
Create Date: 2026-10-19

Nonexistent: `sensitive_consent_at`, `sensitive_consent_version` and
`sensitive_consent_withdrawn_at` existed on the `User` model and nowhere else,
so `alembic upgrade head` produced a users table the app could not insert into.

All three are nullable and have no default on purpose. A migration that backfilled
`granted = true` would manufacture consent nobody gave, which is the one thing
this column must never do.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | Sequence[str] | None = "c1d2e3f4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("sensitive_consent_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "users", sa.Column("sensitive_consent_version", sa.String(length=32), nullable=True)
    )
    op.add_column(
        "users",
        sa.Column("sensitive_consent_withdrawn_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "sensitive_consent_withdrawn_at")
    op.drop_column("users", "sensitive_consent_version")
    op.drop_column("users", "sensitive_consent_at")
