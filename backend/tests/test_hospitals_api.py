"""Endpoint tests for /api/hospitals/nearby. The httpx client dependency is
overridden with a MockTransport-backed client, so these never hit the network.
"""

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api import hospitals
from app.core.config import Settings, get_settings
from app.main import app

DAEGU_LAT, DAEGU_LON = 35.856, 129.224


def _places_payload(*results: dict) -> dict:
    return {"status": "OK", "results": list(results)}


def _result(name: str, lat: float, lon: float, place_id: str = "place-1") -> dict:
    return {
        "place_id": place_id,
        "name": name,
        "vicinity": "123 Main St",
        "geometry": {"location": {"lat": lat, "lng": lon}},
        "opening_hours": {"open_now": True},
    }


def _override_http_client(handler):
    async def _get_client():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            yield client

    return _get_client


@pytest.fixture(autouse=True)
def _clear_overrides():
    app.dependency_overrides[get_settings] = lambda: Settings(google_maps_api_key="test-key")
    yield
    app.dependency_overrides.pop(hospitals.get_http_client, None)
    app.dependency_overrides.pop(get_settings, None)


def test_nearby_returns_ranked_results():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json=_places_payload(_result("ENT Clinic", DAEGU_LAT, DAEGU_LON))
        )

    app.dependency_overrides[hospitals.get_http_client] = _override_http_client(handler)

    with TestClient(app) as client:
        resp = client.get(
            "/api/hospitals/nearby", params={"lat": DAEGU_LAT, "lon": DAEGU_LON, "specialty": "ENT"}
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["provider_available"] is True
    assert body["count"] == 1
    assert body["results"][0]["name"] == "ENT Clinic"
    assert body["results"][0]["rank"] == 1


def test_nearby_survives_dead_upstream():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("boom", request=request)

    app.dependency_overrides[hospitals.get_http_client] = _override_http_client(handler)

    with TestClient(app) as client:
        resp = client.get("/api/hospitals/nearby", params={"lat": DAEGU_LAT, "lon": DAEGU_LON})

    assert resp.status_code == 200
    body = resp.json()
    assert body["provider_available"] is False
    assert body["results"] == []
    assert body["count"] == 0


def test_nearby_rejects_out_of_range_latitude():
    with TestClient(app) as client:
        resp = client.get("/api/hospitals/nearby", params={"lat": 200, "lon": DAEGU_LON})

    assert resp.status_code == 422


def test_nearby_open_now_filter_round_trip():
    open_place = _result("Open Clinic", DAEGU_LAT, DAEGU_LON, place_id="open")
    closed_place = {**_result("Closed Clinic", DAEGU_LAT, DAEGU_LON, place_id="closed")}
    closed_place["opening_hours"] = {"open_now": False}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_places_payload(open_place, closed_place))

    app.dependency_overrides[hospitals.get_http_client] = _override_http_client(handler)

    with TestClient(app) as client:
        resp = client.get(
            "/api/hospitals/nearby",
            params={"lat": DAEGU_LAT, "lon": DAEGU_LON, "open_now": True},
        )

    body = resp.json()
    assert body["count"] == 1
    assert body["results"][0]["place_id"] == "open"
