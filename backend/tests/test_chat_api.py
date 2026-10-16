"""Auth boundary on the chat endpoint.

`POST /api/chat` used to take `user_id` from the request body, so any caller
could post as any user. These tests pin the identity to the bearer token and
pin conversation ownership.

The SSE body is exercised below, but persistence is not: a real turn writes to
`messages` / `symptom_events`, whose JSONB columns SQLite cannot compile. The
streaming tests therefore stub `_load_state` / `_persist_turn` and drive the
real generator with a scripted model. Agent behaviour is covered in
`test_symptom_agent.py`.
"""

import json
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.agents import symptom_agent
from app.api import chat as chat_api
from app.core.db import get_session
from app.core.rate_limit import InMemoryRateLimiter, set_limiter
from app.main import app
from app.models import Conversation, User, UserAllergy
from app.services import triage


@pytest.fixture(autouse=True)
def fresh_limiter():
    """A disabled limiter for every test in this file.

    The real limiter is process-wide, so without this a 429 raised in one test
    would leak into the next and fail it for no reason. These tests are about
    auth and conversation ownership, not throttling; the limiter has its own
    tests in `test_rate_limit.py` plus the 429 cases below.
    """
    set_limiter(InMemoryRateLimiter(limit_per_minute=0))
    yield
    set_limiter(None)


@pytest_asyncio.fixture
async def chat_session() -> AsyncGenerator[AsyncSession, None]:
    """Like the shared `session` fixture, plus the `conversations` table."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: User.metadata.create_all(
                sync_conn,
                tables=[User.__table__, UserAllergy.__table__, Conversation.__table__],
            )
        )

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


async def _register_and_login(client: AsyncClient, email: str) -> str:
    payload = {"email": email, "password": "correcthorse123"}
    await client.post("/api/auth/register", json=payload)
    res = await client.post("/api/auth/login", json=payload)
    return res.json()["access_token"]


@pytest.mark.asyncio
async def test_chat_rejects_anonymous_callers(chat_client: AsyncClient) -> None:
    res = await chat_client.post("/api/chat", json={"message": "my eyes itch"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_chat_ignores_a_user_id_in_the_body(chat_client: AsyncClient) -> None:
    """The old field is gone; supplying it must not grant another identity."""
    res = await chat_client.post("/api/chat", json={"message": "my eyes itch", "user_id": 1})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_cannot_continue_someone_elses_conversation(
    chat_client: AsyncClient, chat_session: AsyncSession
) -> None:
    owner_token = await _register_and_login(chat_client, "owner@example.com")
    intruder_token = await _register_and_login(chat_client, "intruder@example.com")
    assert owner_token != intruder_token

    owner = (
        await chat_client.get("/api/users/me", headers={"Authorization": f"Bearer {owner_token}"})
    ).json()

    conversation = Conversation(user_id=owner["id"], status="ACTIVE")
    chat_session.add(conversation)
    await chat_session.commit()
    await chat_session.refresh(conversation)

    res = await chat_client.post(
        "/api/chat",
        json={"message": "hello", "conversation_id": conversation.id},
        headers={"Authorization": f"Bearer {intruder_token}"},
    )

    # 404 rather than 403, so this never confirms the conversation exists.
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_missing_conversation_is_404(chat_client: AsyncClient) -> None:
    token = await _register_and_login(chat_client, "solo@example.com")
    res = await chat_client.post(
        "/api/chat",
        json={"message": "hello", "conversation_id": 9999},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Rate limiting. Every chat turn is a real model call, so the endpoint has to
# be bounded; auth alone does not bound a signed-up client.
#
# These assert status and headers, not a completed turn: a successful turn
# writes to `symptom_events`, whose JSONB column SQLite cannot compile. The
# 429 path returns before any of that, which is exactly what is under test.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_returns_429_once_the_user_exceeds_the_limit(chat_client: AsyncClient) -> None:
    set_limiter(InMemoryRateLimiter(limit_per_minute=2))
    token = await _register_and_login(chat_client, "spammer@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # A nonexistent conversation id means each request stops at the 404 branch
    # *after* the limiter has already been consulted, so this stays on SQLite
    # while still proving the limiter runs first.
    codes = []
    for _ in range(3):
        res = await chat_client.post(
            "/api/chat",
            json={"message": "hi", "conversation_id": 9999},
            headers=headers,
        )
        codes.append(res.status_code)

    assert codes[-1] == 429
    assert codes[:2] == [404, 404], "the limiter must only bite once the budget is spent"


@pytest.mark.asyncio
async def test_429_is_a_status_code_not_an_sse_event(chat_client: AsyncClient) -> None:
    """It has to arrive before the stream opens.

    Once the 200 and its headers are sent, a refusal inside the generator is
    unreachable by the client — the definition of the bug this guards.
    """
    set_limiter(InMemoryRateLimiter(limit_per_minute=1))
    token = await _register_and_login(chat_client, "streamy@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    for _ in range(2):
        res = await chat_client.post(
            "/api/chat", json={"message": "hi", "conversation_id": 9999}, headers=headers
        )

    assert res.status_code == 429
    assert "text/event-stream" not in res.headers.get("content-type", "")
    assert "event: error" not in res.text


@pytest.mark.asyncio
async def test_429_carries_retry_after_and_a_saying_it(chat_client: AsyncClient) -> None:
    """A bare status code gives a client nothing to act on."""
    set_limiter(InMemoryRateLimiter(limit_per_minute=1))
    token = await _register_and_login(chat_client, "polite@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    for _ in range(2):
        res = await chat_client.post(
            "/api/chat", json={"message": "hi", "conversation_id": 9999}, headers=headers
        )

    assert res.status_code == 429
    assert int(res.headers["Retry-After"]) >= 1
    assert res.headers["X-RateLimit-Limit"] == "1"
    assert "too quickly" in res.json()["detail"]


@pytest.mark.asyncio
async def test_the_limit_is_per_user_not_per_process(chat_client: AsyncClient) -> None:
    """One user's flood must not lock everyone else out of the app."""
    set_limiter(InMemoryRateLimiter(limit_per_minute=1))
    noisy = await _register_and_login(chat_client, "noisy2@example.com")
    quiet = await _register_and_login(chat_client, "quiet2@example.com")

    for _ in range(2):
        await chat_client.post(
            "/api/chat",
            json={"message": "hi", "conversation_id": 9999},
            headers={"Authorization": f"Bearer {noisy}"},
        )

    res = await chat_client.post(
        "/api/chat",
        json={"message": "hi", "conversation_id": 9999},
        headers={"Authorization": f"Bearer {quiet}"},
    )

    assert res.status_code == 404, "the quiet user reached the normal path"


