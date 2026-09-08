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
