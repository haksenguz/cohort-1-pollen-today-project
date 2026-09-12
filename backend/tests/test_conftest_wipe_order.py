"""Regression test for the conftest wipe order.

SymptomEvent.conversation_id has an FK to Conversation. If the wipe
deletes Conversation before SymptomEvent, Postgres raises a
ForeignKeyViolationError and any test that left a chain behind fails
on cleanup. SQLite ignores FK enforcement by default so this slipped
through local sqlite runs and only blew up on the Postgres CI gate.

This test creates the chain in the same session, then asks the
conftest wipe logic to run. Postgres only — the SQLite path doesn't
even create these tables (JSONB-incompatible in sqlite).
"""

import os

import pytest

from app.models import Conversation, Message, SymptomEvent, User

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL", "").startswith("postgresql"),
    reason="FK wipe order only matters when FKs are enforced (Postgres).",
)


@pytest.fixture
def user_email() -> str:
    return "wipe-order@example.com"


async def test_wipe_handles_fk_chain_user_conversation_symptomevent_message(session, user_email):
    user = User(email=user_email, password_hash="x")  # noqa: S106
    session.add(user)
    await session.commit()
    await session.refresh(user)

    conv = Conversation(user_id=user.id, title="triage check")
    session.add(conv)
    await session.commit()
    await session.refresh(conv)

    event = SymptomEvent(conversation_id=conv.id, user_id=user.id)
    session.add(event)
    await session.commit()
    await session.refresh(event)

    msg = Message(conversation_id=conv.id, role="user", content="hi")
    session.add(msg)
    await session.commit()

    # Force the wipe manually (simulates teardown on a Postgres engine).
    # If the order is wrong, this raises IntegrityError on Postgres.
    from sqlalchemy import delete

    from tests.conftest import _ALL_TABLES

    for tbl in _ALL_TABLES:
        await session.execute(delete(tbl))
    await session.commit()
