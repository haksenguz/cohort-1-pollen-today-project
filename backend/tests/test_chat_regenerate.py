"""The last answer can be done again (C3).

A regenerate re-runs the assistant turn for the last thing the user said and
replaces the answer where it stands. The transcript keeps one user turn and
one answer for it, so the thread does not grow a second copy of either.

The redo goes through exactly the same path as a normal turn. The rule engine
still decides the verdict, and the answer that comes back is the one the
engine produced for the fields it was given.
"""

import json
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

from app.api import chat as chat_api
from app.core.db import get_session
from app.core.rate_limit import InMemoryRateLimiter, set_limiter
from app.main import app
from app.models import Conversation, Message
from app.services import triage

# The first extraction answers with a symptom the engine can act on, the second
# with a different one, so a redo has something new to say.
_FIRST_EXTRACTION = json.dumps(
    {
        "symptoms": ["itchy_eyes"],
        "severity": 3,
        "duration": "this morning",
        "possible_trigger": "pollen",
        "breathing_difficulty": False,
        "airway_swelling": False,
        "ready": True,
    }
)
_SECOND_EXTRACTION = json.dumps(
    {
        "symptoms": ["sneezing"],
        "severity": 8,
        "duration": "two days",
        "possible_trigger": "dust",
        "breathing_difficulty": False,
        "airway_swelling": False,
        "ready": True,
    }
)


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


class _ScriptedLLM:
    """Answers the extraction with whatever it is holding, in order."""

    def __init__(self, *extractions: str) -> None:
        self._extractions = list(extractions)
        self.calls = 0

    def complete(self, messages) -> str:
        index = min(self.calls, len(self._extractions) - 1)
        self.calls += 1
        return self._extractions[index]


async def _login(client: AsyncClient, email: str) -> tuple[str, int]:
    payload = {"email": email, "password": "correcthorse123"}
    await client.post("/api/auth/register", json=payload)
    res = await client.post("/api/auth/login", json=payload)
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    # A chat turn writes health information, so the 민감정보 gate asks for
    # consent first. These tests are about the redo, not the gate.
    await client.post("/api/privacy/consent", json={"granted": True}, headers=headers)
    me = await client.get("/api/users/me", headers=headers)
    return token, me.json()["id"]


def _install(monkeypatch, llm) -> None:
    monkeypatch.setitem(app.dependency_overrides, chat_api.get_llm, lambda: llm)


def _parse_sse(body: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for frame in body.split("\n\n"):
        if not frame.strip():
            continue
        name, data = "", ""
        for line in frame.splitlines():
            if line.startswith("event: "):
                name = line[len("event: ") :]
            elif line.startswith("data: "):
                data = line[len("data: ") :]
        events.append((name, json.loads(data)))
    return events


def _only_done(body: str) -> dict:
    dones = [data for name, data in _parse_sse(body) if name == "done"]
    assert len(dones) == 1, f"expected exactly one done event, got {len(dones)}"
    return dones[0]


async def _messages(session: AsyncSession, conversation_id: int) -> list[Message]:
    result = await session.execute(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.id)
    )
    return list(result.scalars().all())


