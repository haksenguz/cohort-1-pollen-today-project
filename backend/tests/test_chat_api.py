"""Auth boundary on the chat endpoint.

`POST /api/chat` used to take `user_id` from the request body, so any caller
could post as any user. These tests pin the identity to the bearer token and
pin conversation ownership.

The happy path is not exercised here: persisting a turn writes to
`symptom_events`, whose JSONB column SQLite cannot compile. Agent behaviour is
covered in `test_symptom_agent.py`.
"""

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.db import get_session
from app.core.rate_limit import InMemoryRateLimiter, set_limiter
from app.main import app
from app.models import Conversation, User, UserAllergy


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
