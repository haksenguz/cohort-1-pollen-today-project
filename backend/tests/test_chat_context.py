"""Context the question prompt may see: a capped history and saved allergy names.

The extraction prompt and the triage path get neither. These tests pin that,
and they pin that persisted history is never trimmed.
"""

import json
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, select

from app.agents import symptom_agent
from app.api import chat as chat_api
from app.core.db import get_session
from app.core.enums import ConversationStatus, MessageRole
from app.core.rate_limit import InMemoryRateLimiter, set_limiter
from app.main import app
from app.models import Conversation, Message

_QUESTION_EXTRACTION = json.dumps(
    {
        "symptoms": ["sneezing"],
        "severity": None,
        "duration": None,
        "possible_trigger": None,
        "breathing_difficulty": False,
        "airway_swelling": False,
        "ready": False,
    }
)


class _RecordingLLM:
    """Returns the extraction for the first call, then a question. Records every prompt."""

    def __init__(self) -> None:
        self.calls: list[list[dict]] = []

    def complete(self, messages) -> str:
        self.calls.append([dict(m) for m in messages])
        if len(self.calls) == 1:
            return _QUESTION_EXTRACTION
        return "How long have you had these symptoms?"


@pytest.fixture(autouse=True)
def fresh_limiter():
    set_limiter(InMemoryRateLimiter(limit_per_minute=0))
    yield
    set_limiter(None)


@pytest_asyncio.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


@pytest_asyncio.fixture
async def client(session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def _override() -> AsyncGenerator[AsyncSession, None]:
        yield session

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def _login(client: AsyncClient, email: str) -> tuple[dict, int]:
    payload = {"email": email, "password": "correcthorse123"}
    await client.post("/api/auth/register", json=payload)
    res = await client.post("/api/auth/login", json=payload)
    headers = {"Authorization": f"Bearer {res.json()['access_token']}"}
    await client.post("/api/privacy/consent", json={"granted": True}, headers=headers)
    me = await client.get("/api/users/me", headers=headers)
    return headers, me.json()["id"]


# --- Pure agent behaviour -------------------------------------------------


def test_question_prompt_names_saved_allergies_only() -> None:
    state = symptom_agent.initial_state([], allergies=["birch", "japanese cedar"])
    prompt = symptom_agent._question_system_prompt(state)
    assert prompt.startswith(symptom_agent.QUESTION_SYSTEM_PROMPT)
    assert "birch, japanese cedar." in prompt


def test_question_prompt_is_unchanged_without_allergies() -> None:
    assert (
        symptom_agent._question_system_prompt(symptom_agent.initial_state([]))
        == symptom_agent.QUESTION_SYSTEM_PROMPT
    )


def test_extraction_prompt_never_carries_allergies() -> None:
    llm = _RecordingLLM()
    state = symptom_agent.initial_state([], allergies=["birch"])
    symptom_agent.run_turn(llm, state, "my eyes itch")
    extraction_system = llm.calls[0][0]["content"]
    assert extraction_system == symptom_agent.EXTRACTION_SYSTEM_PROMPT
    assert "birch" not in extraction_system.lower()


def test_allergy_context_does_not_change_the_triage_verdict() -> None:
    with_allergy = symptom_agent.run_turn(
        _RecordingLLM(), symptom_agent.initial_state([], allergies=["birch"]), "itchy"
    )
    without = symptom_agent.run_turn(_RecordingLLM(), symptom_agent.initial_state([]), "itchy")
    assert with_allergy["triage_level"] == without["triage_level"]


# --- Chat layer -----------------------------------------------------------


@pytest.mark.asyncio
async def test_history_sent_to_the_model_is_capped_but_storage_is_not(
    client: AsyncClient, session: AsyncSession
) -> None:
    headers, user_id = await _login(client, "cap@example.com")
    conversation = Conversation(user_id=user_id, status=ConversationStatus.ACTIVE)
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    total = chat_api.MAX_HISTORY_MESSAGES + 10
    for i in range(total):
        role = MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT
        session.add(Message(conversation_id=conversation.id, role=role, content=f"m{i}"))
    await session.commit()

    state = await chat_api._load_state(session, conversation)
    assert len(state["messages"]) == chat_api.MAX_HISTORY_MESSAGES
    assert state["messages"][-1]["content"] == f"m{total - 1}"
    assert state["messages"][0]["content"] == f"m{total - chat_api.MAX_HISTORY_MESSAGES}"

    stored = await session.execute(
        select(Message).where(Message.conversation_id == conversation.id)
    )
    assert len(stored.scalars().all()) == total


@pytest.mark.asyncio
async def test_saved_allergies_reach_the_question_prompt_only(
    client: AsyncClient, session: AsyncSession, monkeypatch
) -> None:
    headers, _ = await _login(client, "allergy@example.com")
    await client.post(
        "/api/allergies", json={"allergen": "BIRCH", "severity": "MODERATE"}, headers=headers
    )
    await client.post(
        "/api/allergies", json={"allergen": "OAK", "severity": "MILD"}, headers=headers
    )

    llm = _RecordingLLM()
    monkeypatch.setitem(app.dependency_overrides, chat_api.get_llm, lambda: llm)
    res = await client.post("/api/chat", json={"message": "my eyes itch"}, headers=headers)
    assert res.status_code == 200, res.text

    assert len(llm.calls) == 2
    extraction_system = llm.calls[0][0]["content"]
    question_system = llm.calls[1][0]["content"]
    assert "birch" not in extraction_system.lower()
    assert "birch, oak." in question_system


@pytest.mark.asyncio
async def test_no_saved_allergies_leaves_the_question_prompt_as_it_was(
    client: AsyncClient, monkeypatch
) -> None:
    headers, _ = await _login(client, "noallergy@example.com")
    llm = _RecordingLLM()
    monkeypatch.setitem(app.dependency_overrides, chat_api.get_llm, lambda: llm)
    await client.post("/api/chat", json={"message": "my eyes itch"}, headers=headers)
    assert llm.calls[1][0]["content"] == symptom_agent.QUESTION_SYSTEM_PROMPT