@pytest.mark.asyncio
async def test_a_regenerate_replaces_the_last_answer(
    client: AsyncClient, session: AsyncSession, monkeypatch
) -> None:
    """The answer changes, and the thread keeps its shape."""
    llm = _ScriptedLLM(_FIRST_EXTRACTION, _SECOND_EXTRACTION)
    _install(monkeypatch, llm)
    token, _ = await _login(client, "redo@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    first = await client.post("/api/chat", json={"message": "my eyes itch"}, headers=headers)
    first_done = _only_done(first.text)
    conversation_id = first_done["conversation_id"]
    before = await _messages(session, conversation_id)
    assert len(before) == 2
    # The rows are replaced in place, so the values are copied out. Reading
    # them again later would read the new answer.
    before_content = before[1].content
    before_row_id = before[1].id

    second = await client.post(
        "/api/chat",
        json={"regenerate": True, "conversation_id": conversation_id},
        headers=headers,
    )
    assert second.status_code == 200, second.text
    second_done = _only_done(second.text)

    after = await _messages(session, conversation_id)
    assert len(after) == 2, "the transcript must not grow a second user turn"
    assert [m.role for m in after] == ["USER", "ASSISTANT"]
    assert after[0].content == "my eyes itch", "the user's own turn is untouched"

    expected = triage.assess(
        triage.SymptomInput(
            symptoms=["sneezing"], severity=8, breathing_difficulty=False, airway_swelling=False
        )
    )
    assert after[1].content == expected.recommendation
    assert after[1].content != before_content, "the old answer has to be gone"
    assert after[1].id == before_row_id, "the answer is replaced where it stands"
    assert after[1].triage_level == expected.level.value
    assert second_done["message"] == after[1].content
    assert second_done["triage_level"] == expected.level.value


@pytest.mark.asyncio
async def test_a_regenerate_answers_the_last_user_message_again(
    client: AsyncClient, session: AsyncSession, monkeypatch
) -> None:
    """The message that gets answered again is the last one the user sent."""
    llm = _ScriptedLLM(_FIRST_EXTRACTION, _FIRST_EXTRACTION, _SECOND_EXTRACTION)
    _install(monkeypatch, llm)
    token, _ = await _login(client, "redo2@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    first = await client.post("/api/chat", json={"message": "my eyes itch"}, headers=headers)
    conversation_id = _only_done(first.text)["conversation_id"]
    await client.post(
        "/api/chat",
        json={"message": "and my nose runs", "conversation_id": conversation_id},
        headers=headers,
    )

    await client.post(
        "/api/chat",
        json={"regenerate": True, "conversation_id": conversation_id},
        headers=headers,
    )

    messages = await _messages(session, conversation_id)
    assert [m.content for m in messages] == [
        "my eyes itch",
        messages[1].content,
        "and my nose runs",
        messages[3].content,
    ]
    assert len(messages) == 4, "one user turn and one answer for each of the two turns"


@pytest.mark.asyncio
async def test_a_turn_without_a_message_or_a_regenerate_is_rejected(
    client: AsyncClient, monkeypatch
) -> None:
    """The request says how to fix itself."""
    _install(monkeypatch, _ScriptedLLM(_FIRST_EXTRACTION))
    token, _ = await _login(client, "empty@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    res = await client.post("/api/chat", json={}, headers=headers)

    assert res.status_code == 422
    detail = json.dumps(res.json())
    assert "message" in detail
    assert "regenerate" in detail


@pytest.mark.asyncio
async def test_a_regenerate_without_a_conversation_is_rejected(
    client: AsyncClient, monkeypatch
) -> None:
    """A redo needs to know what to redo."""
    _install(monkeypatch, _ScriptedLLM(_FIRST_EXTRACTION))
    token, _ = await _login(client, "noconvo@example.com")

    res = await client.post(
        "/api/chat",
        json={"regenerate": True},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 422
    assert "conversation_id" in json.dumps(res.json())


@pytest.mark.asyncio
async def test_a_regenerate_on_an_empty_conversation_is_rejected(
    client: AsyncClient, session: AsyncSession, monkeypatch
) -> None:
    """Nothing to do again is refused, not quietly ignored."""
    _install(monkeypatch, _ScriptedLLM(_FIRST_EXTRACTION))
    token, user_id = await _login(client, "emptyconvo@example.com")

    conversation = Conversation(user_id=user_id, status="ACTIVE")
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)

    res = await client.post(
        "/api/chat",
        json={"regenerate": True, "conversation_id": conversation.id},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 409, res.text
    assert "message" in json.dumps(res.json()).lower()


@pytest.mark.asyncio
async def test_a_regenerate_does_not_touch_another_users_conversation(
    client: AsyncClient, session: AsyncSession, monkeypatch
) -> None:
    """The conversation has to belong to the caller."""
    _install(monkeypatch, _ScriptedLLM(_FIRST_EXTRACTION))
    token, _ = await _login(client, "owner@example.com")
    _, other_id = await _login(client, "stranger@example.com")

    conversation = Conversation(user_id=other_id, status="ACTIVE")
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)

    res = await client.post(
        "/api/chat",
        json={"regenerate": True, "conversation_id": conversation.id},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 404, res.text


@pytest.mark.asyncio
async def test_a_regenerate_goes_through_the_rule_engine(
    client: AsyncClient, session: AsyncSession, monkeypatch
) -> None:
    """ADR 0001: the redo is judged by the engine, not by the model."""
    emergency = json.dumps(
        {
            "symptoms": ["throat_swelling"],
            "severity": 5,
            "duration": "minutes",
            "possible_trigger": "unknown",
            "breathing_difficulty": True,
            "airway_swelling": False,
            "ready": True,
        }
    )
    llm = _ScriptedLLM(emergency, emergency)
    _install(monkeypatch, llm)
    token, _ = await _login(client, "redoemergency@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    first = await client.post(
        "/api/chat", json={"message": "my throat is closing up"}, headers=headers
    )
    conversation_id = _only_done(first.text)["conversation_id"]

    second = await client.post(
        "/api/chat",
        json={"regenerate": True, "conversation_id": conversation_id},
        headers=headers,
    )
    done = _only_done(second.text)

    expected = triage.assess(
        triage.SymptomInput(
            symptoms=["throat_swelling"],
            severity=5,
            breathing_difficulty=True,
            airway_swelling=False,
        )
    )
    assert done["triage_level"] == expected.level.value == "EMERGENCY"
    assert done["message"] == expected.recommendation