# ---------------------------------------------------------------------------
# Streaming.
#
# The assistant reply arrives as several `message` events, each carrying a
# fragment, and `done` still carries the complete authoritative reply. A client
# appends deltas as they land and reconciles against `done`, which is enough on
# its own to render the turn even if a delta never arrived.
#
# Persistence is still out of reach on SQLite (see the module docstring), so
# the two helpers that touch the JSONB tables are stubbed out. Everything
# asserted below is produced by the real `_run_chat` generator.
# ---------------------------------------------------------------------------


# An extraction complete enough to be handed straight to the rule engine: both
# safety flags answered, severity known, no red-flag symptom. Yields LOW and
# an 18-word recommendation, i.e. several fragments.
_TRIAGE_EXTRACTION = json.dumps(
    {
        "symptoms": ["itchy_eyes", "sneezing"],
        "severity": 3,
        "duration": "this morning",
        "possible_trigger": "pollen",
        "breathing_difficulty": False,
        "airway_swelling": False,
        "ready": True,
    }
)

# What the rule engine says about exactly that input, computed rather than
# pasted so the test cannot drift from the engine.
_LOW_RECOMMENDATION = triage.assess(
    triage.SymptomInput(symptoms=["itchy_eyes", "sneezing"], severity=3)
).recommendation


class _ScriptedLLM:
    """Answers every model call with the same canned string."""

    def __init__(self, response: str) -> None:
        self._response = response

    def complete(self, messages) -> str:
        return self._response


def _stub_turn_reply(reply: str):
    """A `run_turn` that answers with one fixed reply.

    The graph cannot produce an empty or whitespace-only reply on its own —
    `ask_question` falls back to a canned question and `triage_node` to the
    rule engine's text — so that state has to be injected to pin what the
    stream does with it.
    """

    def _run_turn(llm, state, user_message, progress=None):
        next_state = dict(state)
        next_state["assistant_reply"] = reply
        return next_state

    return _run_turn


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


