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
import re
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import select

from app.agents import symptom_agent
from app.api import chat as chat_api
from app.core.db import get_session
from app.core.openai_client import ToolCall, ToolTurn
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


async def _register_and_login(
    client: AsyncClient,
    email: str,
    *,
    latitude: float | None = None,
    longitude: float | None = None,
) -> str:
    payload = {"email": email, "password": "correcthorse123"}
    if latitude is not None:
        payload["latitude"] = latitude
    if longitude is not None:
        payload["longitude"] = longitude
    await client.post("/api/auth/register", json=payload)
    res = await client.post("/api/auth/login", json={"email": email, "password": "correcthorse123"})
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
    unreachable by the client â€” the definition of the bug this guards.
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

    The graph cannot produce an empty or whitespace-only reply on its own â€”
    `ask_question` falls back to a canned question and `triage_node` to the
    rule engine's text â€” so that state has to be injected to pin what the
    stream does with it.

    Takes `registry` and ignores it, like the real `run_turn` it stands in for.
    """

    def _run_turn(llm, state, user_message, progress=None, registry=None):
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
        "ë¬´ìˆ ê°€ í˜¸í¡ê³¤ëž€ì´ ìžˆì–´ìš”",
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


# ---------------------------------------------------------------------------
# Tool activity on the stream.
#
# The agent runs a bounded reason -> act -> observe loop, and a turn may call a
# tool zero times or several. Each call it does make reports `running` the
# moment the model asks for it, then exactly one of `done` / `error` when it
# settles. The terminal `done` event repeats the whole list as an audit trail,
# so a client that missed a live frame can still show what ran.
#
# These drive the real graph, the real tool node and the real `_observe`; only
# persistence is stubbed, as above.
# ---------------------------------------------------------------------------


# Sample directory data, exactly the shape the tool registry promises. It comes
# from a fake executor, never from a real lookup, so nothing here is clinical.
_SAMPLE_CLINICS = [
    {"name": "Han River Clinic", "address": "Seongdong-gu", "distance_m": 900, "rank": 1},
    {"name": "Seoul Allergy Centre", "address": "Jongno-gu", "distance_m": 2100, "rank": 2},
]

_TOOL_NAME = "find_nearby_care"
_TOOL_CALL_ID = "call_abc123"
_TOOL_ARGS = {"radius_m": 3000}


class _ToolScriptedLLM:
    """Asks for one tool on the first tool-enabled call, then answers.

    The second call returns no `tool_calls`, which is what ends the loop the way
    a model that has seen its observation and is ready to reply would end it.
    """

    def __init__(
        self,
        extraction: str,
        name: str = _TOOL_NAME,
        call_id: str = _TOOL_CALL_ID,
        arguments: dict | None = None,
    ) -> None:
        self._extraction = extraction
        self._name = name
        self._call_id = call_id
        self._arguments = arguments if arguments is not None else dict(_TOOL_ARGS)
        self._tool_turns = 0

    def complete(self, messages) -> str:
        return self._extraction

    def complete_with_tools(self, messages, tools):
        self._tool_turns += 1
        if self._tool_turns > 1:
            return ToolTurn(content="looking that up")
        return ToolTurn(
            tool_calls=(ToolCall(id=self._call_id, name=self._name, arguments=self._arguments),)
        )


def _tool_registry(execute, *, wired: bool = True) -> symptom_agent.ToolRegistry:
    """One read-only lookup tool, with no safety field anywhere in its input or
    output schema â€” the ADR 0001 boundary."""
    return symptom_agent.ToolRegistry(
        [
            symptom_agent.ToolDefinition(
                name=_TOOL_NAME,
                description="Look up nearby clinics. Read-only: it changes nothing.",
                parameters={
                    "type": "object",
                    "properties": {"radius_m": {"type": "integer"}},
                    "required": [],
                },
                result_schema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "distance_m": {"type": "integer"},
                    },
                },
                execute=execute,
                wired=wired,
            )
        ]
    )


@pytest.fixture
def tool_registry(monkeypatch):
    def _install(registry) -> None:
        # The real factory takes the caller's resolved origin; these tests
        # supply their own registry and so ignore it.
        monkeypatch.setattr(symptom_agent, "default_tool_registry", lambda origin=None: registry)

    return _install


@pytest.fixture
def tool_llm(monkeypatch):
    def _install(fake) -> None:
        monkeypatch.setitem(app.dependency_overrides, chat_api.get_llm, lambda: fake)

    return _install


def _tool_events(events: list[tuple[str, dict]]) -> list[dict]:
    return [data for name, data in events if name == "tool"]


@pytest.mark.asyncio
async def test_a_tool_call_reports_running_with_its_arguments(
    chat_client: AsyncClient, stub_persistence, tool_registry, tool_llm
) -> None:
    """The user has to watch the lookup start, not learn about it afterwards."""
    tool_registry(_tool_registry(lambda arguments: _SAMPLE_CLINICS))
    tool_llm(_ToolScriptedLLM(_TRIAGE_EXTRACTION))

    token = await _register_and_login(chat_client, "toolrun@example.com")
    events = await _turn(chat_client, token)
    tools = _tool_events(events)
    names = [name for name, _ in events]

    assert [data["status"] for data in tools] == ["running", "done"]
    assert all(data["name"] == _TOOL_NAME for data in tools)
    assert all(data["id"] == _TOOL_CALL_ID for data in tools)
    assert tools[0]["args"] == _TOOL_ARGS
    assert "args" not in tools[1], "arguments are reported when the call starts, not when it ends"
    # Emitted while the turn is still running, not batched after the reply.
    assert names.index("tool") < names.index("message")


@pytest.mark.asyncio
async def test_done_repeats_every_tool_call_as_an_audit_trail(
    chat_client: AsyncClient, stub_persistence, tool_registry, tool_llm
) -> None:
    """A client that missed a live frame can still render what ran.

    The id is what correlates the two, so the audit row and the live event for
    one call have to carry the same one.
    """
    tool_registry(_tool_registry(lambda arguments: _SAMPLE_CLINICS))
    tool_llm(_ToolScriptedLLM(_TRIAGE_EXTRACTION))

    token = await _register_and_login(chat_client, "audit@example.com")
    events = await _turn(chat_client, token)
    running = _tool_events(events)[0]
    audit = _only_done(events)["tool_calls"]

    assert len(audit) == 1
    entry = audit[0]
    assert entry["id"] == running["id"]
    assert entry["name"] == _TOOL_NAME
    assert entry["status"] == "done"
    assert entry["summary"] == "Found 2 results."
    assert "args" not in entry


@pytest.mark.asyncio
async def test_a_turn_with_no_tool_sends_no_tool_calls_key_at_all(
    chat_client: AsyncClient, stub_persistence, scripted_llm
) -> None:
    """No tool ran, so there is nothing to audit.

    An absent key and an empty list are different states on the client side, and
    `done` stays additive: a client that predates this change must see exactly
    the payload it saw before.
    """
    token = await _register_and_login(chat_client, "notools@example.com")
    scripted_llm(_TRIAGE_EXTRACTION)

    events = await _turn(chat_client, token)
    done = _only_done(events)

    assert _tool_events(events) == []
    assert "tool_calls" not in done, "an absent key and an empty array are not the same state"


@pytest.mark.asyncio
async def test_a_failed_tool_says_so_in_plain_words_and_leaks_nothing(
    chat_client: AsyncClient, stub_persistence, tool_registry, tool_llm
) -> None:
    """A failed lookup must be visibly failed, not quietly empty.

    The exception carries a connection string and a traceback's worth of
    detail; none of it belongs on the user's screen.
    """

    def _explode(arguments):
        raise RuntimeError("connection refused: postgres://user:hunter2@10.0.0.5:5432/nav")

    tool_registry(_tool_registry(_explode))
    tool_llm(_ToolScriptedLLM(_TRIAGE_EXTRACTION))

    token = await _register_and_login(chat_client, "toolerr@example.com")
    events = await _turn(chat_client, token)

    assert [data["status"] for data in _tool_events(events)] == ["running", "error"]
    entry = _only_done(events)["tool_calls"][0]

    assert entry["status"] == "error"
    assert entry["summary"] == "That lookup failed."
    assert "\n" not in entry["summary"], "one line, not a paragraph"
    for leak in ("Traceback", "RuntimeError", "postgres://", "hunter2", "10.0.0.5", "{", "error:"):
        assert leak not in entry["summary"]


@pytest.mark.asyncio
async def test_a_tool_with_no_backend_says_so_instead_of_inventing(
    chat_client: AsyncClient, stub_persistence, tool_registry, tool_llm
) -> None:
    """An unwired lookup is reported as unavailable, never as an empty result.

    Reporting "0 results" for a tool that never ran would tell the user there
    are no clinics nearby, which is a claim nobody can support.
    """

    def _must_not_run(arguments):
        raise AssertionError("an unwired tool must not reach its executor")

    tool_registry(_tool_registry(_must_not_run, wired=False))
    tool_llm(_ToolScriptedLLM(_TRIAGE_EXTRACTION))

    token = await _register_and_login(chat_client, "unwired@example.com")
    events = await _turn(chat_client, token)

    entry = _only_done(events)["tool_calls"][0]
    assert entry["status"] == "error"
    assert entry["summary"] == "That lookup is not available right now."


@pytest.mark.asyncio
async def test_a_successful_tool_publishes_its_rows_on_the_wire(
    chat_client: AsyncClient, stub_persistence, tool_registry, tool_llm
) -> None:
    """The client renders from `result`, not from the sentence about it.

    This is the gap that let a "done" report go out claiming the payload was
    on the wire while the parsed rows were decoded, counted and thrown away.
    The user would have seen a sentence about clinics and no clinics.
    """
    clinics = [
        {
            "name": "Seoul National Hospital",
            "address": "Jongno",
            "distance_m": 1240,
            "phone": "02-000-0000",
            "rank": 1,
        },
        {
            "name": "Boramae Clinic",
            "address": "Seongbuk",
            "distance_m": 2310,
            "phone": None,
            "rank": 2,
        },
    ]

    tool_registry(_tool_registry(lambda arguments: clinics))
    tool_llm(_ToolScriptedLLM(_TRIAGE_EXTRACTION))

    token = await _register_and_login(chat_client, "rows@example.com")
    events = await _turn(chat_client, token)

    settled = [d for d in _tool_events(events) if d["status"] == "done"]
    assert len(settled) == 1, f"expected one settled tool event, got {len(settled)}"

    payload = settled[0]
    assert payload["summary"] == "Found 2 results."
    assert payload["result"] == {"clinics": clinics}, (
        "the rows themselves have to reach the client, not just a count of them"
    )

    # The audit row carries the same thing, so a resumed view can render too.
    entry = _only_done(events)["tool_calls"][0]
    assert entry["result"] == {"clinics": clinics}


@pytest.mark.asyncio
async def test_a_failed_tool_publishes_no_rows_at_all(
    chat_client: AsyncClient, stub_persistence, tool_registry, tool_llm
) -> None:
    """No payload on `error` â€” a failure must not render as an empty list.

    An empty `clinics` array on screen says "there are none nearby". That is
    a claim nobody can support, and it is the claim the user is most likely
    to act on.
    """

    def _boom(arguments):
        raise RuntimeError("provider unreachable")

    tool_registry(_tool_registry(_boom))
    tool_llm(_ToolScriptedLLM(_TRIAGE_EXTRACTION))

    token = await _register_and_login(chat_client, "failedrows@example.com")
    events = await _turn(chat_client, token)

    entry = _only_done(events)["tool_calls"][0]
    assert entry["status"] == "error"
    assert "result" not in entry

    settled = [d for d in _tool_events(events) if d["status"] == "error"]
    assert settled and all("result" not in d for d in settled)


@pytest.mark.asyncio
async def test_a_running_tool_event_carries_no_rows_yet(
    chat_client: AsyncClient, stub_persistence, tool_registry, tool_llm
) -> None:
    """`running` reports what was asked for, never what came back."""

    tool_registry(_tool_registry(lambda arguments: [{"name": "X", "rank": 1}]))
    tool_llm(_ToolScriptedLLM(_TRIAGE_EXTRACTION))

    token = await _register_and_login(chat_client, "runningrows@example.com")
    events = await _turn(chat_client, token)

    running = [d for d in _tool_events(events) if d["status"] == "running"]
    assert running, "the running event is what tells the user something is happening"
    assert all("result" not in d for d in running)
    assert all(d["args"] == _TOOL_ARGS for d in running)


@pytest.mark.asyncio
async def test_a_tool_with_no_agreed_result_key_publishes_nothing(
    chat_client: AsyncClient, stub_persistence, tool_registry, tool_llm
) -> None:
    """An unknown tool gets no payload rather than an invented key.

    The wire shape is a contract. Guessing `results` or `data` for a tool
    nobody agreed a key for is how a client ends up reading `undefined`.
    """
    registry = symptom_agent.ToolRegistry(
        [
            symptom_agent.ToolDefinition(
                name="some_other_lookup",
                description="A lookup nobody agreed a result key for.",
                parameters={"type": "object", "properties": {}, "required": []},
                result_schema={"type": "object", "properties": {}},
                execute=lambda arguments: [{"name": "X", "rank": 1}],
                wired=True,
            )
        ]
    )
    tool_registry(registry)
    tool_llm(_ToolScriptedLLM(_TRIAGE_EXTRACTION, name="some_other_lookup"))

    token = await _register_and_login(chat_client, "nokey@example.com")
    events = await _turn(chat_client, token)

    entry = _only_done(events)["tool_calls"][0]
    assert entry["status"] == "done"
    assert entry["summary"] == "Found 1 results."
    assert "result" not in entry


@pytest.mark.asyncio
async def test_no_tool_identifier_ever_reaches_the_user(
    chat_client: AsyncClient, stub_persistence, tool_registry, tool_llm
) -> None:
    """A snake_case name on a safety screen is the same leak as a raw exception.

    The observation names no tool at all — the transcript hands the model its
    own `name` next to the observation — but `summary` is read by a person. A
    user must never be told `find_nearby_hospitals` is unavailable - they do not
    know what that is, and an identifier on that line reads as a broken app
    rather than a broken lookup.
    """

    def _boom(arguments):
        raise RuntimeError("connection refused: postgres://user:pw@10.0.0.5:5432/nav")

    tool_registry(_tool_registry(_boom))
    tool_llm(_ToolScriptedLLM(_TRIAGE_EXTRACTION))

    token = await _register_and_login(chat_client, "noleak@example.com")
    events = await _turn(chat_client, token)

    for data in _tool_events(events):
        # `name` and `args` on the running event are the pinned contract - the
        # client renders the strip from them. Only `summary` is prose written
        # for a person, and only it can leak an identifier.
        summary = data.get("summary") or ""
        # Both spellings: the raw name, and the spaced form a naive
        # underscore-strip would leave behind. Checking only the first is how
        # this test passed while the leak was still on screen.
        for form in (_TOOL_NAME, _TOOL_NAME.replace("_", " ")):
            assert form.lower() not in summary.lower(), (
                f"tool name leaked to the user as {form!r}: {summary}"
            )
        assert not re.search(r"\b[a-z][a-z0-9]*_[a-z0-9_]+\b", summary), (
            f"an identifier leaked into a user-facing line: {summary}"
        )
        if data["status"] == "error":
            assert summary, "a failure the user can see must say something"


@pytest.mark.asyncio
async def test_no_tool_payload_carries_a_safety_field(
    chat_client: AsyncClient, stub_persistence, tool_registry, tool_llm
) -> None:
    """ADR 0001, on the wire this time.

    The registry guard pins what a tool may declare; this pins what actually
    reaches the client, so no tool can smuggle an urgency judgement out through
    an argument or a summary.
    """
    tool_registry(_tool_registry(lambda arguments: _SAMPLE_CLINICS))
    tool_llm(_ToolScriptedLLM(_TRIAGE_EXTRACTION))

    token = await _register_and_login(chat_client, "boundary@example.com")
    events = await _turn(chat_client, token)

    banned = {"triage_level", "triage_severity", "triage_verdict"}
    payloads = list(_tool_events(events)) + list(_only_done(events)["tool_calls"])
    for payload in payloads:
        assert not set(payload) & banned
        assert not set(payload.get("args") or {}) & banned


# ---------------------------------------------------------------------------
# B3: the shipped clinic lookup, end to end over the wire.
#
# These run the real `default_tool_registry`, not a stand-in, because the whole
# point of B3 is what that factory does. Only the provider call is faked - the
# executor, the refusal, the observation and the settle all run for real.
# ---------------------------------------------------------------------------


def _shipped_tool_llm() -> _ToolScriptedLLM:
    return _ToolScriptedLLM(_TRIAGE_EXTRACTION, name="find_nearby_hospitals", arguments={})


@pytest.fixture
def fake_search(monkeypatch):
    """Replace the Naver call itself; everything either side of it stays real."""
    calls: list[tuple] = []

    def _install(*, clinics=None, provider_available=True):
        def _search(origin, *, specialty, location_query):
            calls.append((origin, specialty, location_query))
            return symptom_agent.NearbyCareSearch(
                clinics=clinics if clinics is not None else [],
                provider_available=provider_available,
            )

        monkeypatch.setattr(symptom_agent, "_nearby_care_search", _search)
        return calls

    return _install


@pytest.mark.asyncio
async def test_a_missing_location_reaches_the_user_as_no_location(
    chat_client: AsyncClient, stub_persistence, tool_llm
) -> None:
    """The one failure a user can fix in five seconds must not read as a dead end.

    A fresh account has no coordinates. The turn must still do the lookup, and
    must say *why* it produced nothing - not "there are no clinics nearby",
    which is a claim about the user's city that nothing backs.
    """
    tool_llm(_shipped_tool_llm())

    token = await _register_and_login(chat_client, "nolocation@example.com")
    events = await _turn(chat_client, token)

    settled = _tool_events(events)[-1]
    assert settled["status"] == "error"
    assert settled["code"] == symptom_agent.NO_LOCATION
    assert "result" not in settled, "a refused lookup has no rows to publish"
    assert "does not mean there are no clinics" in settled["summary"]
    # The code is for the client, not the reader.
    assert symptom_agent.NO_LOCATION not in settled["summary"]


@pytest.mark.asyncio
async def test_a_dead_provider_is_not_reported_as_no_nearby_clinics(
    chat_client: AsyncClient, stub_persistence, tool_llm, fake_search
) -> None:
    """A provider that was never reached is not an empty result set."""
    fake_search(provider_available=False)
    tool_llm(_shipped_tool_llm())

    # Registered with a location, or the tool refuses before it ever reaches
    # the provider and this would pass for the wrong reason.
    token = await _register_and_login(
        chat_client, "providerdown@example.com", latitude=37.5665, longitude=126.978
    )
    events = await _turn(chat_client, token)

    settled = _tool_events(events)[-1]
    assert settled["status"] == "error"
    assert settled["code"] == symptom_agent.PROVIDER_UNAVAILABLE
    assert "result" not in settled


@pytest.mark.asyncio
async def test_a_saved_location_is_resolved_by_the_server_and_never_by_the_model(
    chat_client: AsyncClient, stub_persistence, tool_llm, fake_search
) -> None:
    """The executor searches around the user's saved home, not around nothing.

    The model was asked for `latitude`/`longitude` it cannot know, so it never
    called the tool at all. The origin now arrives from the profile, and the
    arguments the model does send are only the optional narrowing.
    """
    calls = fake_search(clinics=_SAMPLE_CLINICS)
    tool_llm(_shipped_tool_llm())

    token = await _register_and_login(
        chat_client, "homebody@example.com", latitude=37.5665, longitude=126.978
    )
    events = await _turn(chat_client, token)

    origin, specialty, location_query = calls[0]
    assert (origin.latitude, origin.longitude) == (37.5665, 126.978)
    assert specialty is None and location_query is None

    settled = _tool_events(events)[-1]
    assert settled["status"] == "done"
    assert [row["name"] for row in settled["result"]["clinics"]] == [
        row["name"] for row in _SAMPLE_CLINICS
    ]


@pytest.mark.asyncio
async def test_the_user_is_told_to_search_nothing_only_when_nothing_was_searched(
    chat_client: AsyncClient, stub_persistence, tool_llm, fake_search
) -> None:
    """A search that ran and came back empty is allowed to say so.

    The mirror of `no_location`: the two must not collapse into one, because
    one means "go and set your location" and the other means "try a different
    clinic or call an ambulance".
    """
    fake_search(clinics=[])
    tool_llm(_shipped_tool_llm())

    token = await _register_and_login(
        chat_client, "empty@example.com", latitude=37.5665, longitude=126.978
    )
    events = await _turn(chat_client, token)

    settled = _tool_events(events)[-1]
    assert settled["status"] == "done"
    assert settled["result"]["clinics"] == []
    assert settled["result"]["provider_available"] is True
    assert settled.get("code") is None


@pytest.mark.asyncio
async def test_half_a_location_is_treated_as_none(chat_session: AsyncSession) -> None:
    """A latitude with no longitude would search somewhere in the ocean.

    Both fields exist independently on `users` and a partial save is a normal
    thing for a settings form to produce. A wrong clinic on a safety path is
    worse than no clinic, so an incomplete pair is refused rather than
    completed with a default.
    """
    both = User(email="both@example.com", password_hash="x", latitude=37.5, longitude=127.0)
    half = User(email="half@example.com", password_hash="x", latitude=37.5, longitude=None)
    neither = User(email="neither@example.com", password_hash="x")
    chat_session.add_all([both, half, neither])
    await chat_session.commit()

    resolved = await chat_session.execute(select(User).where(User.email == "both@example.com"))
    assert (
        await chat_api._origin_for(chat_session, resolved.scalars().first().id)
    ).latitude == 37.5

    for email in ("half@example.com", "neither@example.com", "missing@example.com"):
        found = await chat_session.execute(select(User).where(User.email == email))
        user = found.scalars().first()
        user_id = user.id if user else 999_999
        assert await chat_api._origin_for(chat_session, user_id) is None, email
