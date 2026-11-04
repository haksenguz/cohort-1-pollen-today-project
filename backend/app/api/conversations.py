"""Read-only conversation history: the thread the chat screen reloads.

`POST /api/chat` stores every turn, but before this the stored turns had no way
out, so a refresh lost the conversation. Both routes here are GETs and scope
every read to `CurrentUser`; nothing in this module judges urgency (ADR 0001),
it only returns the verdict the rule engine already wrote onto the message.

A conversation that belongs to somebody else is a 404, never a 403: a 403
would confirm the id exists, which leaks that another user holds it. Same rule
`POST /api/chat` uses in `app/api/chat.py`.
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.db import SessionDep
from app.core.security import CurrentUser
from app.models import Message
from app.services import conversation_service

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    triage_level: str | None
    triage_reasons: list[str]
    created_at: datetime


class ConversationSummaryResponse(BaseModel):
    id: int
    title: str | None
    created_at: datetime
    updated_at: datetime
    last_message: str | None
    message_count: int


class ConversationListResponse(BaseModel):
    conversations: list[ConversationSummaryResponse]


class ConversationDetailResponse(BaseModel):
    id: int
    title: str | None
    created_at: datetime
    messages: list[MessageResponse]


def _message_out(message: Message) -> MessageResponse:
    return MessageResponse(
        id=message.id,
        # Stored uppercase (MessageRole); the chat stream already sends this
        # lowercased, so a reloaded thread renders identically.
        role=message.role.lower(),
        content=message.content,
        triage_level=message.triage_level,
        triage_reasons=message.triage_reasons,
        created_at=message.created_at,
    )


@router.get("")
async def list_conversations(
    current_user: CurrentUser, session: SessionDep, q: str | None = None
) -> ConversationListResponse:
    """This user's conversations, newest first.

    `q` searches the titles and the messages of the caller's own
    conversations. An empty or absent `q` returns everything, so the list is
    the same call with one parameter added.
    """
    summaries = await conversation_service.list_conversations(
        session, user_id=current_user.id, query=q
    )
    return ConversationListResponse(
        conversations=[
            ConversationSummaryResponse(
                id=summary.id,
                title=summary.title,
                created_at=summary.created_at,
                updated_at=summary.updated_at,
                last_message=summary.last_message,
                message_count=summary.message_count,
            )
            for summary in summaries
        ]
    )


@router.get("/{conversation_id}")
async def read_conversation(
    conversation_id: int, current_user: CurrentUser, session: SessionDep
) -> ConversationDetailResponse:
    detail = await conversation_service.get_conversation(
        session, conversation_id=conversation_id, user_id=current_user.id
    )
    # Covers both "no such id" and "not yours", so the two stay
    # indistinguishable from the outside.
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return ConversationDetailResponse(
        id=detail.id,
        title=detail.title,
        created_at=detail.created_at,
        messages=[_message_out(message) for message in detail.messages],
    )
