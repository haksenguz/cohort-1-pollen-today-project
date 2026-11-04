"""A conversation has a name, a truthful timestamp and a way to be found.

Three small gaps in the history list:

* every conversation was called "Untitled conversation", because nothing ever
  wrote `conversations.title`;
* `conversations.updated_at` stayed frozen at the creation timestamp, so
  anyone reading the column got a plausible wrong answer;
* there was no way to find a thread once the list grew.

The title is derived from the user's own first message. It costs nothing, adds
no latency to a turn, and stays in the language the user wrote in.
"""

import json
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

from app.api import chat as chat_api
from app.core.db import get_session
from app.core.rate_limit import InMemoryRateLimiter, set_limiter
from app.main import app
from app.models import Conversation, Message
from app.services import conversation_title

# An extraction the rule engine can answer, so a turn reaches a verdict and
# is stored like a real one.
_TRIAGE_EXTRACTION = json.dumps(
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
    """Answers every model call with the same canned extraction."""

    def __init__(self, response: str = _TRIAGE_EXTRACTION) -> None:
        self._response = response

    def complete(self, messages) -> str:
        return self._response


async def _login(client: AsyncClient, email: str) -> tuple[str, int]:
    payload = {"email": email, "password": "correcthorse123"}
    await client.post("/api/auth/register", json=payload)
    res = await client.post("/api/auth/login", json=payload)
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    # A chat turn writes health information, so the 민감정보 gate asks for
    # consent first. These tests are about the history, not the gate.
    await client.post("/api/privacy/consent", json={"granted": True}, headers=headers)
    me = await client.get("/api/users/me", headers=headers)
    return token, me.json()["id"]


def _install(monkeypatch, llm) -> None:
    monkeypatch.setitem(app.dependency_overrides, chat_api.get_llm, lambda: llm)


async def _search(client: AsyncClient, token: str, q: str | None = None) -> dict:
    params = {"q": q} if q is not None else {}
    res = await client.get(
        "/api/conversations", params=params, headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200, res.text
    return res.json()


async def _turn(client: AsyncClient, token: str, message: str, conversation_id: int | None = None):
    body: dict = {"message": message}
    if conversation_id is not None:
        body["conversation_id"] = conversation_id
    res = await client.post("/api/chat", json=body, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200, res.text
    return res.text


def _conversation_id(sse_body: str) -> int:
    for frame in sse_body.split("\n\n"):
        if '"conversation_id"' in frame:
            return json.loads(frame.split("data: ", 1)[1])["conversation_id"]
    raise AssertionError(f"no conversation id in {sse_body}")


# ---------------------------------------------------------------------------
# B5: the title.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_conversation_is_named_after_its_first_message(
    client: AsyncClient, session: AsyncSession, monkeypatch
) -> None:
    _install(monkeypatch, _ScriptedLLM())
    token, user_id = await _login(client, "titled@example.com")

    await _turn(client, token, "my eyes itch since this morning")

    conversation = await session.get(Conversation, 1)
    assert conversation.title == "my eyes itch since this morning"


@pytest.mark.asyncio
async def test_a_long_first_message_is_cut_to_a_title(
    client: AsyncClient, session: AsyncSession, monkeypatch
) -> None:
    """A title has to fit a list row, so it is cut, and the cut is marked."""
    _install(monkeypatch, _ScriptedLLM())
    token, _ = await _login(client, "longtitle@example.com")

    message = "my eyes itch and my nose runs and my throat feels dry since this morning"
    await _turn(client, token, message)

    conversation = await session.get(Conversation, 1)
    title = conversation.title
    assert title is not None
    assert title.endswith(conversation_title.ELLIPSIS)
    assert len(title) <= conversation_title.MAX_TITLE_LENGTH + len(conversation_title.ELLIPSIS)
    assert title.startswith("my eyes itch")
    # The cut lands on a word boundary, never in the middle of a word.
    assert not title[:-1].endswith(" ")


@pytest.mark.asyncio
async def test_a_title_collapses_the_whitespace_of_the_message(
    client: AsyncClient, session: AsyncSession, monkeypatch
) -> None:
    _install(monkeypatch, _ScriptedLLM())
    token, _ = await _login(client, "spaces@example.com")

    await _turn(client, token, "  my   eyes\titch \n badly  ")

    conversation = await session.get(Conversation, 1)
    assert conversation.title == "my eyes itch badly"


@pytest.mark.asyncio
async def test_a_title_keeps_the_language_the_user_wrote_in(
    client: AsyncClient, session: AsyncSession, monkeypatch
) -> None:
    _install(monkeypatch, _ScriptedLLM())
    token, _ = await _login(client, "korean@example.com")

    await _turn(client, token, "눈이 가려워요")

    conversation = await session.get(Conversation, 1)
    assert conversation.title == "눈이 가려워요"


@pytest.mark.asyncio
async def test_a_second_turn_leaves_the_title_alone(
    client: AsyncClient, session: AsyncSession, monkeypatch
) -> None:
    _install(monkeypatch, _ScriptedLLM())
    token, _ = await _login(client, "secondturn@example.com")

    first = _conversation_id(await _turn(client, token, "my eyes itch"))
    await _turn(client, token, "and now my nose runs", conversation_id=first)

    conversation = await session.get(Conversation, first)
    assert conversation.title == "my eyes itch"


def test_a_title_needs_no_model_call() -> None:
    """The title is derived, so it costs nothing and adds no latency."""
    assert conversation_title.derive_title("my eyes itch") == "my eyes itch"
    assert conversation_title.derive_title("   ") is None
    assert conversation_title.derive_title("") is None


# ---------------------------------------------------------------------------
# B-015a: the column.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_updated_at_column_moves_on_every_turn(
    client: AsyncClient, session: AsyncSession, monkeypatch
) -> None:
    """The column used to stay frozen at the creation timestamp."""
    _install(monkeypatch, _ScriptedLLM())
    token, _ = await _login(client, "stamped@example.com")

    first = _conversation_id(await _turn(client, token, "my eyes itch"))
    conversation = await session.get(Conversation, first)
    first_stamp = conversation.updated_at
    assert first_stamp >= conversation.created_at

    await _turn(client, token, "and now my nose runs", conversation_id=first)
    await session.refresh(conversation)

    assert conversation.updated_at > first_stamp, (
        "the column has to follow the last turn, not the creation of the thread"
    )


@pytest.mark.asyncio
async def test_the_list_still_reports_the_last_activity(
    client: AsyncClient, session: AsyncSession, monkeypatch
) -> None:
    """The derived ordering and the column have to agree."""
    _install(monkeypatch, _ScriptedLLM())
    token, _ = await _login(client, "agree@example.com")

    conversation_id = _conversation_id(await _turn(client, token, "my eyes itch"))
    await _turn(client, token, "and now my nose runs", conversation_id=conversation_id)

    body = await _search(client, token)
    summary = next(c for c in body["conversations"] if c["id"] == conversation_id)

    assert summary["updated_at"] != summary["created_at"]
    assert summary["title"] == "my eyes itch"


# ---------------------------------------------------------------------------
# B7: the search.
# ---------------------------------------------------------------------------


async def _seed(session: AsyncSession, user_id: int, title: str, messages: list[str]) -> int:
    conversation = Conversation(user_id=user_id, status="ACTIVE", title=title)
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    for index, content in enumerate(messages):
        session.add(
            Message(
                conversation_id=conversation.id,
                role="USER" if index % 2 == 0 else "ASSISTANT",
                content=content,
            )
        )
    await session.commit()
    return conversation.id


@pytest.mark.asyncio
async def test_a_search_finds_a_conversation_by_its_title(
    client: AsyncClient, session: AsyncSession
) -> None:
    token, user_id = await _login(client, "searchtitle@example.com")
    hayfever = await _seed(session, user_id, "hay fever in April", ["it started in April"])
    await _seed(session, user_id, "a chest thing", ["unrelated"])

    body = await _search(client, token, "hay fever")

    assert [c["id"] for c in body["conversations"]] == [hayfever]


@pytest.mark.asyncio
async def test_a_search_finds_a_conversation_by_what_was_said(
    client: AsyncClient, session: AsyncSession
) -> None:
    token, user_id = await _login(client, "searchbody@example.com")
    found = await _seed(session, user_id, "untitled thread", ["my nose runs every morning"])
    await _seed(session, user_id, "another thread", ["nothing to see here"])

    body = await _search(client, token, "nose runs")

    assert [c["id"] for c in body["conversations"]] == [found]


@pytest.mark.asyncio
async def test_a_search_ignores_the_case(client: AsyncClient, session: AsyncSession) -> None:
    token, user_id = await _login(client, "searchcase@example.com")
    hayfever = await _seed(session, user_id, "Hay Fever", ["Sneezing in April"])

    body = await _search(client, token, "hay fever")

    assert [c["id"] for c in body["conversations"]] == [hayfever]


@pytest.mark.asyncio
async def test_an_empty_search_returns_everything(
    client: AsyncClient, session: AsyncSession
) -> None:
    token, user_id = await _login(client, "searchempty@example.com")
    await _seed(session, user_id, "one", ["first"])
    await _seed(session, user_id, "two", ["second"])

    empty = await _search(client, token, "")
    absent = await _search(client, token)

    assert len(empty["conversations"]) == 2
    assert absent == empty, "an empty search is the same as no search"


@pytest.mark.asyncio
async def test_a_search_never_reaches_another_users_conversation(
    client: AsyncClient, session: AsyncSession
) -> None:
    token, user_id = await _login(client, "searchmine@example.com")
    _, other_id = await _login(client, "searchtheirs@example.com")

    mine = await _seed(session, user_id, "my hay fever", ["my own symptoms"])
    await _seed(session, other_id, "their hay fever", ["their own symptoms"])

    body = await _search(client, token, "hay fever")

    assert [c["id"] for c in body["conversations"]] == [mine]
    assert "their own symptoms" not in body["conversations"][0]["last_message"]


@pytest.mark.asyncio
async def test_a_search_keeps_the_response_shape(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The body is the same shape with or without a search."""
    token, user_id = await _login(client, "searchshape@example.com")
    await _seed(session, user_id, "a thread", ["something"])

    body = await _search(client, token, "thread")

    assert set(body) == {"conversations"}
    assert set(body["conversations"][0]) == {
        "id",
        "title",
        "created_at",
        "updated_at",
        "last_message",
        "message_count",
    }
