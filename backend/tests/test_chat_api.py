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
from app.main import app
from app.models import Conversation, User, UserAllergy


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
