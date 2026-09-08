"""Offline tests for the Places client + ranking logic. No network calls:
every httpx.AsyncClient is built with httpx.MockTransport.
"""

import httpx
import pytest

from app.services.hospital_service import (
    PlacesClient,
    PlacesClientError,
    find_nearby_hospitals,
)

DAEGU_LAT, DAEGU_LON = 35.856, 129.224


def _places_payload(*results: dict) -> dict:
    return {"status": "OK", "results": list(results)}


def _result(
    name: str,
    lat: float,
    lon: float,
    *,
    place_id: str = "place-1",
    open_now: bool | None = True,
    vicinity: str = "123 Main St",
) -> dict:
    return {
        "place_id": place_id,
        "name": name,
        "vicinity": vicinity,
        "geometry": {"location": {"lat": lat, "lng": lon}},
        "opening_hours": {"open_now": open_now},
    }


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_finds_and_ranks_by_distance():
    near = _result("Near ENT Clinic", DAEGU_LAT + 0.001, DAEGU_LON, place_id="near")
    far = _result("Far ENT Clinic", DAEGU_LAT + 0.05, DAEGU_LON, place_id="far")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_places_payload(far, near))

    async with _client(handler) as http:
        places = PlacesClient(http, api_key="test-key")
        outcome = await find_nearby_hospitals(places, latitude=DAEGU_LAT, longitude=DAEGU_LON)

    assert outcome.provider_available is True
    assert [r.place_id for r in outcome.results] == ["near", "far"]
    assert [r.rank for r in outcome.results] == [1, 2]
    assert outcome.results[0].distance_m < outcome.results[1].distance_m


async def test_specialty_filter_sends_keyword_and_tags_results():
    seen_params: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_params.update(dict(request.url.params))
        return httpx.Response(
            200, json=_places_payload(_result("ENT Center", DAEGU_LAT, DAEGU_LON))
        )

    async with _client(handler) as http:
        places = PlacesClient(http, api_key="test-key")
        outcome = await find_nearby_hospitals(
            places, latitude=DAEGU_LAT, longitude=DAEGU_LON, specialty="ent"
        )

    assert seen_params["keyword"] == "ENT clinic"
    assert outcome.results[0].specialty == "ENT"


async def test_open_now_filter_excludes_closed_facilities():
    open_place = _result("Open Clinic", DAEGU_LAT, DAEGU_LON, place_id="open", open_now=True)
    closed_place = _result("Closed Clinic", DAEGU_LAT, DAEGU_LON, place_id="closed", open_now=False)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_places_payload(open_place, closed_place))

    async with _client(handler) as http:
        places = PlacesClient(http, api_key="test-key")
        outcome = await find_nearby_hospitals(
            places, latitude=DAEGU_LAT, longitude=DAEGU_LON, open_now=True
        )

    assert [r.place_id for r in outcome.results] == ["open"]


async def test_provider_http_failure_is_handled_gracefully():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="upstream on fire")

    async with _client(handler) as http:
        places = PlacesClient(http, api_key="test-key")
        outcome = await find_nearby_hospitals(places, latitude=DAEGU_LAT, longitude=DAEGU_LON)

    assert outcome.provider_available is False
    assert outcome.results == []
    assert outcome.error


async def test_provider_timeout_is_handled_gracefully():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("connect timed out", request=request)

    async with _client(handler) as http:
        places = PlacesClient(http, api_key="test-key")
        outcome = await find_nearby_hospitals(places, latitude=DAEGU_LAT, longitude=DAEGU_LON)

    assert outcome.provider_available is False
    assert outcome.results == []


async def test_provider_api_error_status_is_handled_gracefully():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "REQUEST_DENIED", "error_message": "bad key"})

    async with _client(handler) as http:
        places = PlacesClient(http, api_key="test-key")
        outcome = await find_nearby_hospitals(places, latitude=DAEGU_LAT, longitude=DAEGU_LON)

    assert outcome.provider_available is False
    assert outcome.results == []


async def test_missing_api_key_is_handled_gracefully():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("must not call the network without an api key")

    async with _client(handler) as http:
        places = PlacesClient(http, api_key="")
        outcome = await find_nearby_hospitals(places, latitude=DAEGU_LAT, longitude=DAEGU_LON)

    assert outcome.provider_available is False


async def test_results_missing_a_name_are_skipped():
    bad = {"place_id": "no-name", "geometry": {"location": {"lat": DAEGU_LAT, "lng": DAEGU_LON}}}
    good = _result("Real Clinic", DAEGU_LAT, DAEGU_LON, place_id="real")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_places_payload(bad, good))

    async with _client(handler) as http:
        places = PlacesClient(http, api_key="test-key")
        outcome = await find_nearby_hospitals(places, latitude=DAEGU_LAT, longitude=DAEGU_LON)

    assert [r.place_id for r in outcome.results] == ["real"]


async def test_limit_caps_result_count():
    results = [_result(f"Clinic {i}", DAEGU_LAT, DAEGU_LON, place_id=str(i)) for i in range(5)]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_places_payload(*results))

    async with _client(handler) as http:
        places = PlacesClient(http, api_key="test-key")
        outcome = await find_nearby_hospitals(
            places, latitude=DAEGU_LAT, longitude=DAEGU_LON, limit=2
        )

    assert len(outcome.results) == 2


async def test_places_client_raises_on_bad_json():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not json")

    async with _client(handler) as http:
        places = PlacesClient(http, api_key="test-key")
        with pytest.raises(PlacesClientError):
            await places.nearby_search(
                latitude=DAEGU_LAT, longitude=DAEGU_LON, radius_m=5000, keyword=None
            )
