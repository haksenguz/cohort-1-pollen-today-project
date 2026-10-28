"""The 민감정보 consent gate: what it refuses, and what it lets through.

`has_sensitive_consent()` existed and nothing called it, so the app recorded
consent and then processed health data anyway. These tests pin the other half
of that: the three routes that write 민감정보 refuse without consent, work
after consent, and lock again after a withdrawal.

Two things are deliberately not tested here, because they must keep working
without consent:

- recording the consent and withdrawing it, and
- reading what is already held, and deleting it.

A gate that blocked the withdrawal would trap the user in the state the gate
created. 제36조 has to stay reachable.
"""

import json

import pytest
from httpx import AsyncClient

from app.agents import symptom_agent
from app.api import chat as chat_api
from app.main import app
from app.services import consent as consent_service

CODE = consent_service.SENSITIVE_CONSENT_REQUIRED_CODE

_EXTRACTION = json.dumps(
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


async def _register(client: AsyncClient, email: str) -> dict[str, str]:
    payload = {"email": email, "password": "correcthorse123"}
    await client.post("/api/auth/register", json=payload)
    res = await client.post("/api/auth/login", json=payload)
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


async def _grant(client: AsyncClient, headers: dict[str, str]) -> None:
    res = await client.post("/api/privacy/consent", json={"granted": True}, headers=headers)
    assert res.status_code == 200, res.text


@pytest.fixture
def scripted_chat(monkeypatch):
    """A chat turn that never leaves the machine.

    The model is replaced and persistence is stubbed, so a turn that got past
    the gate costs nothing and touches no network.
    """

    async def _load_state(session, conversation):
        return symptom_agent.initial_state([])

    async def _persist_turn(session, conversation, **kwargs):
        return None

    monkeypatch.setattr(chat_api, "_load_state", _load_state)
    monkeypatch.setattr(chat_api, "_persist_turn", _persist_turn)

    class _ScriptedLLM:
        def complete(self, messages) -> str:
            return _EXTRACTION

    monkeypatch.setitem(app.dependency_overrides, chat_api.get_llm, lambda: _ScriptedLLM())


def _assert_refusal(res) -> None:
    """A refusal is a status code with a code in it and a way to fix it."""
    assert res.status_code == 403, res.text
    detail = res.json()["detail"]
    assert detail["code"] == CODE
    assert detail["message"], "a refusal that does not say what to do is a dead end"
    assert "privacy notice" in detail["message"]


@pytest.mark.asyncio
async def test_a_chat_turn_is_refused_without_consent(client: AsyncClient) -> None:
    headers = await _register(client, "chat-noconsent@example.com")

    res = await client.post("/api/chat", json={"message": "my eyes itch"}, headers=headers)

    _assert_refusal(res)


@pytest.mark.asyncio
async def test_a_triage_write_is_refused_without_consent(client: AsyncClient) -> None:
    headers = await _register(client, "triage-noconsent@example.com")

    res = await client.post(
        "/api/triage", json={"symptoms": ["sneezing"], "severity": 2}, headers=headers
    )

    _assert_refusal(res)


@pytest.mark.asyncio
async def test_an_allergy_write_is_refused_without_consent(client: AsyncClient) -> None:
    headers = await _register(client, "allergy-noconsent@example.com")

    res = await client.post(
        "/api/allergies", json={"allergen": "TREE_POLLEN", "severity": "SEVERE"}, headers=headers
    )

    _assert_refusal(res)


@pytest.mark.asyncio
async def test_the_refusal_arrives_before_the_chat_stream_opens(client: AsyncClient) -> None:
    """Once the 200 and its headers are sent, a refusal is unreachable.

    A refusal inside the generator would arrive as a broken stream, and the
    symptom text would already have been on its way to the model.
    """
    headers = await _register(client, "chat-stream@example.com")

    res = await client.post("/api/chat", json={"message": "my eyes itch"}, headers=headers)

    assert res.status_code == 403
    assert "text/event-stream" not in res.headers.get("content-type", "")
    assert "event: error" not in res.text


@pytest.mark.asyncio
async def test_consent_unlocks_the_sensitive_flows(client: AsyncClient, scripted_chat) -> None:
    headers = await _register(client, "granted@example.com")
    await _grant(client, headers)

    chat = await client.post("/api/chat", json={"message": "my eyes itch"}, headers=headers)
    assert chat.status_code == 200, chat.text

    triage = await client.post(
        "/api/triage", json={"symptoms": ["sneezing"], "severity": 2}, headers=headers
    )
    assert triage.status_code == 200, triage.text

    allergy = await client.post(
        "/api/allergies",
        json={"allergen": "TREE_POLLEN", "severity": "SEVERE"},
        headers=headers,
    )
    assert allergy.status_code == 201, allergy.text


@pytest.mark.asyncio
async def test_withdrawing_locks_the_sensitive_flows_again(
    client: AsyncClient, scripted_chat
) -> None:
    """Consent that cannot be taken back is not consent."""
    headers = await _register(client, "withdraw@example.com")
    await _grant(client, headers)

    withdrawn = await client.post("/api/privacy/consent", json={"granted": False}, headers=headers)
    assert withdrawn.status_code == 200
    assert withdrawn.json()["granted"] is False

    chat = await client.post("/api/chat", json={"message": "my eyes itch"}, headers=headers)
    _assert_refusal(chat)

    triage = await client.post(
        "/api/triage", json={"symptoms": ["sneezing"], "severity": 2}, headers=headers
    )
    _assert_refusal(triage)

    allergy = await client.post(
        "/api/allergies",
        json={"allergen": "TREE_POLLEN", "severity": "SEVERE"},
        headers=headers,
    )
    _assert_refusal(allergy)


@pytest.mark.asyncio
async def test_the_consent_record_and_the_withdrawal_work_without_consent(
    client: AsyncClient,
) -> None:
    """The record is not 민감정보, and the gate must not guard its own exit."""
    headers = await _register(client, "record@example.com")

    granted = await client.post("/api/privacy/consent", json={"granted": True}, headers=headers)
    assert granted.status_code == 200
    assert granted.json()["granted"] is True

    withdrawn = await client.post("/api/privacy/consent", json={"granted": False}, headers=headers)
    assert withdrawn.status_code == 200
    assert withdrawn.json()["granted"] is False


@pytest.mark.asyncio
async def test_reading_and_deleting_stay_open_without_consent(client: AsyncClient) -> None:
    """제35조 and 제36조 must not be behind the gate that protects the data.

    A user who withdraws consent keeps the right to see what is held and to
    delete it. Gating those would punish the person for withdrawing.
    """
    headers = await _register(client, "rights@example.com")

    listed = await client.get("/api/allergies", headers=headers)
    assert listed.status_code == 200

    summary = await client.get("/api/privacy/summary", headers=headers)
    assert summary.status_code == 200

    exported = await client.get("/api/privacy/export", headers=headers)
    assert exported.status_code == 200

    deleted = await client.delete("/api/privacy/account", headers=headers)
    assert deleted.status_code == 200
