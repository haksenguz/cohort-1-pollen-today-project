"""Chat endpoint for the symptom agent (documentation §12, ADR 0002).

The frontend PWA streams chat over SSE (ADR 0002), so this endpoint responds
with `text/event-stream`: a `message` event per assistant turn, and a
`done` event carrying the same fields as documentation §12's example
response plus the structured extraction and, once the rule engine has run,
its triage verdict.

Safety boundary (ADR 0001): this module never decides urgency itself. It
loads/saves conversation state and calls `app.agents.symptom_agent.run_turn`,
which only ever produces a `triage_level` by calling the deterministic
`app.services.triage.assess`. Nothing here inspects symptoms and picks a
level on its own.
"""

import json
import logging
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.agents import symptom_agent
from app.core.config import get_settings
from app.core.db import SessionDep
from app.core.enums import ConversationStatus, MessageRole
from app.core.security import CurrentUser
from app.models import Conversation, Message, SymptomEvent, TriageResult

router = APIRouter(prefix="/api/chat", tags=["chat"])
logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: int | None = None


class ChatResponse(BaseModel):
    message: str
    conversation_id: int
    symptoms: list[str]
    severity: int | None
    duration: str | None
    possible_trigger: str | None
    breathing_difficulty: bool | None
    airway_swelling: bool | None
    triage_level: str | None
    triage_reasons: list[str]
    triage_rule_version: str | None


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def _get_or_create_conversation(
    session: AsyncSession, *, conversation_id: int | None, user_id: int
) -> Conversation:
    if conversation_id is not None:
        conversation = await session.get(Conversation, conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="conversation not found")
        if conversation.user_id != user_id:
            # Same 404 as "missing" on purpose, so this never confirms that a
            # conversation belonging to someone else exists.
            raise HTTPException(status_code=404, detail="conversation not found")
        return conversation

    conversation = Conversation(user_id=user_id, status=ConversationStatus.ACTIVE)
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    return conversation


async def _load_state(
    session: AsyncSession, conversation: Conversation
) -> symptom_agent.AllergyState:
    rows = await session.execute(
        select(Message).where(Message.conversation_id == conversation.id).order_by(Message.id)
    )
    history: list[symptom_agent.ChatMessage] = [
        {"role": m.role.lower(), "content": m.content} for m in rows.scalars().all()
    ]
    state = symptom_agent.initial_state(history)

    latest = await session.execute(
        select(SymptomEvent)
        .where(SymptomEvent.conversation_id == conversation.id)
        .order_by(SymptomEvent.id.desc())
    )
    event = latest.scalars().first()
    if event is not None:
        state["symptoms"] = list(event.symptoms or [])
        state["severity"] = event.severity
        state["duration"] = event.duration
        state["possible_trigger"] = event.possible_trigger
        state["breathing_difficulty"] = event.breathing_difficulty
        state["airway_swelling"] = event.airway_swelling
    return state


async def _persist_turn(
    session: AsyncSession,
    conversation: Conversation,
    *,
    user_id: int,
    user_message: str,
    result: symptom_agent.AllergyState,
) -> SymptomEvent | None:
    session.add(
        Message(conversation_id=conversation.id, role=MessageRole.USER, content=user_message)
    )
    session.add(
        Message(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content=result.get("assistant_reply") or "",
        )
    )

    event = SymptomEvent(
        user_id=user_id,
        conversation_id=conversation.id,
        symptoms=result.get("symptoms") or [],
        severity=result.get("severity"),
        duration=result.get("duration"),
        possible_trigger=result.get("possible_trigger"),
        breathing_difficulty=bool(result.get("breathing_difficulty")),
        airway_swelling=bool(result.get("airway_swelling")),
    )
    session.add(event)

    triage_level = result.get("triage_level")
    if triage_level is not None:
        conversation.status = ConversationStatus.COMPLETED

    await session.commit()
    await session.refresh(event)

    if triage_level is not None:
        session.add(
            TriageResult(
                symptom_event_id=event.id,
                risk_level=triage_level,
                recommendation=result.get("triage_recommendation"),
                rule_version=result.get("triage_rule_version"),
            )
        )
        await session.commit()

    return event


async def _run_chat(
    req: ChatRequest,
    session: AsyncSession,
    llm: symptom_agent.LLMClient,
    user_id: int,
    conversation: Conversation,
) -> AsyncIterator[str]:
    state = await _load_state(session, conversation)

    try:
        result = symptom_agent.run_turn(llm, state, req.message)
    except Exception:
        logger.exception("symptom_agent.run_turn failed")
        yield _sse("error", {"detail": "the symptom agent failed to process this message"})
        return

    await _persist_turn(
        session,
        conversation,
        user_id=user_id,
        user_message=req.message,
        result=result,
    )

    reply = result.get("assistant_reply") or ""
    yield _sse("message", {"delta": reply})

    payload = ChatResponse(
        message=reply,
        conversation_id=conversation.id,
        symptoms=result.get("symptoms") or [],
        severity=result.get("severity"),
        duration=result.get("duration"),
        possible_trigger=result.get("possible_trigger"),
        breathing_difficulty=result.get("breathing_difficulty"),
        airway_swelling=result.get("airway_swelling"),
        triage_level=result.get("triage_level"),
        triage_reasons=result.get("triage_reasons") or [],
        triage_rule_version=result.get("triage_rule_version"),
    )
    yield _sse("done", payload.model_dump())


class _LazyLLMClient:
    """Builds the real client on first use, not at dependency-resolution time.

    Constructing eagerly made a missing `openai_api_key` a 500 on every chat
    request, including ones that should have been rejected as unauthenticated,
    because FastAPI resolves this before the auth dependency runs. Deferring it
    means a misconfigured key surfaces as the stream's `error` event instead.
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client: symptom_agent.LLMClient | None = None

    def complete(self, messages) -> str:
        if self._client is None:
            self._client = symptom_agent.get_llm_client(self._api_key)
        return self._client.complete(messages)


def get_llm() -> symptom_agent.LLMClient:
    """FastAPI dependency so tests can swap in a fake without a real API key."""
    return _LazyLLMClient(get_settings().openai_api_key)


LLMDep = Annotated[symptom_agent.LLMClient, Depends(get_llm)]


@router.post("")
async def chat(
    req: ChatRequest, session: SessionDep, llm: LLMDep, user: CurrentUser
) -> StreamingResponse:
    # Resolve the conversation before the stream opens. Raising inside the
    # generator would be too late: the 200 and its headers are already sent,
    # so a 404 there would never reach the client.
    conversation = await _get_or_create_conversation(
        session, conversation_id=req.conversation_id, user_id=user.id
    )
    return StreamingResponse(
        _run_chat(req, session, llm, user.id, conversation),
        media_type="text/event-stream",
    )
