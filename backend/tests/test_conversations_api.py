"""Read-only conversation history endpoints.

Two things are worth knowing about the fixture.

`conversations` and `messages` are the tables under test. The `messages`
columns that hold JSON are JSONB on Postgres and plain JSON on SQLite, so both
dialects compile the real table definitions and this file does not need a
substituted copy of the schema.

Ordering is set with explicit `updated_at`/`created_at` values instead of
sleeping, so "newest first" is asserted rather than assumed.
"""

import os
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.db import get_session
from app.main import app
from app.models import Conversation, Message, User, UserAllergy

T0 = datetime(2026, 10, 16, 8, 12, 0, tzinfo=UTC)


def _sqlite_metadata() -> MetaData:
    """users/conversations/messages, as the models declare them."""
    metadata = MetaData()
    for table in (User.__table__, UserAllergy.__table__, Conversation.__table__, Message.__table__):
        table.to_metadata(metadata)
    return metadata


def _build_engine():
    url = os.environ.get("TEST_DATABASE_URL", "")
    if url.startswith("postgresql"):
        return create_async_engine(url, future=True), True
    return (
        create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        ),
        False,
    )


@pytest_asyncio.fixture
async def conversation_session() -> AsyncGenerator[AsyncSession, None]:
    engine, is_postgres = _build_engine()
    if is_postgres:
        async with engine.begin() as conn:
            await conn.run_sync(lambda c: User.metadata.create_all(c))
        # Children first, as tests/test_conftest_wipe_order.py pins.
        async with engine.begin() as conn:
            for table in (Message.__table__, Conversation.__table__, User.__table__):
                await conn.execute(table.delete())
    else:
        async with engine.begin() as conn:
            await conn.run_sync(_sqlite_metadata().create_all)

    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