async def _turn(
    client: AsyncClient, token: str, message: str = "my eyes itch"
) -> list[tuple[str, dict]]:
    res = await client.post(
        "/api/chat",
        json={"message": message},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200, res.text
    return _parse_sse(res.text)


@pytest.fixture
def stub_persistence(monkeypatch):
    """Take the JSONB tables out of the turn, keeping `_run_chat` itself real."""

    async def _load_state(session, conversation):
        return symptom_agent.initial_state([])

    async def _persist_turn(session, conversation, **kwargs):
        return None

    monkeypatch.setattr(chat_api, "_load_state", _load_state)
    monkeypatch.setattr(chat_api, "_persist_turn", _persist_turn)


@pytest.fixture
def scripted_llm(monkeypatch):
    def _install(response: str) -> None:
        monkeypatch.setitem(
            app.dependency_overrides, chat_api.get_llm, lambda: _ScriptedLLM(response)
        )

    return _install


@pytest.mark.asyncio
async def test_reply_arrives_as_several_deltas_not_one_blob(
    chat_client: AsyncClient, stub_persistence, scripted_llm
) -> None:
    token = await _register_and_login(chat_client, "stream@example.com")
    scripted_llm(_TRIAGE_EXTRACTION)

    events = await _turn(chat_client, token)
    messages = [data for name, data in events if name == "message"]

    assert len(messages) > 1, f"the reply arrived in one frame: {messages}"
    assert all(set(data) == {"delta"} for data in messages), (
        "a delta carries only text; `done` is what carries state"
    )
    assert all(data["delta"] for data in messages), "an empty delta is noise to filter"


@pytest.mark.asyncio
async def test_deltas_concatenate_to_the_done_message_exactly(
    chat_client: AsyncClient, stub_persistence, scripted_llm
) -> None:
    """The contract: what the client appended is what `done` says the reply is."""
    token = await _register_and_login(chat_client, "concat@example.com")
    scripted_llm(_TRIAGE_EXTRACTION)

    events = await _turn(chat_client, token)
    joined = "".join(data["delta"] for name, data in events if name == "message")
    done = _only_done(events)

    assert joined == done["message"]
    # And it is the rule engine's own text, not a re-worded or padded copy.
    assert joined == _LOW_RECOMMENDATION


@pytest.mark.asyncio
async def test_done_still_carries_every_field(
    chat_client: AsyncClient, stub_persistence, scripted_llm
) -> None:
    token = await _register_and_login(chat_client, "fields@example.com")
    scripted_llm(_TRIAGE_EXTRACTION)

    done = _only_done(await _turn(chat_client, token))

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
    assert done["message"] == _LOW_RECOMMENDATION
    assert isinstance(done["conversation_id"], int) and done["conversation_id"] > 0
    assert done["symptoms"] == ["itchy_eyes", "sneezing"]
    assert done["severity"] == 3
    assert done["duration"] == "this morning"
    assert done["possible_trigger"] == "pollen"
    assert done["breathing_difficulty"] is False
    assert done["airway_swelling"] is False
    assert done["triage_level"] == "LOW"
    assert done["triage_reasons"]
    assert done["triage_rule_version"] == triage.RULE_VERSION


@pytest.mark.asyncio
async def test_status_stages_stream_before_the_reply(
    chat_client: AsyncClient, stub_persistence, scripted_llm
) -> None:
    """Progress is still progressive, and it still leads the reply."""
    token = await _register_and_login(chat_client, "stages@example.com")
    scripted_llm(_TRIAGE_EXTRACTION)

    events = await _turn(chat_client, token)
    names = [name for name, _ in events]
    stages = [data["stage"] for name, data in events if name == "status"]

    first_message = names.index("message")
    assert names[:first_message] and set(names[:first_message]) == {"status"}, (
        f"progress must all precede the reply, got {names}"
    )
    assert stages[0] == "starting"
    assert "extracting" in stages
    assert "assessing" in stages
    assert stages[-1] == "saving"
    assert len(stages) >= 4, "the stages are separate events, not one batch at the end"
    assert names[-1] == "done"


@pytest.mark.asyncio
async def test_empty_reply_streams_no_deltas_and_still_terminates(
    chat_client: AsyncClient, stub_persistence, monkeypatch
) -> None:
    """Decision: an empty reply emits zero `message` events.

    `done` still carries `message: ""`, so the turn renders correctly with no
    delta at all; an empty delta would only give a client something to filter.
    """
    monkeypatch.setattr(chat_api.symptom_agent, "run_turn", _stub_turn_reply(""))

    token = await _register_and_login(chat_client, "empty@example.com")
    events = await _turn(chat_client, token)
    names = [name for name, _ in events]

    assert "message" not in names
    assert names[-1] == "done"
    assert _only_done(events)["message"] == ""
    assert "error" not in names


@pytest.mark.asyncio
async def test_whitespace_only_reply_is_delivered_verbatim(
    chat_client: AsyncClient, stub_persistence, monkeypatch
) -> None:
    """Whitespace is content here, not padding: it must survive, not be trimmed."""
    reply = "   \n "
    monkeypatch.setattr(chat_api.symptom_agent, "run_turn", _stub_turn_reply(reply))

    token = await _register_and_login(chat_client, "blank@example.com")
    events = await _turn(chat_client, token)
    deltas = [data["delta"] for name, data in events if name == "message"]

    assert deltas == [reply]
    assert _only_done(events)["message"] == reply


@pytest.mark.parametrize(
    "text",
    [
        "",
        " ",
        "   \n ",
        "one",
        "Are you having any difficulty breathing?",
        "  leading space then a handful of short words",
        "double  spaces  between  every  single  word  in  this  one",
        "a much longer reply that runs well past the fragment size "
        "so the cut lands in the middle of a sentence",
        "무술가 호흡곤란이 있어요",
        "tabs\tand\nnewlines\n\nmixed   in here with more than six words",
        "trailing spaces here   ",
    ],
)
def test_fragments_concatenate_back_to_the_original(text: str) -> None:
    parts = chat_api._fragments(text)

    assert "".join(parts) == text
    assert all(part in text for part in parts)
    assert all(parts), "an empty fragment is noise the client has to filter"


# ---------------------------------------------------------------------------
# ADR 0001: the verdict that gets persisted is re-derived, never copied.
# ---------------------------------------------------------------------------


def test_verdict_ignores_a_tampered_state_dict() -> None:
    """The whole point of `_verdict`.

    Copying `result["triage_level"]` into the database would let anything that
    can write the state dict choose a safety verdict. Poison it to LOW while the
    symptoms say otherwise; what lands must be the engine's answer, not LOW.
    """
    state: symptom_agent.AllergyState = {
        "triage_level": "LOW",
        "triage_reasons": ["looks fine to me"],
        "triage_rule_version": "forged-v0",
        "symptoms": ["itchy eyes"],
        "severity": 2,
        "breathing_difficulty": True,
        "airway_swelling": False,
    }

    level, reasons, version = chat_api._verdict(state)

    assert level == triage.TriageLevel.EMERGENCY.value
    assert version == triage.RULE_VERSION
    assert "forged" not in version
    assert "looks fine to me" not in reasons
    assert any("breathing" in r for r in reasons)


def test_verdict_does_not_invent_one_for_an_unanswered_turn() -> None:
    """A turn that only asked a follow-up question has no verdict to store.

    Re-deriving must not hand the engine symptoms the graph never confirmed and
    stamp a level on a turn where the user has not been told anything yet.
    """
    state: symptom_agent.AllergyState = {
        "triage_level": None,
        "symptoms": ["itchy eyes"],
        "severity": 9,
        "breathing_difficulty": True,
        "airway_swelling": True,
    }

    assert chat_api._verdict(state) == (None, [], None)


def test_verdict_agrees_with_the_engine_on_a_normal_turn() -> None:
    """Not every re-derivation is a disagreement.

    A benign turn must round-trip to the same level the graph already reported,
    otherwise the persistence path has quietly changed every verdict.
    """
    state: symptom_agent.AllergyState = {
        "triage_level": triage.TriageLevel.LOW.value,
        "symptoms": ["itchy eyes"],
        "severity": 3,
        "breathing_difficulty": False,
        "airway_swelling": False,
    }

    level, reasons, version = chat_api._verdict(state)

    assert level == triage.TriageLevel.LOW.value
    assert (
        reasons == triage.assess(triage.SymptomInput(symptoms=["itchy eyes"], severity=3)).reasons
    )
    assert version == triage.RULE_VERSION
