"""add the user_llm_setting table

Revision ID: d1e2f3a4b5c6
Revises: b8c9d0e1f2a3
Create Date: 2026-11-17

One row per user who brought their own LLM key. The key is stored only as
Fernet ciphertext. created_at gets the same server default as every other
created_at column (see a7b8c9d0e1f2).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d1e2f3a4b5c6"
down_revision: str | Sequence[str] | None = "b8c9d0e1f2a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_llm_setting",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("api_key_encrypted", sa.String(length=1024), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index(
        op.f("ix_user_llm_setting_user_id"), "user_llm_setting", ["user_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_user_llm_setting_user_id"), table_name="user_llm_setting")
    op.drop_table("user_llm_setting")
