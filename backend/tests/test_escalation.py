"""The scope boundary the model is not allowed to cross (D11).

Two guarantees, both of which are stronger than a prompt instruction:

1. **A crisis message never reaches the model.** It cannot be answered with a
   pollen reading, and no phrasing gets past the check.
2. **The app never claims a human will read it.** There is no staffed team, so
   the copy must say so. An app that implies a human is watching spends the
   exact moment someone reached out.

The false-positive tests matter as much as the true-positive ones. A boundary
that fires on "my eyes itch" does not protect anyone: it refuses everything and
the app stops working, which is its own safety failure.
"""

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import chat as chat_api
from app.main import app
from app.services import escalation

# The end-to-end case runs the real request path, which calls _load_state and so
# needs the `conversations` table. It used to run on the Postgres gate only,
# because the local SQLite fixture did not create that table. The schema is now
# whole on both engines, so this one runs locally too.


async def _register(client: AsyncClient, email: str) -> str:
    payload = {"email": email, "password": "correcthorse123"}
    await client.post("/api/auth/register", json=payload)
    res = await client.post("/api/auth/login", json=payload)
    return res.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize(
    "message",
    [
        "my eyes itch",
        "my eyes are itchy and I keep sneezing",
        "my throat is closing up",
        "pollen is killing the plants today",
        "can I take my usual tablet",
        "",
    ],
)
def test_ordinary_symptom_messages_are_not_treated_as_out_of_scope(message: str) -> None:
    """The boundary must not fire on the traffic it exists to protect.

    A pattern ending in a stray `|`, or a term loose enough to match "itchy",
    turns every message into a refusal. The app then answers nothing at all,
    which is a safety failure wearing the costume of a safety feature.
    """
    assert escalation.assess(message).verdict == "in_scope", message


@pytest.mark.parametrize(
    "message",
    [
        "I want to die",
        "I want to kill myself",
        "I have been thinking about suicide",
        "I want to end my life",
        "self harm again",
        "자살할까 생각 중",
        "요즘 자해하고 싶어요",
        "목숨을 끊을까 고민 중",
        "죽고 싶어요",
    ],
)
def test_a_crisis_disclosure_is_caught(message: str) -> None:
    assert escalation.assess(message).verdict == "crisis", message


@pytest.mark.parametrize(
    "message",
    [
        "무슨 질병일까요",
        "진단해줘",
        "약 얼마나 먹어야 되나요",
        "처방전 좀 봐줘",
        "이 약이 맞는지 알려줘",
        "검사 결과 해석해줘",
        "can you diagnose me",
        "how much should I take",
        "what dose is right for me",
    ],
)
def test_a_diagnosis_or_dosage_request_is_refused(message: str) -> None:
    assert escalation.assess(message).verdict == "out_of_scope", message


def test_a_crisis_outranks_an_out_of_scope_request() -> None:
    """Someone in crisis who also asks a medical question gets the crisis reply.

    Ordering matters: the other way round a person saying "how much should I
    take, I want to die" is told they are asking the wrong question, which is
    both useless and fairly grim.
    """
    verdict = escalation.assess("약 얼마나 먹어야 되나요, 죽고 싶어요").verdict
    assert verdict == "crisis"


def test_the_crisis_reply_says_no_one_is_reading() -> None:
    """The single most important sentence in the app.

    There is no staffed team. Promising a reply that never comes is worse than
    silence, because it spends the moment the user reached out.
    """
    reply = escalation.crisis_reply(escalation.assess("I want to die"))

    assert "1393" in reply and "1333" in reply, "the real crisis lines must be offered"
    assert "119" in reply
    assert "nobody" in reply.lower()
    assert "not a team" in reply.lower() or "no one will reply" in reply.lower()


def test_the_out_of_scope_reply_signposts_instead_of_only_refusing() -> None:
    """A bare "I can't help" strands the user.

    The app can still do its actual job — how urgent this is, today's pollen,
    a nearby clinic — so it says that rather than stopping at the refusal.
    """
    reply = escalation.out_of_scope_reply()

    assert "clinic" in reply.lower()
    assert "pollen" in reply.lower()
    assert "doctor" in reply.lower()


def test_no_crisis_pattern_matches_the_empty_string() -> None:
    """A trailing `|` in a VERBOSE pattern adds an empty branch.

    That branch matches at position 0, so the pattern fires on every message
    and the whole feature silently blocks all traffic.
    """
    for pattern in (escalation._CRISIS_PATTERNS, escalation._OUT_OF_SCOPE_PATTERNS):
        assert pattern.search("") is None, "an empty alternative is matching empty input"


@pytest_asyncio.fixture
async def chat_client(session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """The shared session, exposed as an HTTP client.

    `chat_client` is local to test_chat_api.py, and the crisis path runs the
    real request path including `_load_state`, so it needs the conversations
    table. On Postgres the shared fixture has it; on SQLite this test is
    skipped for that reason.
    """
    from app.core.db import get_session

    async def _get_session_override():
        yield session

    app.dependency_overrides[get_session] = _get_session_override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_a_crisis_turn_never_calls_the_model(chat_client: AsyncClient) -> None:
    """The end-to-end proof: the model object must never be asked anything.

    Note what this does *not* assert: that the model is never constructed.
    FastAPI resolves every dependency at request entry, so `get_llm` runs
    before `_run_chat` is entered and the object exists whatever the message
    says. What matters is that no completion is ever requested.
    """

    class _NeverCalled:
        async def complete(self, *_a, **_k):
            raise AssertionError("the model must not be asked about a crisis disclosure")

        async def complete_with_tools(self, *_a, **_k):
            raise AssertionError("the model must not be asked about a crisis disclosure")

        def __getattr__(self, _name):
            raise AssertionError("the model must not be touched for a crisis disclosure")

    app.dependency_overrides[chat_api.get_llm] = lambda: _NeverCalled()
    token = await _register(chat_client, "crisis@example.com")

    res = await chat_client.post(
        "/api/chat", json={"message": "요즘 죽고 싶어요"}, headers=_auth(token)
    )

    assert res.status_code == 200
    assert "1393" in res.text
    assert "nobody" in res.text.lower()
