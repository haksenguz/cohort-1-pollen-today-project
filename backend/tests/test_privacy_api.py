"""Personal-data rights: what is held, taking a copy, and deleting it.

Grounded in 개인정보 보호법:

- 제4조3 / 제35조 — the right to inspect and to take a copy (전송).
- 제36조 — the right to correct or delete, and 제36조③ requires deletion to be
  non-recoverable.

The tests that matter here are the ones that would catch a plausible
implementation being wrong. Exporting a password hash, leaving orphan messages
behind after "delete everything", or leaking one account's health data into
another account's export are all bugs that pass a happy-path smoke test.
"""

import os

import pytest
from httpx import AsyncClient
from sqlalchemy import func
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models import (
    Conversation,
    HospitalResult,
    HospitalSearch,
    Message,
    SymptomEvent,
    TriageResult,
    User,
    UserAllergy,
)

# These exercise `symptom_events`, `triage_results` and the `hospital_*`
# tables. The SQLite in-memory engine behind the default `session` fixture
# cannot compile `symptom_events` — it is JSONB — and conftest deliberately
# creates only a subset there, so on SQLite there is nothing to assert against.
# Postgres is where the schema is real and where the FK order inside the delete
# actually matters, which is the point of most of these.
requires_full_schema = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL", "").startswith("postgresql"),
    reason="Needs the JSONB and enforced-FK behaviour only Postgres has; run the Postgres gate.",
)


async def _register(client: AsyncClient, email: str) -> str:
    payload = {"email": email, "password": "correcthorse123"}
    await client.post("/api/auth/register", json=payload)
    res = await client.post("/api/auth/login", json=payload)
    return res.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _seed(session: AsyncSession, *, email: str, needle: str) -> int:
    """Fill the account `_register` already created with a row in every table.

    Every string carries `needle` so a leak is a substring match rather than a
    judgement call about whether this is the right row.
    """
    found = await session.execute(select(User).where(User.email == email))
    user = found.scalars().first()
    assert user is not None, f"{email} was not registered before seeding"
    user.latitude = 37.5
    user.longitude = 127.0
    session.add(user)
    await session.commit()
    await session.refresh(user)

    session.add(UserAllergy(user_id=user.id, allergen="birch", severity="HIGH"))
    conversation = Conversation(user_id=user.id, title=f"c-{needle}")
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)

    session.add(
        Message(
            conversation_id=conversation.id,
            role="USER",
            content=f"I cannot breathe, itchy throat {needle}",
        )
    )
    session.add(
        SymptomEvent(
            user_id=user.id, conversation_id=conversation.id, symptoms=[needle], severity=4
        )
    )
    await session.commit()

    events = (
        (await session.execute(select(SymptomEvent).where(SymptomEvent.user_id == user.id)))
        .scalars()
        .all()
    )
    session.add(
        TriageResult(
            symptom_event_id=events[0].id, risk_level="EMERGENCY", recommendation="call 119"
        )
    )
    search = HospitalSearch(user_id=user.id, latitude=37.5, longitude=127.0, specialty="ALLERGY")
    session.add(search)
    await session.commit()
    await session.refresh(search)

    session.add(HospitalResult(hospital_search_id=search.id, name=f"Hospital {needle}"))
    await session.commit()
    return user.id


@requires_full_schema
async def test_the_export_never_carries_the_password_hash(
    client: AsyncClient, session: AsyncSession
):
    """A "download my data" endpoint that returns the hash is a credential leak.

    It reads like a privacy feature and it hands an attacker who gets hold of
    the file every credential for the account.
    """
    token = await _register(client, "hash@example.com")
    await _seed(session, email="hash@example.com", needle="hashneedle")

    res = await client.get("/api/privacy/export", headers=_auth(token))
    assert res.status_code == 200

    assert "password_hash" not in res.text
    assert "hashed-not-exported" not in res.text


@requires_full_schema
async def test_the_export_is_a_download_named_for_the_day(
    client: AsyncClient, session: AsyncSession
):
    """전송 is a right to a *copy*, so it arrives as a file, not a rendered page."""
    token = await _register(client, "dl@example.com")
    await _seed(session, email="dl@example.com", needle="dlneedle")

    res = await client.get("/api/privacy/export", headers=_auth(token))

    assert res.status_code == 200
    assert res.headers["content-type"].startswith("application/json")
    assert "attachment" in res.headers["content-disposition"]
    assert "my-data-" in res.headers["content-disposition"]
    # Personal data must not be left in a shared cache.
    assert res.headers.get("cache-control") == "no-store"


@requires_full_schema
async def test_the_export_contains_the_health_data_and_nests_it_readably(
    client: AsyncClient, session: AsyncSession
):
    """A flat dump of eleven tables is not something a person can check."""
    token = await _register(client, "nested@example.com")
    await _seed(session, email="nested@example.com", needle="nestneedle")

    body = (await client.get("/api/privacy/export", headers=_auth(token))).json()

    assert body["account"]["email"] == "nested@example.com"
    assert body["counts"]["conversations"] == 1
    assert body["counts"]["messages"] == 1

    conversation = body["conversations"][0]
    assert conversation["messages"][0]["content"].endswith("nestneedle")

    # The engine's verdict travels with the symptoms it was derived from, so the
    # export cannot be read as "this is what you said" on its own.
    event = body["symptom_events"][0]
    assert event["triage_result"]["risk_level"] == "EMERGENCY"

    search = body["hospital_searches"][0]
    assert search["results"][0]["name"].endswith("nestneedle")

    assert body["allergies"][0]["allergen"] == "birch"


