"""Read-only queries behind the conversation history endpoints.

`POST /api/chat` already persists every turn into `conversations` +
`messages`, but nothing read them back, so a page refresh dropped the thread
and the user restarted cold. These queries are that read side.

The SQL lives here rather than in `app/api/conversations.py` to keep the
router thin and auth-only, the same split `app/api/notifications.py` uses
with `notification_service.py`.

Scope is strictly reads, and nothing here decides urgency (ADR 0001): the
triage verdict comes back exactly as the rule engine wrote it onto the
message.
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models import Conversation, Message


def _like_pattern(query: str) -> str:
    """The user's text as a LIKE pattern that matches it literally.

    `%` and `_` mean something to LIKE and nothing to the user, so they are
    escaped. A search for "itchy_eyes" has to find "itchy_eyes" and not
    "itchyXeyes".
    """
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


@dataclass(frozen=True)
class ConversationSummary:
    """One entry in the conversation list.

    `last_message` is a preview, not the full log, so the chat screen can draw
    the list without loading every message of every thread.

    `updated_at` means last activity - the newest message, or the conversation's
    own created_at if it has none. It is NOT the `conversations.updated_at`
    column, which nothing writes. The name is kept because it is what the client
    already reads and renders; a second `last_activity_at` alongside it would
    just be two near-identical timestamps for the next reader to choose between.
    """

    id: int
    title: str | None
    created_at: datetime
    updated_at: datetime
    last_message: str | None
    message_count: int


@dataclass(frozen=True)
class ConversationDetail:
    """One conversation with its whole message log, oldest first."""

    id: int
    title: str | None
    created_at: datetime
    messages: list[Message]


async def list_conversations(
    session: AsyncSession, *, user_id: int, query: str | None = None
) -> list[ConversationSummary]:
    """This user's conversations, most recently active first.

    `message_count` counts message *rows*, so three exchanges that each wrote
    a user row and an assistant row report six. A conversation with no messages
    yet reports 0 and a null preview rather than being left out of the list —
    the user just started it.

    `updated_at` is DERIVED from the newest message, not read off the column.
    The column is now written on every turn, so the two agree; deriving it
    still means the list is right even for a row written before that, and it
    keeps the ordering correct for a conversation whose newest message is not
    the newest thing that happened in it.

    Derived rather than maintained by a BEFORE UPDATE trigger on purpose. Tests
    build their schema from SQLModel metadata on SQLite, not from
    db/init/01_schema.sql, so a trigger in the Postgres schema file would exist
    in production and not in the test database at all - a test asserting the
    ordering would pass in CI and fail live. This is plain SQL that behaves the
    same on both engines.

    A conversation with no messages has no newest message, so it coalesces to
    its own created_at. Without that it would sort on NULL, and NULL ordering
    is engine-dependent - the same class of divergence this avoids.

    `query` filters by title or by message content, case-insensitively. An
    empty query means no filter. The filter is ANDed with the owner check, so
    a search can never reach another user's conversation.
    """
    last_activity = func.coalesce(func.max(Message.created_at), Conversation.created_at)

    statement = (
        select(
            Conversation.id,
            Conversation.title,
            Conversation.created_at,
            last_activity,
            func.count(Message.id),
            func.max(Message.id),
        )
        .select_from(Conversation)
        .outerjoin(Message, Message.conversation_id == Conversation.id)
        .where(Conversation.user_id == user_id)
        # Conversation.id is the primary key, so Postgres/SQLite may take the
        # remaining columns from it.
        .group_by(Conversation.id)
        .order_by(last_activity.desc(), Conversation.id.desc())
    )

    needle = query.strip() if query else ""
    if needle:
        pattern = _like_pattern(needle)
        statement = statement.where(
            or_(
                Conversation.title.ilike(pattern, escape="\\"),
                Conversation.id.in_(
                    select(Message.conversation_id).where(
                        Message.content.ilike(pattern, escape="\\")
                    )
                ),
            )
        )

    result = await session.execute(statement)
    rows = result.all()

    # One extra round trip for the previews, instead of a correlated subquery
    # per conversation row.
    newest_ids = [row[5] for row in rows if row[5] is not None]
    previews: dict[int, str] = {}
    if newest_ids:
        latest = await session.execute(
            select(Message.id, Message.content).where(Message.id.in_(newest_ids))
        )
        previews = {message_id: content for message_id, content in latest.all()}

    return [
        ConversationSummary(
            id=conversation_id,
            title=title,
            created_at=created_at,
            updated_at=updated_at,
            last_message=previews.get(newest_id) if newest_id is not None else None,
            message_count=message_count,
        )
        for (
            conversation_id,
            title,
            created_at,
            updated_at,
            message_count,
            newest_id,
        ) in rows
    ]


async def get_conversation(
    session: AsyncSession, *, conversation_id: int, user_id: int
) -> ConversationDetail | None:
    """One conversation with its messages, or None if the caller cannot have it.

    Ownership is part of the WHERE clause rather than a check after the fetch,
    so "not yours" and "no such id" are one and the same answer. The caller
    turns None into a 404; see `app/api/conversations.py` for why it must not
    be a 403.
    """
    result = await session.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
    )
    conversation = result.scalars().first()
    if conversation is None:
        return None

    messages = await session.execute(
        select(Message).where(Message.conversation_id == conversation.id).order_by(Message.id)
    )
    return ConversationDetail(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        messages=list(messages.scalars().all()),
    )
