"""The reply arrives while the model is still writing it (C1).

The stream used to carry the whole answer in one `message` event, produced
after the model had finished, so the user watched a spinner and then saw the
answer appear all at once. Now the provider is asked for a stream and each
piece is sent as it arrives.

The pieces are the answer exactly. What the client appended is what the `done`
event carries, and the `done` event still carries every field the frontend
parses, including the verdict the rule engine produced.

The client that cannot stream is the offline fake every other test uses. It
gets the whole answer in one call and the stream degrades to what it was
before, which is why the rest of the suite keeps passing unchanged.
"""

import json
import time
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import symptom_agent
from app.api import chat as chat_api
from app.core.db import get_session
from app.core.openai_client import LLMCallError
from app.core.rate_limit import InMemoryRateLimiter, set_limiter
from app.main import app
from app.models import Conversation, User
from app.services import triage

# An extraction with both safety answers but nothing else. The graph cannot
# hand that to the rule engine, so it asks the model a follow-up question, and
# that question is the reply. It is the one turn where the model owns the
# wording.
_QUESTION_EXTRACTION = json.dumps(
    {
        "symptoms": [],
        "severity": None,
        "duration": None,
        "possible_trigger": None,
        "breathing_difficulty": False,
        "airway_swelling": False,
        "ready": False,
    }
)

# A red flag in the extraction. The rule engine answers EMERGENCY for it, and
# the answer is the engine's own text, not the model's.
_EMERGENCY_EXTRACTION = json.dumps(
    {
        "symptoms": ["throat_swelling"],
        "severity": 5,
        "duration": "this morning",
        "possible_trigger": "unknown",
        "breathing_difficulty": True,
        "airway_swelling": False,
        "ready": True,
    }
)

_PIECES = ["How long ", "has this ", "been going on?"]


@pytest.fixture(autouse=True)
def fresh_limiter():
    """A disabled limiter for every test in this file.

    The real limiter is process-wide, so a 429 raised in one test would leak
    into the next and fail it for no reason.
    """
    set_limiter(InMemoryRateLimiter(limit_per_minute=0))
    yield
    set_limiter(None)