@requires_full_schema
async def test_one_account_can_never_export_another_accounts_health_data(
    client: AsyncClient, session: AsyncSession
):
    """The whole point of scoping the query to `user_id`."""
    await _register(client, "mine@example.com")
    await _register(client, "theirs@example.com")
    await _seed(session, email="mine@example.com", needle="mineneedle")
    await _seed(session, email="theirs@example.com", needle="THEIRSNEEDLE")

    body = (
        await client.get(
            "/api/privacy/export", headers=_auth(await _token(client, "mine@example.com"))
        )
    ).json()

    assert "THEIRSNEEDLE" not in str(body), "one account saw another account's health data"
    assert body["account"]["email"] == "mine@example.com"


@requires_full_schema
async def test_deleting_removes_the_orphans_too_not_just_the_rows_keyed_on_user(
    client: AsyncClient, session: AsyncSession
):
    """messages, triage_results and hospital_results have no user_id of their own.

    A delete written table-by-table on `user_id` leaves all three behind, and
    they still point at a user that no longer exists. This is the single most
    likely way to implement "delete my account" wrong.
    """
    token = await _register(client, "del@example.com")
    user_id = await _seed(session, email="del@example.com", needle="delneedle")

    res = await client.delete("/api/privacy/account", headers=_auth(token))
    assert res.status_code == 200
    assert res.json()["deleted"]["account"] == 1

    for model, label in (
        (User, "users"),
        (Conversation, "conversations"),
        (SymptomEvent, "symptom_events"),
        (TriageResult, "triage_results"),
    ):
        remaining = await session.scalar(sa_select(func.count()).select_from(model))
        assert remaining == 0, f"{label} survived an account deletion"

    # The three child tables carry no user_id, so they are checked directly.
    assert await session.scalar(sa_select(func.count()).select_from(Message)) == 0
    assert await session.scalar(sa_select(func.count()).select_from(HospitalResult)) == 0
    assert await session.scalar(sa_select(func.count()).select_from(HospitalSearch)) == 0
    assert await session.get(User, user_id) is None


@requires_full_schema
async def test_deleting_one_account_leaves_the_others_data_alone(
    client: AsyncClient, session: AsyncSession
):
    """The caller deletes their own account and nobody else's.

    The token is taken from `leaver`, so `stayer` is the account that has to
    survive. Reading it the other way round would delete the account the
    assertion expects to find gone.
    """
    await _register(client, "stayer@example.com")
    leaver_token = await _register(client, "leaver@example.com")
    await _seed(session, email="stayer@example.com", needle="stayneedle")
    await _seed(session, email="leaver@example.com", needle="goeneedle")

    await client.delete("/api/privacy/account", headers=_auth(leaver_token))

    survivors = (await session.execute(select(User))).scalars().all()
    assert [u.email for u in survivors] == ["stayer@example.com"]
    remaining = await session.scalar(sa_select(func.count()).select_from(Message))
    assert remaining == 1, "deleting one account took another account's messages with it"


@requires_full_schema
async def test_after_deletion_the_data_cannot_be_read_back(
    client: AsyncClient, session: AsyncSession
):
    """제36조③: deletion must not leave anything recoverable.

    A soft-delete flag or a tombstone row would pass a "the row is gone from the
    list" test and still fail here.

    The strongest form of the guarantee is not an empty document — it is that
    the deleted account's own token stops working. An unexpired JWT still
    carries a valid signature, so only the lookup of its user can reject it, and
    that is what makes the row genuinely gone rather than merely hidden.
    """
    token = await _register(client, "gone@example.com")
    await _seed(session, email="gone@example.com", needle="goneneedle")

    await client.delete("/api/privacy/account", headers=_auth(token))

    res = await client.get("/api/privacy/export", headers=_auth(token))
    assert res.status_code == 401, "a deleted account's token still serves data"
    assert "goneneedle" not in res.text

    # And nothing of theirs survives in the database either.
    assert await session.scalar(sa_select(func.count()).select_from(Message)) == 0
    assert await session.scalar(sa_select(func.count()).select_from(SymptomEvent)) == 0


async def test_every_privacy_right_requires_being_signed_in(client: AsyncClient):
    """Otherwise these endpoints are a public dump of everyone's health data."""
    anonymous = {"Authorization": ""}

    assert (await client.get("/api/privacy/summary")).status_code == 401
    assert (await client.get("/api/privacy/export")).status_code == 401
    assert (await client.delete("/api/privacy/account", headers=anonymous)).status_code == 401


async def test_the_summary_names_what_is_never_collected(client: AsyncClient):
    """Stating what is not collected matters as much as stating what is.

    Silence reads as a gap in the policy, and the user has no way to tell the
    difference between "we do not do this" and "we did not mention it".
    """
    token = await _register(client, "summary@example.com")

    body = (await client.get("/api/privacy/summary", headers=_auth(token))).json()

    assert body["account_email"] == "summary@example.com"
    assert any(point["sensitive"] for point in body["data_points"])
    assert body["not_stored"], "the app never says what it does not collect"
    tables = " ".join(point["table"] for point in body["data_points"])
    for table in ("users", "messages", "symptom_events", "triage_results", "hospital_searches"):
        assert table in tables, f"{table} holds personal data but the summary does not say so"


async def _token(client: AsyncClient, email: str) -> str:
    res = await client.post("/api/auth/login", json={"email": email, "password": "correcthorse123"})
    return res.json()["access_token"]
