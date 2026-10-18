"""add conversations.title and the denormalised triage columns on messages

Why this exists: the app never ran its migrations. `init_db()` calls
`SQLModel.metadata.create_all`, which creates a table that is missing and does
nothing at all to a table that already exists — so every column added to a model
after 2026-09-09 reached tests (which build from SQLModel metadata) and never
reached a deployed database.

Three columns were in that state:

  conversations.title          read by the history list, never existed in the
                               migration, so a database built from the
                               migration cannot store a title
  messages.triage_level        the persisted ADR 0001 verdict
  messages.triage_reasons      likewise

The two CHECK constraints below had the same problem for a different reason.
They are declared in the model's `__table_args__` so that tests and local runs
enforce them, and in `docs/erd/gen_dmm.py` so the generated
`db/init/01_schema.sql` carries them — but neither is in any migration, so on a
database created by `alembic upgrade head` they were absent while the code
assumed them.

Revision ID: c1d2e3f4a5b6
Revises: 4fb86814b892
Create Date: 2026-10-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql

revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, Sequence[str], None] = '4fb86814b892'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('conversations',
                  sa.Column('title',
                            sqlmodel.sql.sqltypes.AutoString(length=200),
                            nullable=True))
    op.add_column('messages',
                  sa.Column('triage_level',
                            sqlmodel.sql.sqltypes.AutoString(length=12),
                            nullable=True))
    op.add_column('messages',
                  sa.Column('triage_reasons',
                            postgresql.JSONB(astext_type=sa.Text()),
                            nullable=True))

    # UPPERCASE, because that is what app/core/enums.py writes and what every
    # existing row holds. SYSTEM is excluded: nothing writes it, and the API's
    # role union has no "system", so allowing it would let through a row that
    # renders with no safety banner. Kept identical to __table_args__ in
    # app/models/__init__.py and to gen_dmm.py; test_schema_constraints.py
    # asserts the three agree.
    op.create_check_constraint(
        'messages_role_check', 'messages', "role IN ('USER', 'ASSISTANT')"
    )
    op.create_check_constraint(
        'messages_triage_level_check',
        'messages',
        "triage_level IS NULL OR triage_level IN ('LOW', 'MODERATE', 'EMERGENCY')",
    )


def downgrade() -> None:
    op.drop_constraint('messages_triage_level_check', 'messages', type_='check')
    op.drop_constraint('messages_role_check', 'messages', type_='check')
    op.drop_column('messages', 'triage_reasons')
    op.drop_column('messages', 'triage_level')
    op.drop_column('conversations', 'title')