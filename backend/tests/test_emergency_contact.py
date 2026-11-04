"""The emergency contact: one person to call, stored on the account.

It is the highest-value setting an allergy app can hold, and every operating
system ships its own version of it. Three things have to be true for it to be
worth anything:

- it round trips,
- a typo is caught before it is saved, with a message that says what a good
  phone number looks like, and
- it is the user's own data, so it travels with the export and it goes when the
  account goes.
"""

from httpx import AsyncClient
from sqlalchemy import func
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


async def _register(client: AsyncClient, email: str) -> dict[str, str]:
    payload = {"email": email, "password": "correcthorse123"}
    await client.post("/api/auth/register", json=payload)
    res = await client.post("/api/auth/login", json=payload)
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


async def test_the_contact_round_trips(client: AsyncClient) -> None:
    headers = await _register(client, "contact@example.com")

    empty = await client.get("/api/users/me/emergency-contact", headers=headers)
    assert empty.status_code == 200
    assert empty.json() == {"name": None, "phone": None, "note": None}

    saved = await client.put(
        "/api/users/me/emergency-contact",
        json={"name": "Park Minjun", "phone": "010-1234-5678", "note": "Carries an EpiPen"},
        headers=headers,
    )
    assert saved.status_code == 200
    assert saved.json() == {
        "name": "Park Minjun",
        "phone": "010-1234-5678",
        "note": "Carries an EpiPen",
    }

    read_back = await client.get("/api/users/me/emergency-contact", headers=headers)
    assert read_back.json()["phone"] == "010-1234-5678"


async def test_an_empty_value_clears_the_contact(client: AsyncClient) -> None:
    headers = await _register(client, "clear@example.com")
    await client.put(
        "/api/users/me/emergency-contact",
        json={"name": "Park Minjun", "phone": "010-1234-5678"},
        headers=headers,
    )

    cleared = await client.put(
        "/api/users/me/emergency-contact",
        json={"name": "", "phone": "", "note": ""},
        headers=headers,
    )

    assert cleared.status_code == 200
    assert cleared.json() == {"name": None, "phone": None, "note": None}


async def test_a_bad_phone_is_rejected_with_a_message_that_says_how_to_fix_it(
    client: AsyncClient,
) -> None:
    """A number that cannot be dialled is worse than no number, because the
    user believes it is there."""
    headers = await _register(client, "badphone@example.com")

    res = await client.put(
        "/api/users/me/emergency-contact",
        json={"name": "Park Minjun", "phone": "call my mum"},
        headers=headers,
    )

    assert res.status_code == 422
    message = str(res.json())
    assert "digits" in message
    assert "phone number" in message

    # Nothing was saved, so a rejected number never becomes the saved one.
    read_back = await client.get("/api/users/me/emergency-contact", headers=headers)
    assert read_back.json()["phone"] is None


async def test_a_phone_with_too_few_digits_is_rejected(client: AsyncClient) -> None:
    headers = await _register(client, "shortphone@example.com")

    res = await client.put(
        "/api/users/me/emergency-contact",
        json={"phone": "123"},
        headers=headers,
    )

    assert res.status_code == 422
    assert "digits" in str(res.json())


async def test_the_contact_needs_a_signed_in_user(client: AsyncClient) -> None:
    assert (await client.get("/api/users/me/emergency-contact")).status_code == 401
    assert (await client.put("/api/users/me/emergency-contact", json={})).status_code == 401


async def test_the_contact_is_in_the_export(client: AsyncClient) -> None:
    """It is the user's own data, so a copy of the data has to carry it."""
    headers = await _register(client, "export@example.com")
    await client.put(
        "/api/users/me/emergency-contact",
        json={"name": "Park Minjun", "phone": "010-1234-5678", "note": "Carries an EpiPen"},
        headers=headers,
    )

    body = (await client.get("/api/privacy/export", headers=headers)).json()

    assert body["emergency_contact"] == {
        "name": "Park Minjun",
        "phone": "010-1234-5678",
        "note": "Carries an EpiPen",
    }


async def test_the_contact_is_gone_when_the_account_is_deleted(client: AsyncClient) -> None:
    headers = await _register(client, "delete@example.com")
    await client.put(
        "/api/users/me/emergency-contact",
        json={"name": "Park Minjun", "phone": "010-1234-5678"},
        headers=headers,
    )

    res = await client.delete("/api/privacy/account", headers=headers)
    assert res.status_code == 200

    remaining = await client.get("/api/users/me/emergency-contact", headers=headers)
    assert remaining.status_code == 401, "the contact answered for a deleted account"


async def test_no_contact_survives_on_any_user_row(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The columns live on the account row, so the row goes and they go."""
    headers = await _register(client, "rows@example.com")
    await client.put(
        "/api/users/me/emergency-contact",
        json={"name": "Park Minjun", "phone": "010-1234-5678"},
        headers=headers,
    )

    await client.delete("/api/privacy/account", headers=headers)

    count = await session.scalar(sa_select(func.count()).select_from(User))
    assert count == 0
