"""initial schema

Revision ID: 321c67bcf900
Revises:
Create Date: 2026-09-08 21:01:55.760985

Hand-written to match backend/db/init/01_schema.sql exactly (10 tables). See
that file and docs/erd/allergy_ai.dmm for the source of truth today; the PR
description covers how the two now relate.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "321c67bcf900"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )

    op.create_table(
        "user_allergies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("allergen", sa.String(length=30), nullable=False),
        sa.Column("severity", sa.String(length=10), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "status", sa.String(length=12), server_default=sa.text("'ACTIVE'"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=10), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "symptom_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=True),
        sa.Column("symptoms", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("severity", sa.Integer(), nullable=True),
        sa.Column("duration", sa.String(length=50), nullable=True),
        sa.Column("possible_trigger", sa.String(length=50), nullable=True),
        sa.Column(
            "breathing_difficulty",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("airway_swelling", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "triage_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("symptom_event_id", sa.Integer(), nullable=False),
        sa.Column("risk_level", sa.String(length=12), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("rule_version", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["symptom_event_id"], ["symptom_events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "environment_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("tree_pollen", sa.String(length=10), nullable=True),
        sa.Column("grass_pollen", sa.String(length=10), nullable=True),
        sa.Column("weed_pollen", sa.String(length=10), nullable=True),
        sa.Column("pm25", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("pm10", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("temperature", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("humidity", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("wind_speed", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("risk_level", sa.String(length=12), nullable=True),
        sa.Column("captured_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("environment_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("risk_level", sa.String(length=12), nullable=False),
        sa.Column("alert_type", sa.String(length=15), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["environment_snapshot_id"], ["environment_snapshots.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "hospital_searches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("specialty", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "hospital_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("hospital_search_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("address", sa.String(length=300), nullable=True),
        sa.Column("distance_m", sa.Integer(), nullable=True),
        sa.Column("specialty", sa.String(length=40), nullable=True),
        sa.Column("is_open", sa.Boolean(), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("place_id", sa.String(length=120), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["hospital_search_id"], ["hospital_searches.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("hospital_results")
    op.drop_table("hospital_searches")
    op.drop_table("alerts")
    op.drop_table("environment_snapshots")
    op.drop_table("triage_results")
    op.drop_table("symptom_events")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("user_allergies")
    op.drop_table("users")
