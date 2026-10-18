from httpx import AsyncClient


async def _register(client: AsyncClient, email: str, password: str = "correcthorse123") -> str:
    resp = await client.post("/api/auth/register", json={"email": email, "password": password})
    return resp.json()["access_token"]


async def test_read_me_requires_auth(client: AsyncClient):
    resp = await client.get("/api/users/me")
    assert resp.status_code == 401


async def test_read_me_returns_current_user(client: AsyncClient):
    token = await _register(client, "me@example.com")
    resp = await client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "me@example.com"
    assert "password_hash" not in body


async def test_update_me_updates_location(client: AsyncClient):
    token = await _register(client, "loc@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.put(
        "/api/users/me", json={"latitude": 35.856, "longitude": 129.224}, headers=headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["latitude"] == 35.856
    assert body["longitude"] == 129.224


async def test_a_saved_location_can_be_cleared(client: AsyncClient):
    """The way back out of a wrong location.

    The chat tells someone with no location to fix it, so a user who saved the
    wrong place has to be able to remove it. With an `is not None` guard the
    null was silently ignored and the old coordinates stayed forever.
    """
    token = await _register(client, "clearme@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    await client.put(
        "/api/users/me", json={"latitude": 35.856, "longitude": 129.224}, headers=headers
    )

    resp = await client.put(
        "/api/users/me", json={"latitude": None, "longitude": None}, headers=headers
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["latitude"] is None
    assert body["longitude"] is None


async def test_omitting_a_field_leaves_it_alone(client: AsyncClient):
    """Absent is not the same as null.

    A settings form that PUTs `{"email": ...}` must not wipe the location, and
    clearing only works because the two are now distinguishable.
    """
    token = await _register(client, "partial@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    await client.put(
        "/api/users/me", json={"latitude": 35.856, "longitude": 129.224}, headers=headers
    )

    resp = await client.put("/api/users/me", json={"password": "brandnewpass1"}, headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["latitude"] == 35.856
    assert body["longitude"] == 129.224


async def test_clearing_a_location_survives_a_reread(client: AsyncClient):
    """Cleared means cleared on the way back out, not just in the response body."""
    token = await _register(client, "roundtrip@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    await client.put(
        "/api/users/me", json={"latitude": 35.856, "longitude": 129.224}, headers=headers
    )
    await client.put("/api/users/me", json={"latitude": None, "longitude": None}, headers=headers)

    me = (await client.get("/api/users/me", headers=headers)).json()

    assert me["latitude"] is None
    assert me["longitude"] is None


async def test_update_me_rejects_email_already_taken(client: AsyncClient):
    await _register(client, "taken@example.com")
    token = await _register(client, "free@example.com")
    resp = await client.put(
        "/api/users/me",
        json={"email": "taken@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409


async def test_read_me_rejects_bad_token(client: AsyncClient):
    resp = await client.get("/api/users/me", headers={"Authorization": "Bearer garbage"})
    assert resp.status_code == 401
