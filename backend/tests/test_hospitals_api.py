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


def _naver_payload(*items: dict) -> dict:
    return {"total": len(items), "start": 1, "display": len(items), "items": list(items)}


def _item(name: str, lat: float, lon: float) -> dict:
    return {
        "title": f"<b>{name}</b>",
        "category": "병원>이비인후과",
        "description": "",
        "telephone": "02-1234-5678",
        "address": "대구 동구 신천동 123",
        "roadAddress": "대구 동구 동대구로 456",
        "mapx": str(round(lon * 1e7)),
        "mapy": str(round(lat * 1e7)),
    }


def _override_http_client(handler):
    async def _get_client():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            yield client

    return _get_client


@pytest.fixture(autouse=True)
def _clear_overrides():
    app.dependency_overrides[get_settings] = lambda: Settings(
        naver_client_id="test-id", naver_client_secret="test-secret"
    )
    yield
    app.dependency_overrides.pop(hospitals.get_http_client, None)
    app.dependency_overrides.pop(get_settings, None)


def test_nearby_returns_ranked_results():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_naver_payload(_item("ENT Clinic", DAEGU_LAT, DAEGU_LON)))

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
    assert "place_id" not in body["results"][0]
    assert "is_open" not in body["results"][0]


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


def test_nearby_has_no_open_now_param():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_naver_payload(_item("Clinic", DAEGU_LAT, DAEGU_LON)))

    app.dependency_overrides[hospitals.get_http_client] = _override_http_client(handler)

    with TestClient(app) as client:
        # open_now is silently ignored (not a declared query param) rather
        # than accepted and lied about.
        resp = client.get(
            "/api/hospitals/nearby",
            params={"lat": DAEGU_LAT, "lon": DAEGU_LON, "open_now": True},
        )

    assert resp.status_code == 200
    assert "open_now" not in resp.json()
    assert "is_open" not in resp.json()["results"][0]


def test_nearby_location_query_round_trip():
    seen_params: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_params.update(dict(request.url.params))
        return httpx.Response(200, json=_naver_payload(_item("Clinic", DAEGU_LAT, DAEGU_LON)))

    app.dependency_overrides[hospitals.get_http_client] = _override_http_client(handler)

    with TestClient(app) as client:
        resp = client.get(
            "/api/hospitals/nearby",
            params={
                "lat": DAEGU_LAT,
                "lon": DAEGU_LON,
                "specialty": "ENT",
                "location_query": "대구 동구",
            },
        )

    assert resp.status_code == 200
    assert seen_params["query"] == "대구 동구 이비인후과"


def test_nearby_caps_at_five_results():
    items = [_item(f"Clinic {i}", DAEGU_LAT, DAEGU_LON) for i in range(5)]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["display"] == "5"
        return httpx.Response(200, json=_naver_payload(*items))

    app.dependency_overrides[hospitals.get_http_client] = _override_http_client(handler)

    with TestClient(app) as client:
        resp = client.get("/api/hospitals/nearby", params={"lat": DAEGU_LAT, "lon": DAEGU_LON})

    assert resp.json()["count"] == 5