@pytest_asyncio.fixture
async def chat_session() -> AsyncGenerator[AsyncSession, None]:
    """A database with the whole schema, so a turn can be persisted for real."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool
    from sqlmodel import SQLModel

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
async def chat_client(chat_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def _override() -> AsyncGenerator[AsyncSession, None]:
        yield chat_session

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


class _StreamingLLM:
    """A client that answers the extraction in one call and streams the reply.

    `pieces` arrive one at a time, `delay` apart, so the reply can be caught
    in the middle of being written. `fail_after` kills the stream half way
    through, the way a flaky provider does.
    """

    def __init__(
        self,
        extraction: str,
        pieces: list[str] | None = None,
        *,
        fail_after: int | None = None,
        delay: float = 0.0,
        fail_extraction: bool = False,
    ) -> None:
        self._extraction = extraction
        self._pieces = pieces or []
        self._fail_after = fail_after
        self._delay = delay
        self._fail_extraction = fail_extraction
        self.produced: list[str] = []

    def complete(self, messages) -> str:
        if self._fail_extraction:
            raise LLMCallError("unavailable", "model call failed")
        return self._extraction

    def stream_complete(self, messages):
        for index, piece in enumerate(self._pieces):
            if self._fail_after is not None and index >= self._fail_after:
                raise LLMCallError("unavailable", "model call failed")
            if self._delay:
                time.sleep(self._delay)
            self.produced.append(piece)
            yield piece


async def _register_and_login(client: AsyncClient, email: str) -> tuple[str, int]:
    payload = {"email": email, "password": "correcthorse123"}
    await client.post("/api/auth/register", json=payload)
    res = await client.post("/api/auth/login", json=payload)
    token = res.json()["access_token"]
    # A chat turn writes health information, so the 민감정보 gate asks for
    # consent first. These tests are about the stream, not the gate.
    await client.post(
        "/api/privacy/consent", json={"granted": True}, headers={"Authorization": f"Bearer {token}"}
    )
    me = await client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    return token, me.json()["id"]


def _install(monkeypatch, llm) -> None:
    monkeypatch.setitem(app.dependency_overrides, chat_api.get_llm, lambda: llm)


def _parse_sse(body: str) -> list[tuple[str, dict]]:
    """SSE frames in arrival order, as (event name, parsed data) pairs."""
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


def _only_done(events: list[tuple[str, dict]]) -> dict:
    dones = [data for name, data in events if name == "done"]
    assert len(dones) == 1, f"expected exactly one done event, got {len(dones)}"
    return dones[0]


def _deltas(events: list[tuple[str, dict]]) -> list[str]:
    return [data["delta"] for name, data in events if name == "message"]


@pytest.mark.asyncio
async def test_the_reply_arrives_as_the_provider_writes_it(
    chat_client: AsyncClient, monkeypatch
) -> None:
    """More than one delta, and the pieces are the model's own."""
    _install(monkeypatch, _StreamingLLM(_QUESTION_EXTRACTION, _PIECES))
    token, _ = await _register_and_login(chat_client, "stream@example.com")

    res = await chat_client.post(
        "/api/chat", json={"message": "my eyes itch"}, headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 200, res.text
    events = _parse_sse(res.text)
    deltas = _deltas(events)

    assert len(deltas) > 1, f"the reply arrived in one frame: {deltas}"
    assert deltas == _PIECES, "the pieces have to be the ones the provider sent"


@pytest.mark.asyncio
async def test_the_deltas_concatenate_to_the_done_message_exactly(
    chat_client: AsyncClient, monkeypatch
) -> None:
    """The contract: what the client appended is what `done` says the reply is."""
    _install(monkeypatch, _StreamingLLM(_QUESTION_EXTRACTION, _PIECES))
    token, _ = await _register_and_login(chat_client, "concat@example.com")

    res = await chat_client.post(
        "/api/chat", json={"message": "my eyes itch"}, headers={"Authorization": f"Bearer {token}"}
    )
    events = _parse_sse(res.text)

    assert "".join(_deltas(events)) == _only_done(events)["message"]


@pytest.mark.asyncio
async def test_the_first_piece_arrives_before_the_model_has_finished(
    chat_session: AsyncSession, monkeypatch
) -> None:
    """The whole point of asking the provider for a stream.

    The reply is read while it is still being written: the first delta is on
    the wire before the model has produced the last piece.
    """
    llm = _StreamingLLM(_QUESTION_EXTRACTION, _PIECES, delay=0.1)
    user = User(email="early@example.com", password_hash="x")
    chat_session.add(user)
    await chat_session.commit()
    await chat_session.refresh(user)

    conversation = Conversation(user_id=user.id, status="ACTIVE")
    chat_session.add(conversation)
    await chat_session.commit()
    await chat_session.refresh(conversation)

    request = chat_api.ChatRequest(message="my eyes itch")
    produced_at_first_delta = None
    async for frame in chat_api._run_chat(request, chat_session, llm, user.id, conversation):
        if produced_at_first_delta is None and frame.startswith("event: message"):
            produced_at_first_delta = len(llm.produced)

    assert produced_at_first_delta is not None, "no delta was emitted"
    assert 0 < produced_at_first_delta < len(_PIECES), (
        f"the whole answer was already written when the first delta went out: {llm.produced}"
    )


@pytest.mark.asyncio
async def test_the_done_event_still_carries_every_field(
    chat_client: AsyncClient, monkeypatch
) -> None:
    """Streaming changes when the text arrives, never what `done` carries."""
    _install(monkeypatch, _StreamingLLM(_QUESTION_EXTRACTION, _PIECES))
    token, _ = await _register_and_login(chat_client, "fields@example.com")

    res = await chat_client.post(
        "/api/chat", json={"message": "my eyes itch"}, headers={"Authorization": f"Bearer {token}"}
    )
    done = _only_done(_parse_sse(res.text))

    assert set(done) == {
        "message",
        "conversation_id",
        "symptoms",
        "severity",
        "duration",
        "possible_trigger",
        "breathing_difficulty",
        "airway_swelling",
        "triage_level",
        "triage_reasons",
        "triage_rule_version",
    }
    assert done["message"] == "".join(_PIECES)
    assert isinstance(done["conversation_id"], int) and done["conversation_id"] > 0
    assert done["triage_level"] is None
    assert done["triage_reasons"] == []


@pytest.mark.asyncio
async def test_the_verdict_is_the_rule_engines_own(chat_client: AsyncClient, monkeypatch) -> None:
    """ADR 0001: the level on the wire is the one the engine produced."""
    _install(monkeypatch, _StreamingLLM(_EMERGENCY_EXTRACTION))
    token, _ = await _register_and_login(chat_client, "verdict@example.com")

    res = await chat_client.post(
        "/api/chat",
        json={"message": "my throat is closing up"},
        headers={"Authorization": f"Bearer {token}"},
    )
    done = _only_done(_parse_sse(res.text))

    expected = triage.assess(
        triage.SymptomInput(
            symptoms=["throat_swelling"],
            severity=5,
            breathing_difficulty=True,
            airway_swelling=False,
        )
    )
    assert done["triage_level"] == expected.level.value == "EMERGENCY"
    assert done["triage_reasons"] == expected.reasons
    assert done["triage_rule_version"] == triage.RULE_VERSION


@pytest.mark.asyncio
async def test_a_provider_failure_mid_stream_is_an_error_event_not_a_500(
    chat_client: AsyncClient, monkeypatch
) -> None:
    """A dead provider is reported, and the stream still ends properly."""
    _install(monkeypatch, _StreamingLLM(_QUESTION_EXTRACTION, _PIECES, fail_after=1))
    token, _ = await _register_and_login(chat_client, "broken@example.com")

    res = await chat_client.post(
        "/api/chat", json={"message": "my eyes itch"}, headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 200, res.text
    events = _parse_sse(res.text)
    names = [name for name, _ in events]

    assert "error" in names, "a dead provider has to be reported"
    assert names.index("error") > names.index("done"), (
        "the error comes after `done`, so the reply reaches the client first"
    )
    assert _only_done(events)["message"] == symptom_agent.FALLBACK_QUESTION


@pytest.mark.asyncio
async def test_a_flaky_provider_cannot_swallow_the_emergency_verdict(
    chat_client: AsyncClient, monkeypatch
) -> None:
    """The recommendation survives a dead provider.

    The first turn confirms a red flag, so the rule engine answers EMERGENCY
    and the answer is stored. The second turn's model call fails. The verdict
    is still on the wire, because the engine decides it and the model does
    not.
    """
    _install(monkeypatch, _StreamingLLM(_EMERGENCY_EXTRACTION))
    token, _ = await _register_and_login(chat_client, "emergency@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    first = await chat_client.post(
        "/api/chat", json={"message": "my throat is closing up"}, headers=headers
    )
    first_done = _only_done(_parse_sse(first.text))
    assert first_done["triage_level"] == "EMERGENCY"

    _install(monkeypatch, _StreamingLLM(_EMERGENCY_EXTRACTION, fail_extraction=True))
    second = await chat_client.post(
        "/api/chat",
        json={
            "message": "and now my chest is tight",
            "conversation_id": first_done["conversation_id"],
        },
        headers=headers,
    )

    assert second.status_code == 200, second.text
    done = _only_done(_parse_sse(second.text))
    assert done["triage_level"] == "EMERGENCY", "the verdict is the engine's, and it still arrives"


@pytest.mark.asyncio
async def test_a_client_that_cannot_stream_still_gets_the_whole_reply(
    chat_client: AsyncClient, monkeypatch
) -> None:
    """The offline path is unchanged: one call, then the text as fragments."""

    class _NoStreamLLM:
        def complete(self, messages) -> str:
            return _QUESTION_EXTRACTION

    _install(monkeypatch, _NoStreamLLM())
    token, _ = await _register_and_login(chat_client, "nostream@example.com")

    res = await chat_client.post(
        "/api/chat", json={"message": "my eyes itch"}, headers={"Authorization": f"Bearer {token}"}
    )
    events = _parse_sse(res.text)

    assert "".join(_deltas(events)) == _only_done(events)["message"]
    assert len(_deltas(events)) > 1, "the whole reply is still cut into fragments"
