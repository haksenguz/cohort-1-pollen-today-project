"""Bring-your-own-LLM-key: the settings contract, encryption, and chat routing."""

import json
from types import SimpleNamespace

import pytest
from cryptography.fernet import InvalidToken
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api import chat as chat_api
from app.core import openai_client
from app.core.config import get_settings
from app.core.openai_client import LLMCallError, clear_client_cache, get_client_for_key
from app.models import UserLLMSetting
from app.services import llm_key
from app.services.llm_key import decrypt_api_key, encrypt_api_key
from app.services.privacy_service import delete_user_account

USER_KEY = "gsk_user_secret_WXYZ"
SERVER_KEY = "sk-server-test-key-0000"
PASSWORD = "correcthorse123"
GROQ_URL = "https://api.groq.com/openai/v1"

_EXTRACTION = json.dumps(
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


@pytest.fixture(autouse=True)
def _fresh_clients():
    clear_client_cache()
    yield
    clear_client_cache()


async def _login(client: AsyncClient, email: str) -> dict[str, str]:
    payload = {"email": email, "password": PASSWORD}
    await client.post("/api/auth/register", json=payload)
    res = await client.post("/api/auth/login", json=payload)
    headers = {"Authorization": f"Bearer {res.json()['access_token']}"}
    # A chat turn writes health data, so the consent gate runs first.
    await client.post("/api/privacy/consent", json={"granted": True}, headers=headers)
    return headers


class _Provider:
    """Stands in for the SDK client. `fail` is raised by every call."""

    def __init__(self, fail: Exception | None = None) -> None:
        self._fail = fail

    def complete(self, messages) -> str:
        if self._fail is not None:
            raise self._fail
        return _EXTRACTION

    def stream_complete(self, messages):
        if self._fail is not None:
            raise self._fail
        yield from ["Tell me ", "more."]


@pytest.fixture
def builds(monkeypatch):
    """Records every client the app builds, and what each was built with."""
    calls: list[dict] = []
    state: dict = {"fail": None}

    def _fake_build(*, api_key, base_url, model, max_tokens=0, timeout=0.0):
        calls.append({"api_key": api_key, "base_url": base_url, "model": model})
        return _Provider(fail=state["fail"])

    monkeypatch.setattr(openai_client, "_build_openai_client", _fake_build)
    settings = get_settings().model_copy(
        update={"openai_api_key": SERVER_KEY, "openai_base_url": "", "openai_model": "server-model"}
    )
    monkeypatch.setattr(openai_client, "get_settings", lambda: settings)
    monkeypatch.setattr(chat_api, "get_settings", lambda: settings)
    return SimpleNamespace(calls=calls, state=state)


def _sse_events(body: str) -> list[tuple[str, dict]]:
    events = []
    for frame in body.split("\n\n"):
        name, data = "", ""
        for line in frame.splitlines():
            if line.startswith("event: "):
                name = line[len("event: ") :]
            elif line.startswith("data: "):
                data = line[len("data: ") :]
        if name and data:
            events.append((name, json.loads(data)))
    return events


# --- settings contract -------------------------------------------------------


async def test_put_then_get_never_returns_the_key(client: AsyncClient) -> None:
    headers = await _login(client, "byok-a@example.com")
    body = {"api_key": USER_KEY, "provider": "groq"}

    put = await client.put("/api/users/me/llm", json=body, headers=headers)
    assert put.status_code == 200
    assert USER_KEY not in put.text
    assert put.json() == {
        "configured": True,
        "key_hint": "WXYZ",
        "provider": "groq",
        "base_url": GROQ_URL,
        "model": "openai/gpt-oss-20b",
    }

    get = await client.get("/api/users/me/llm", headers=headers)
    assert get.status_code == 200
    assert USER_KEY not in get.text
    assert get.json()["key_hint"] == "WXYZ"


async def test_get_when_unset_says_not_configured(client: AsyncClient) -> None:
    headers = await _login(client, "byok-empty@example.com")
    res = await client.get("/api/users/me/llm", headers=headers)
    assert res.json() == {
        "configured": False,
        "key_hint": "",
        "provider": None,
        "base_url": None,
        "model": None,
    }


async def test_base_url_is_never_taken_from_the_request(client: AsyncClient) -> None:
    headers = await _login(client, "byok-ssrf@example.com")
    body = {
        "api_key": USER_KEY,
        "provider": "openai",
        "base_url": "http://169.254.169.254/latest",
        "model": "gpt-4o",
    }
    res = await client.put("/api/users/me/llm", json=body, headers=headers)
    assert res.status_code == 200
    assert res.json()["base_url"] == "https://api.openai.com/v1"
    assert res.json()["model"] == "gpt-4o"


async def test_invalid_provider_is_422(client: AsyncClient) -> None:
    headers = await _login(client, "byok-prov@example.com")
    res = await client.put(
        "/api/users/me/llm", json={"api_key": USER_KEY, "provider": "anthropic"}, headers=headers
    )
    assert res.status_code == 422
    assert USER_KEY not in res.text


@pytest.mark.parametrize("key", ["QzT7", "x" * 600])
async def test_bad_key_length_is_422_and_never_echoes_the_key(
    client: AsyncClient, key: str
) -> None:
    headers = await _login(client, f"byok-len{len(key)}@example.com")
    res = await client.put(
        "/api/users/me/llm", json={"api_key": key, "provider": "groq"}, headers=headers
    )
    assert res.status_code == 422
    assert key not in res.text


async def test_delete_clears_the_key_and_returns_204(client: AsyncClient) -> None:
    headers = await _login(client, "byok-del@example.com")
    await client.put(
        "/api/users/me/llm", json={"api_key": USER_KEY, "provider": "groq"}, headers=headers
    )
    res = await client.delete("/api/users/me/llm", headers=headers)
    assert res.status_code == 204
    after = await client.get("/api/users/me/llm", headers=headers)
    assert after.json()["configured"] is False


async def test_a_user_cannot_see_another_users_key(client: AsyncClient) -> None:
    alice = await _login(client, "byok-alice@example.com")
    bob = await _login(client, "byok-bob@example.com")
    await client.put(
        "/api/users/me/llm", json={"api_key": USER_KEY, "provider": "groq"}, headers=alice
    )
    res = await client.get("/api/users/me/llm", headers=bob)
    assert res.json()["configured"] is False


async def test_settings_routes_need_auth(client: AsyncClient) -> None:
    assert (await client.get("/api/users/me/llm")).status_code == 401


# --- encryption --------------------------------------------------------------


async def test_key_is_stored_encrypted_and_round_trips(
    client: AsyncClient, session: AsyncSession
) -> None:
    headers = await _login(client, "byok-enc@example.com")
    await client.put(
        "/api/users/me/llm", json={"api_key": USER_KEY, "provider": "groq"}, headers=headers
    )
    row = (await session.execute(select(UserLLMSetting))).scalars().one()
    assert row.api_key_encrypted != USER_KEY
    assert USER_KEY not in row.api_key_encrypted
    assert decrypt_api_key(row.api_key_encrypted) == USER_KEY


def test_fernet_round_trip_and_secret_dependence(monkeypatch) -> None:
    token = encrypt_api_key(USER_KEY)
    assert token != USER_KEY
    assert decrypt_api_key(token) == USER_KEY

    other = get_settings().model_copy(update={"llm_key_secret": "a-different-secret-value-123"})
    monkeypatch.setattr(llm_key, "get_settings", lambda: other)
    with pytest.raises(InvalidToken):
        decrypt_api_key(token)


# --- chat routing ------------------------------------------------------------


async def test_chat_uses_the_users_key_when_set(client: AsyncClient, builds) -> None:
    headers = await _login(client, "byok-chat-user@example.com")
    await client.put(
        "/api/users/me/llm", json={"api_key": USER_KEY, "provider": "groq"}, headers=headers
    )
    res = await client.post("/api/chat", json={"message": "my eyes itch"}, headers=headers)
    assert res.status_code == 200
    assert {"api_key": USER_KEY, "base_url": GROQ_URL, "model": "openai/gpt-oss-20b"} in (
        builds.calls
    )
    assert all(call["api_key"] != SERVER_KEY for call in builds.calls)


async def test_chat_uses_the_server_key_when_the_user_has_none(client: AsyncClient, builds) -> None:
    headers = await _login(client, "byok-chat-server@example.com")
    res = await client.post("/api/chat", json={"message": "my eyes itch"}, headers=headers)
    assert res.status_code == 200
    assert builds.calls
    assert all(call["api_key"] == SERVER_KEY for call in builds.calls)


async def test_a_rejected_user_key_does_not_fall_back_to_the_server_key(
    client: AsyncClient, builds
) -> None:
    headers = await _login(client, "byok-reject@example.com")
    await client.put(
        "/api/users/me/llm", json={"api_key": USER_KEY, "provider": "groq"}, headers=headers
    )
    builds.state["fail"] = LLMCallError(
        "unavailable", "model rejected the request", rejected_key=True
    )
    res = await client.post("/api/chat", json={"message": "my eyes itch"}, headers=headers)
    errors = [data for name, data in _sse_events(res.text) if name == "error"]
    assert errors and errors[0]["kind"] == "user_key_rejected"
    assert "Settings" in errors[0]["detail"]
    assert all(call["api_key"] != SERVER_KEY for call in builds.calls)


async def test_an_undecryptable_user_key_refuses_instead_of_falling_back(
    client: AsyncClient, builds, monkeypatch
) -> None:
    headers = await _login(client, "byok-undec@example.com")
    await client.put(
        "/api/users/me/llm", json={"api_key": USER_KEY, "provider": "groq"}, headers=headers
    )
    rotated = get_settings().model_copy(update={"llm_key_secret": "rotated-secret-value-xyz-123"})
    monkeypatch.setattr(llm_key, "get_settings", lambda: rotated)
    res = await client.post("/api/chat", json={"message": "my eyes itch"}, headers=headers)
    errors = [data for name, data in _sse_events(res.text) if name == "error"]
    assert errors and errors[0]["kind"] == "user_key_rejected"
    assert builds.calls == []


def test_user_client_cache_is_bounded() -> None:
    for index in range(40):
        get_client_for_key(api_key=f"key-number-{index:04d}", base_url=GROQ_URL, model="m")
    assert len(openai_client._user_client_cache) <= 16


async def test_account_deletion_removes_the_key(client: AsyncClient, session: AsyncSession) -> None:
    headers = await _login(client, "byok-delete-acct@example.com")
    await client.put(
        "/api/users/me/llm", json={"api_key": USER_KEY, "provider": "groq"}, headers=headers
    )
    me = await client.get("/api/users/me", headers=headers)
    await delete_user_account(session, user_id=me.json()["id"])
    await session.commit()
    rows = (await session.execute(select(UserLLMSetting))).scalars().all()
    assert rows == []