@pytest_asyncio.fixture
async def conversation_client(
    conversation_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    async def _override() -> AsyncGenerator[AsyncSession, None]:
        yield conversation_session

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def _login(client: AsyncClient, email: str) -> tuple[str, int]:
    payload = {"email": email, "password": "correcthorse123"}
    await client.post("/api/auth/register", json=payload)
    res = await client.post("/api/auth/login", json=payload)
    token = res.json()["access_token"]
    me = await client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    return token, me.json()["id"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _as_utc(value: str) -> datetime:
    """Read a wire timestamp as an aware UTC datetime.

    The trailing `Z` in docs/API_CONTRACT.md is what Postgres sends, because
    these columns are TIMESTAMPTZ there and Postgres is what docker runs.
    SQLite's DATETIME hands the value back naive, so the suffix cannot be
    asserted here — that is the dialect gap tests/conftest.py documents, and
    papering over it would hide the very bug that note exists to catch.
    """
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


async def _conversation(session: AsyncSession, user_id: int, **kwargs) -> Conversation:
    conversation = Conversation(user_id=user_id, status="ACTIVE", **kwargs)
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    return conversation


async def _message(session: AsyncSession, conversation_id: int, role: str, content: str, **kwargs):
    message = Message(conversation_id=conversation_id, role=role, content=content, **kwargs)
    session.add(message)
    await session.commit()
    await session.refresh(message)
    return message


# ---------------------------------------------------------------------------
# Auth boundary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_rejects_anonymous_callers(conversation_client: AsyncClient) -> None:
    res = await conversation_client.get("/api/conversations")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_read_rejects_anonymous_callers(conversation_client: AsyncClient) -> None:
    res = await conversation_client.get("/api/conversations/1")
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/conversations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_returns_the_callers_conversations(
    conversation_client: AsyncClient, conversation_session: AsyncSession
) -> None:
    token, user_id = await _login(conversation_client, "lister@example.com")
    other_token, other_id = await _login(conversation_client, "neighbour@example.com")

    mine = await _conversation(
        conversation_session, user_id, title="chest tightness after running", created_at=T0
    )
    await _conversation(conversation_session, other_id, title="someone else", created_at=T0)
    # Uppercase, matching MessageRole and the column's CHECK. chat.py only
    # ever writes uppercase; the API lowercases on the way out.
    for i in range(1, 4):
        await _message(
            conversation_session,
            mine.id,
            "USER" if i % 2 else "ASSISTANT",
            f"m{i}",
        )

    res = await conversation_client.get("/api/conversations", headers=_auth(token))

    assert res.status_code == 200
    body = res.json()
    assert [c["id"] for c in body["conversations"]] == [mine.id], "another user's thread leaked"
    summary = body["conversations"][0]
    assert summary["title"] == "chest tightness after running"
    assert _as_utc(summary["created_at"]) == T0
    assert "updated_at" in summary
    assert summary["last_message"] == "m3"
    assert summary["message_count"] == 3
    assert set(summary) == {
        "id",
        "title",
        "created_at",
        "updated_at",
        "last_message",
        "message_count",
    }


@pytest.mark.asyncio
async def test_list_orders_by_last_activity_not_creation(
    conversation_client: AsyncClient, conversation_session: AsyncSession
) -> None:
    """A thread you came back to today belongs above one you opened later and left.

    Nothing writes `conversations.updated_at`: `_persist_turn` returns an
    existing conversation untouched, so that column stays frozen at whatever
    INSERT put there. Ordering by it silently orders by creation time instead,
    and it looks right for as long as a conversation is messaged seconds after
    it is opened. The `updated_at` values below are set explicitly to show the
    ordering ignores them entirely.
    """
    token, user_id = await _login(conversation_client, "activity@example.com")

    revisited = await _conversation(
        conversation_session, user_id, created_at=T0, updated_at=T0 + timedelta(minutes=1)
    )
    await _message(
        conversation_session, revisited.id, "USER", "back again", created_at=T0 + timedelta(hours=3)
    )

    abandoned = await _conversation(
        conversation_session,
        user_id,
        created_at=T0 + timedelta(hours=1),
        updated_at=T0 + timedelta(hours=1),
    )

    res = await conversation_client.get("/api/conversations", headers=_auth(token))

    assert [c["id"] for c in res.json()["conversations"]] == [revisited.id, abandoned.id]


@pytest.mark.asyncio
async def test_updated_at_reports_last_activity_not_the_stale_column(
    conversation_client: AsyncClient, conversation_session: AsyncSession
) -> None:
    """The client renders this field as relative time.

    ChatHistoryList.tsx:112 calls `formatRelativeTime(conversation.updated_at)`.
    Fixing only the ORDER while still returning the frozen column would sort
    correctly and then display "3 months ago" on a thread from yesterday -
    right order, lying timestamp.
    """
    token, user_id = await _login(conversation_client, "stamp@example.com")
    conversation = await _conversation(conversation_session, user_id, created_at=T0, updated_at=T0)
    await _message(
        conversation_session,
        conversation.id,
        "ASSISTANT",
        "still here",
        created_at=T0 + timedelta(days=3),
    )

    body = (await conversation_client.get("/api/conversations", headers=_auth(token))).json()

    summary = next(c for c in body["conversations"] if c["id"] == conversation.id)
    assert _as_utc(summary["updated_at"]) == T0 + timedelta(days=3)
    assert summary["updated_at"] != summary["created_at"], (
        "returning the untouched column is the bug; it would render as the "
        "conversation's age rather than its last activity"
    )


@pytest.mark.asyncio
async def test_empty_conversation_orders_by_its_own_creation(
    conversation_client: AsyncClient, conversation_session: AsyncSession
) -> None:
    """`max()` over no messages is NULL, and NULL ordering is engine-dependent.

    Without the coalesce a brand-new conversation sorts on NULL against real
    timestamps, which Postgres and SQLite do not agree on - reintroducing
    exactly the cross-engine divergence the derived ordering exists to avoid.
    """
    token, user_id = await _login(conversation_client, "emptyorder@example.com")

    older = await _conversation(conversation_session, user_id, created_at=T0)
    newer = await _conversation(conversation_session, user_id, created_at=T0 + timedelta(hours=2))

    res = await conversation_client.get("/api/conversations", headers=_auth(token))
    conversations = res.json()["conversations"]

    assert [c["id"] for c in conversations] == [newer.id, older.id]
    # The coalesce, asserted on the value rather than only on the position: with
    # no messages there is no newest message, so the fallback has to be the
    # conversation's own created_at and not NULL. NULL would sort differently
    # per engine and render as a dash in ChatHistoryList.
    for summary, conversation in ((conversations[0], newer), (conversations[1], older)):
        assert _as_utc(summary["updated_at"]) == T0 + (
            timedelta(hours=2) if conversation.id == newer.id else timedelta()
        )


@pytest.mark.asyncio
async def test_message_count_counts_rows_not_turns(
    conversation_client: AsyncClient, conversation_session: AsyncSession
) -> None:
    token, user_id = await _login(conversation_client, "turns@example.com")
    conversation = await _conversation(conversation_session, user_id, created_at=T0)

    for turn in range(3):
        await _message(conversation_session, conversation.id, "USER", f"q{turn}")
        await _message(conversation_session, conversation.id, "ASSISTANT", f"a{turn}")

    body = (await conversation_client.get("/api/conversations", headers=_auth(token))).json()

    summary = body["conversations"][0]
    assert summary["message_count"] == 6, "three exchanges are six rows"
    assert summary["last_message"] == "a2"


@pytest.mark.asyncio
async def test_empty_conversation_reports_a_null_preview(
    conversation_client: AsyncClient, conversation_session: AsyncSession
) -> None:
    token, user_id = await _login(conversation_client, "empty@example.com")
    await _conversation(conversation_session, user_id, created_at=T0)

    body = (await conversation_client.get("/api/conversations", headers=_auth(token))).json()

    summary = body["conversations"][0]
    assert summary["message_count"] == 0
    assert summary["last_message"] is None


@pytest.mark.asyncio
async def test_title_stays_null_until_something_generates_it(
    conversation_client: AsyncClient, conversation_session: AsyncSession
) -> None:
    """No placeholder title: null has to stay distinguishable from "titled"."""
    token, user_id = await _login(conversation_client, "untitled@example.com")
    untitled = await _conversation(conversation_session, user_id, created_at=T0)
    titled = await _conversation(conversation_session, user_id, title="hay fever", created_at=T0)

    body = (await conversation_client.get("/api/conversations", headers=_auth(token))).json()
    by_id = {c["id"]: c for c in body["conversations"]}

    assert by_id[untitled.id]["title"] is None
    assert by_id[titled.id]["title"] == "hay fever"

    detail = (
        await conversation_client.get(f"/api/conversations/{untitled.id}", headers=_auth(token))
    ).json()
    assert detail["title"] is None


@pytest.mark.asyncio
async def test_list_is_empty_for_a_user_with_no_conversations(
    conversation_client: AsyncClient,
) -> None:
    token, _ = await _login(conversation_client, "fresh@example.com")

    res = await conversation_client.get("/api/conversations", headers=_auth(token))

    assert res.status_code == 200
    assert res.json() == {"conversations": []}


# ---------------------------------------------------------------------------
# GET /api/conversations/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_returns_the_thread_with_its_triage_verdict(
    conversation_client: AsyncClient, conversation_session: AsyncSession
) -> None:
    token, user_id = await _login(conversation_client, "reader@example.com")
    conversation = await _conversation(
        conversation_session, user_id, title="chest tightness after running", created_at=T0
    )
    await _message(conversation_session, conversation.id, "USER", "my chest feels tight")
    await _message(
        conversation_session,
        conversation.id,
        "ASSISTANT",
        "that needs attention now",
        triage_level="MODERATE",
        triage_reasons=["severity 6 >= 5"],
    )

    res = await conversation_client.get(
        f"/api/conversations/{conversation.id}", headers=_auth(token)
    )

    assert res.status_code == 200
    body = res.json()
    assert body["id"] == conversation.id
    assert body["title"] == "chest tightness after running"
    assert _as_utc(body["created_at"]) == T0
    assert set(body) == {"id", "title", "created_at", "messages"}

    first, second = body["messages"]
    assert set(first) == {
        "id",
        "role",
        "content",
        "triage_level",
        "triage_reasons",
        "created_at",
    }
    assert (first["role"], first["content"]) == ("user", "my chest feels tight")
    assert first["triage_level"] is None
    assert first["triage_reasons"] == []
    assert (second["role"], second["triage_level"]) == ("assistant", "MODERATE")
    assert second["triage_reasons"] == ["severity 6 >= 5"]


@pytest.mark.asyncio
async def test_messages_come_back_in_id_order_not_created_at_order(
    conversation_client: AsyncClient, conversation_session: AsyncSession
) -> None:
    token, user_id = await _login(conversation_client, "chronological@example.com")
    conversation = await _conversation(conversation_session, user_id, created_at=T0)
    # created_at is deliberately reversed: the log follows the row id the chat
    # screen appended in, not a timestamp that can drift.
    first = await _message(
        conversation_session, conversation.id, "USER", "first", created_at=T0 + timedelta(minutes=5)
    )
    second = await _message(
        conversation_session, conversation.id, "ASSISTANT", "second", created_at=T0
    )

    body = (
        await conversation_client.get(f"/api/conversations/{conversation.id}", headers=_auth(token))
    ).json()

    assert first.id < second.id
    assert [m["id"] for m in body["messages"]] == [first.id, second.id]
    assert [m["content"] for m in body["messages"]] == ["first", "second"]


@pytest.mark.asyncio
async def test_read_returns_an_empty_log_for_an_empty_conversation(
    conversation_client: AsyncClient, conversation_session: AsyncSession
) -> None:
    token, user_id = await _login(conversation_client, "bare@example.com")
    conversation = await _conversation(conversation_session, user_id, created_at=T0)

    res = await conversation_client.get(
        f"/api/conversations/{conversation.id}", headers=_auth(token)
    )

    assert res.status_code == 200
    assert res.json()["messages"] == []


@pytest.mark.asyncio
async def test_cannot_read_someone_elses_conversation(
    conversation_client: AsyncClient, conversation_session: AsyncSession
) -> None:
    owner_token, owner_id = await _login(conversation_client, "owner2@example.com")
    intruder_token, _ = await _login(conversation_client, "intruder2@example.com")
    conversation = await _conversation(conversation_session, owner_id, created_at=T0)
    await _message(conversation_session, conversation.id, "USER", "private symptom history")

    assert (
        await conversation_client.get(
            f"/api/conversations/{conversation.id}", headers=_auth(owner_token)
        )
    ).status_code == 200

    res = await conversation_client.get(
        f"/api/conversations/{conversation.id}", headers=_auth(intruder_token)
    )

    # 404, never 403: a 403 confirms the id exists, which tells the intruder
    # that somebody else holds this conversation.
    assert res.status_code == 404
    assert res.status_code != 403
    assert "private symptom history" not in res.text


@pytest.mark.asyncio
async def test_missing_conversation_is_404(conversation_client: AsyncClient) -> None:
    token, _ = await _login(conversation_client, "solo2@example.com")

    res = await conversation_client.get("/api/conversations/999999", headers=_auth(token))

    assert res.status_code == 404
