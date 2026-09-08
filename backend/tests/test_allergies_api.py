from httpx import AsyncClient


async def _auth_headers(client: AsyncClient, email: str) -> dict:
    resp = await client.post(
        "/api/auth/register", json={"email": email, "password": "correcthorse123"}
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def test_create_and_list_allergy(client: AsyncClient):
    headers = await _auth_headers(client, "allergy1@example.com")
    create = await client.post(
        "/api/allergies",
        json={"allergen": "TREE_POLLEN", "severity": "SEVERE"},
        headers=headers,
    )
    assert create.status_code == 201
    body = create.json()
    assert body["allergen"] == "TREE_POLLEN"
    assert body["severity"] == "SEVERE"

    listed = await client.get("/api/allergies", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1


async def test_create_allergy_rejects_unknown_allergen(client: AsyncClient):
    headers = await _auth_headers(client, "allergy2@example.com")
    resp = await client.post(
        "/api/allergies",
        json={"allergen": "NOT_A_REAL_ALLERGEN", "severity": "MILD"},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_allergies_are_scoped_to_owner(client: AsyncClient):
    headers_a = await _auth_headers(client, "owner_a@example.com")
    headers_b = await _auth_headers(client, "owner_b@example.com")
    await client.post(
        "/api/allergies",
        json={"allergen": "DUST", "severity": "MILD"},
        headers=headers_a,
    )
    listed_b = await client.get("/api/allergies", headers=headers_b)
    assert listed_b.json() == []


async def test_delete_allergy(client: AsyncClient):
    headers = await _auth_headers(client, "allergy3@example.com")
    create = await client.post(
        "/api/allergies",
        json={"allergen": "MOLD", "severity": "MODERATE"},
        headers=headers,
    )
    allergy_id = create.json()["id"]

    deleted = await client.delete(f"/api/allergies/{allergy_id}", headers=headers)
    assert deleted.status_code == 204

    listed = await client.get("/api/allergies", headers=headers)
    assert listed.json() == []


async def test_delete_allergy_not_owned_returns_404(client: AsyncClient):
    headers_a = await _auth_headers(client, "owner_c@example.com")
    headers_b = await _auth_headers(client, "owner_d@example.com")
    create = await client.post(
        "/api/allergies",
        json={"allergen": "PM25", "severity": "MILD"},
        headers=headers_a,
    )
    allergy_id = create.json()["id"]

    resp = await client.delete(f"/api/allergies/{allergy_id}", headers=headers_b)
    assert resp.status_code == 404


async def test_delete_missing_allergy_returns_404(client: AsyncClient):
    headers = await _auth_headers(client, "allergy4@example.com")
    resp = await client.delete("/api/allergies/999999", headers=headers)
    assert resp.status_code == 404
