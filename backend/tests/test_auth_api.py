from httpx import AsyncClient


async def test_register_returns_access_token(client: AsyncClient):
    resp = await client.post(
        "/api/auth/register", json={"email": "new@example.com", "password": "correcthorse123"}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


async def test_register_duplicate_email_is_rejected(client: AsyncClient):
    payload = {"email": "dupe@example.com", "password": "correcthorse123"}
    first = await client.post("/api/auth/register", json=payload)
    second = await client.post("/api/auth/register", json=payload)
    assert first.status_code == 201
    assert second.status_code == 409


async def test_register_short_password_is_rejected(client: AsyncClient):
    resp = await client.post(
        "/api/auth/register", json={"email": "weak@example.com", "password": "short"}
    )
    assert resp.status_code == 422


async def test_login_with_correct_credentials_returns_token(client: AsyncClient):
    payload = {"email": "login@example.com", "password": "correcthorse123"}
    await client.post("/api/auth/register", json=payload)
    resp = await client.post("/api/auth/login", json=payload)
    assert resp.status_code == 200
    assert resp.json()["access_token"]


async def test_login_with_wrong_password_is_rejected(client: AsyncClient):
    payload = {"email": "login2@example.com", "password": "correcthorse123"}
    await client.post("/api/auth/register", json=payload)
    resp = await client.post(
        "/api/auth/login", json={"email": payload["email"], "password": "wrongpassword"}
    )
    assert resp.status_code == 401


async def test_login_with_unknown_email_is_rejected(client: AsyncClient):
    resp = await client.post(
        "/api/auth/login", json={"email": "ghost@example.com", "password": "correcthorse123"}
    )
    assert resp.status_code == 401
