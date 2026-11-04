"""민감정보 consent: the record, the withdrawal, and what the policy has to say.

Grounded in 개인정보 보호법:

- 제23조①1호 — 건강 information is 민감정보 and may be processed only on consent
  that is separate from consent to anything else.
- 제15조② — that consent requires four specific things be disclosed first.
- 제22조 — a processor entrusted with the data has to be disclosed, which this
  app needs because symptom text goes to an LLM provider.
- 제30조 — the processing policy has to be established and published.

The tests that matter are the ones about *withdrawal*. A consent record that can
be granted but not withdrawn, or that keeps reporting `granted: true` after the
user says no, is the failure mode that makes the whole feature worse than not
having it — it manufactures evidence of agreement.
"""

from httpx import AsyncClient

from app.services import consent as consent_service


async def _token(client: AsyncClient, email: str = "consent@example.com") -> str:
    payload = {"email": email, "password": "correcthorse123"}
    await client.post("/api/auth/register", json=payload)
    res = await client.post("/api/auth/login", json=payload)
    return res.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- the policy itself ---------------------------------------------------


async def test_policy_is_public(client: AsyncClient) -> None:
    """Unauthenticated on purpose: a policy you can only read after signing up
    was never disclosed before consent was sought, which is what 제15조② is for."""
    res = await client.get("/api/privacy/policy")
    assert res.status_code == 200
    assert res.json()["version"] == consent_service.POLICY_VERSION


async def test_policy_is_marked_as_needing_legal_review(client: AsyncClient) -> None:
    """The text is written from the code, not by a lawyer. Saying so is the
    difference between a draft and a misrepresentation."""
    body = (await client.get("/api/privacy/policy")).json()
    assert body["status"] == "draft"
    assert body["requires_legal_review"] is True
    assert body["effective_from"] is None


async def test_policy_has_every_section_jih30_jo_requires(client: AsyncClient) -> None:
    """제30조: 처리 목적, 보유 기간, 제3자 제공, 파기절차 및 파기방법."""
    body = (await client.get("/api/privacy/policy")).json()
    text = " ".join(
        " ".join(section["body"]) + " " + section["heading"] for section in body["sections"]
    )
    for required in ("처리 목적", "보유 및 이용 기간", "파기절차", "위탁"):
        assert required in text, f"policy omits {required}"


async def test_policy_discloses_the_llm_transfer(client: AsyncClient) -> None:
    """The one thing that leaves the server. Silence about it in a privacy
    policy is the defect this section exists to prevent (제22조)."""
    body = (await client.get("/api/privacy/policy")).json()
    text = " ".join(" ".join(s["body"]) for s in body["sections"])
    assert "언어모델" in text
    assert "전송" in text


async def test_policy_lists_the_four_jih15_notice_items(client: AsyncClient) -> None:
    items = (await client.get("/api/privacy/policy")).json()["required_notice_items"]
    assert len(items) == 4
    assert items == list(consent_service.REQUIRED_NOTICE_ITEMS)


# --- the record ----------------------------------------------------------


async def test_a_new_account_has_not_consented(client: AsyncClient) -> None:
    token = await _token(client)
    body = (await client.get("/api/privacy/consent", headers=_auth(token))).json()
    assert body["granted"] is False
    assert body["granted_at"] is None
    assert body["version"] is None


async def test_granting_records_the_version_agreed_to(client: AsyncClient) -> None:
    """A bare timestamp cannot answer "were they told about symptom_events
    before we started storing them?", and that is the question an audit asks."""
    token = await _token(client)
    res = await client.post(
        "/api/privacy/consent",
        json={"granted": True, "version": "2026-01-01-old"},
        headers=_auth(token),
    )
    body = res.json()
    assert body["granted"] is True
    assert body["granted_at"] is not None
    # What they agreed to, not what is current now.
    assert body["version"] == "2026-01-01-old"
    assert body["policy_version"] == consent_service.POLICY_VERSION


async def test_withdrawing_clears_the_grant(client: AsyncClient) -> None:
    """Not just a withdrawn_at stamp. If the grant stayed set, any code checking
    only the consent column would keep seeing a consented user."""
    token = await _token(client)
    await client.post("/api/privacy/consent", json={"granted": True}, headers=_auth(token))
    body = (
        await client.post("/api/privacy/consent", json={"granted": False}, headers=_auth(token))
    ).json()
    assert body["granted"] is False
    assert body["granted_at"] is None
    assert body["version"] is None
    assert body["withdrawn_at"] is not None


async def test_granting_again_clears_the_withdrawal(client: AsyncClient) -> None:
    """Otherwise the account is simultaneously granted and withdrawn, and the
    answer depends on which column the caller happens to read."""
    token = await _token(client)
    await client.post("/api/privacy/consent", json={"granted": True}, headers=_auth(token))
    await client.post("/api/privacy/consent", json={"granted": False}, headers=_auth(token))
    body = (
        await client.post("/api/privacy/consent", json={"granted": True}, headers=_auth(token))
    ).json()
    assert body["granted"] is True
    assert body["withdrawn_at"] is None


async def test_consent_requires_authentication(client: AsyncClient) -> None:
    assert (await client.get("/api/privacy/consent")).status_code in (401, 403)
    assert (await client.post("/api/privacy/consent", json={"granted": True})).status_code in (
        401,
        403,
    )


async def test_consent_is_per_account(client: AsyncClient) -> None:
    """One user's consent must never satisfy another's."""
    a = await _token(client, "a@example.com")
    b = await _token(client, "b@example.com")
    await client.post("/api/privacy/consent", json={"granted": True}, headers=_auth(a))
    body_b = (await client.get("/api/privacy/consent", headers=_auth(b))).json()
    assert body_b["granted"] is False


# --- it shows up where the user can see it -------------------------------


async def test_summary_reports_consent_state(client: AsyncClient) -> None:
    token = await _token(client)
    await client.post("/api/privacy/consent", json={"granted": True}, headers=_auth(token))
    body = (await client.get("/api/privacy/summary", headers=_auth(token))).json()
    assert body["sensitive_consent"]["granted"] is True


async def test_summary_states_that_chat_text_leaves_the_server(client: AsyncClient) -> None:
    """The summary used to note that saved coordinates are never sent to the
    LLM, while saying nothing about the symptom text that is. Naming the safe
    one without naming the other is worse than naming neither."""
    token = await _token(client)
    body = (await client.get("/api/privacy/summary", headers=_auth(token))).json()
    notes = " ".join(p.get("note") or "" for p in body["data_points"])
    assert "sent to the LLM" in notes


async def test_export_carries_the_consent_record(client: AsyncClient) -> None:
    """제35조 is a right to a copy of what is held; a consent record is held."""
    token = await _token(client)
    await client.post(
        "/api/privacy/consent", json={"granted": True, "version": "v-test"}, headers=_auth(token)
    )
    res = await client.get("/api/privacy/export", headers=_auth(token))
    account = res.json()["account"]
    assert account["sensitive_consent_version"] == "v-test"
    assert account["sensitive_consent_at"] is not None


async def test_export_never_carries_the_password_hash(client: AsyncClient) -> None:
    token = await _token(client)
    res = await client.get("/api/privacy/export", headers=_auth(token))
    assert "password_hash" not in res.json()["account"]
