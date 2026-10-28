"""add the emergency contact to users

Revision ID: f2a3b4c5d6e7
Revises: e5f6a7b8c9d0
Create Date: 2026-10-28

The emergency contact is the highest-value setting an allergy app can hold, and
every operating system ships its own version of it. It lives on the account
row, so it is deleted with the account and travels with the privacy export.

All three columns are nullable and have no default. An empty contact is a
contact that was never set, which is different from a contact with a blank
name.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f2a3b4c5d6e7"
down_revision: str | Sequence[str] | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("emergency_contact_name", sa.String(length=80), nullable=True)
    )
    op.add_column(
        "users", sa.Column("emergency_contact_phone", sa.String(length=40), nullable=True)
    )
    op.add_column(
        "users", sa.Column("emergency_contact_note", sa.String(length=200), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("users", "emergency_contact_note")
    op.drop_column("users", "emergency_contact_phone")
    op.drop_column("users", "emergency_contact_name")
