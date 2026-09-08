"""Offline tests for the Naver Local Search client + ranking logic. No
network calls: every httpx.AsyncClient is built with httpx.MockTransport.
"""

import httpx
import pytest

from app.services.hospital_service import (
    NaverLocalClient,
    NaverLocalClientError,
    find_nearby_hospitals,
)

DAEGU_LAT, DAEGU_LON = 35.856, 129.224


def _naver_payload(*items: dict) -> dict:
    return {
        "lastBuildDate": "Tue, 08 Sep 2026 00:00:00 +0900",
        "total": len(items),
        "start": 1,
        "display": len(items),
        "items": list(items),
    }


def _mapxy(lat: float, lon: float) -> tuple[str, str]:
    """Naver's real response shape: WGS84 lon/lat * 1e7, as strings."""
    return str(round(lon * 1e7)), str(round(lat * 1e7))


def _item(
    name: str,
    lat: float,
    lon: float,
    *,
    telephone: str = "02-1234-5678",
    address: str = "대구 동구 신천동 123",
    road_address: str = "대구 동구 동대구로 456",
    category: str = "병원>이비인후과",
) -> dict:
    mapx, mapy = _mapxy(lat, lon)
    return {
        "title": f"<b>{name}</b> 이비인후과의원",
        "link": "https://example.com",
        "category": category,
        "description": "",
        "telephone": telephone,
        "address": address,
        "roadAddress": road_address,
        "mapx": mapx,
        "mapy": mapy,
    }


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_finds_and_ranks_by_distance():
    near = _item("Near ENT Clinic", DAEGU_LAT + 0.001, DAEGU_LON)
    far = _item("Far ENT Clinic", DAEGU_LAT + 0.05, DAEGU_LON)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_naver_payload(far, near))

    async with _client(handler) as http:
        naver = NaverLocalClient(http, client_id="id", client_secret="secret")
        outcome = await find_nearby_hospitals(
            naver, latitude=DAEGU_LAT, longitude=DAEGU_LON, radius_m=10000
        )

    assert outcome.provider_available is True
    assert [r.name for r in outcome.results] == [
        "Near ENT Clinic 이비인후과의원",
        "Far ENT Clinic 이비인후과의원",
    ]
    assert [r.rank for r in outcome.results] == [1, 2]
    assert outcome.results[0].distance_m < outcome.results[1].distance_m


async def test_html_tags_are_stripped_from_title():
    item = _item("Central", DAEGU_LAT, DAEGU_LON)
    item["title"] = "<b>Central</b> ENT <b>Clinic</b>"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_naver_payload(item))

    async with _client(handler) as http:
        naver = NaverLocalClient(http, client_id="id", client_secret="secret")
        outcome = await find_nearby_hospitals(naver, latitude=DAEGU_LAT, longitude=DAEGU_LON)

    assert outcome.results[0].name == "Central ENT Clinic"


async def test_coordinate_conversion_from_wgs84_mapx_mapy():
    # 대구 시청 근방: lat 35.8714, lon 128.6014 roughly — use a small, known
    # offset from the origin and check the converted point lands close by.
    lat, lon = DAEGU_LAT + 0.01, DAEGU_LON + 0.01
    item = _item("Coord Check", lat, lon)
    assert item["mapx"] == str(round(lon * 1e7))
    assert item["mapy"] == str(round(lat * 1e7))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_naver_payload(item))

    async with _client(handler) as http:
        naver = NaverLocalClient(http, client_id="id", client_secret="secret")
        outcome = await find_nearby_hospitals(naver, latitude=DAEGU_LAT, longitude=DAEGU_LON)

    assert outcome.results[0].distance_m is not None
    assert outcome.results[0].distance_m > 0


async def test_legacy_katech_coordinates_are_dropped_defensively():
    # Old-format Naver responses used KATECH/TM128 map units, which do not
    # divide down into valid WGS84 ranges. We should not plot a bogus point.
    item = _item("Legacy Coords", DAEGU_LAT, DAEGU_LON)
    item["mapx"] = "1280000000"  # /1e7 = 128.0 -> valid longitude
    item["mapy"] = "4500000000"  # /1e7 = 450.0 -> out of WGS84 latitude range

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_naver_payload(item))

    async with _client(handler) as http:
        naver = NaverLocalClient(http, client_id="id", client_secret="secret")
        outcome = await find_nearby_hospitals(naver, latitude=DAEGU_LAT, longitude=DAEGU_LON)

    assert outcome.results[0].distance_m is None


async def test_specialty_filter_sends_korean_keyword_and_tags_results():
    seen_params: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_params.update(dict(request.url.params))
        return httpx.Response(200, json=_naver_payload(_item("ENT Center", DAEGU_LAT, DAEGU_LON)))

    async with _client(handler) as http:
        naver = NaverLocalClient(http, client_id="id", client_secret="secret")
        outcome = await find_nearby_hospitals(
            naver, latitude=DAEGU_LAT, longitude=DAEGU_LON, specialty="ent"
        )

    assert seen_params["query"] == "이비인후과"
    assert outcome.results[0].specialty == "ENT"


async def test_location_query_is_mixed_into_keyword():
    seen_params: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_params.update(dict(request.url.params))
        return httpx.Response(200, json=_naver_payload(_item("ENT Center", DAEGU_LAT, DAEGU_LON)))

    async with _client(handler) as http:
        naver = NaverLocalClient(http, client_id="id", client_secret="secret")
        await find_nearby_hospitals(
            naver,
            latitude=DAEGU_LAT,
            longitude=DAEGU_LON,
            specialty="ent",
            location_query="대구 동구",
        )

    assert seen_params["query"] == "대구 동구 이비인후과"


async def test_display_is_capped_at_five_and_start_is_always_one():
    seen_params: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_params.update(dict(request.url.params))
        return httpx.Response(200, json=_naver_payload())

    async with _client(handler) as http:
        naver = NaverLocalClient(http, client_id="id", client_secret="secret")
        await naver.search(query="병원", display=50)

    assert seen_params["display"] == "5"
    assert seen_params["start"] == "1"


async def test_client_sends_naver_auth_headers():
    seen_headers: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.update(dict(request.headers))
        return httpx.Response(200, json=_naver_payload())

    async with _client(handler) as http:
        naver = NaverLocalClient(http, client_id="my-id", client_secret="my-secret")
        await naver.search(query="병원")

    assert seen_headers["x-naver-client-id"] == "my-id"
    assert seen_headers["x-naver-client-secret"] == "my-secret"


async def test_radius_m_filters_client_side_after_ranking():
    near = _item("Near Clinic", DAEGU_LAT + 0.001, DAEGU_LON)
    far = _item("Far Clinic", DAEGU_LAT + 0.5, DAEGU_LON)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_naver_payload(near, far))

    async with _client(handler) as http:
        naver = NaverLocalClient(http, client_id="id", client_secret="secret")
        outcome = await find_nearby_hospitals(
            naver, latitude=DAEGU_LAT, longitude=DAEGU_LON, radius_m=2000
        )

    assert [r.name for r in outcome.results] == ["Near Clinic 이비인후과의원"]


async def test_provider_http_failure_is_handled_gracefully():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="upstream on fire")

    async with _client(handler) as http:
        naver = NaverLocalClient(http, client_id="id", client_secret="secret")
        outcome = await find_nearby_hospitals(naver, latitude=DAEGU_LAT, longitude=DAEGU_LON)

    assert outcome.provider_available is False
    assert outcome.results == []
    assert outcome.error


async def test_provider_timeout_is_handled_gracefully():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("connect timed out", request=request)

    async with _client(handler) as http:
        naver = NaverLocalClient(http, client_id="id", client_secret="secret")
        outcome = await find_nearby_hospitals(naver, latitude=DAEGU_LAT, longitude=DAEGU_LON)

    assert outcome.provider_available is False
    assert outcome.results == []


async def test_provider_api_error_body_is_handled_gracefully():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"errorMessage": "Invalid display value", "errorCode": "SE02"}
        )

    async with _client(handler) as http:
        naver = NaverLocalClient(http, client_id="id", client_secret="secret")
        outcome = await find_nearby_hospitals(naver, latitude=DAEGU_LAT, longitude=DAEGU_LON)

    assert outcome.provider_available is False
    assert outcome.results == []


async def test_missing_credentials_is_handled_gracefully():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("must not call the network without credentials")

    async with _client(handler) as http:
        naver = NaverLocalClient(http, client_id="", client_secret="")
        outcome = await find_nearby_hospitals(naver, latitude=DAEGU_LAT, longitude=DAEGU_LON)

    assert outcome.provider_available is False


async def test_results_missing_a_title_are_skipped():
    bad = {
        "category": "병원",
        "telephone": "",
        "address": "",
        "roadAddress": "",
        "mapx": str(round(DAEGU_LON * 1e7)),
        "mapy": str(round(DAEGU_LAT * 1e7)),
    }
    good = _item("Real Clinic", DAEGU_LAT, DAEGU_LON)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_naver_payload(bad, good))

    async with _client(handler) as http:
        naver = NaverLocalClient(http, client_id="id", client_secret="secret")
        outcome = await find_nearby_hospitals(naver, latitude=DAEGU_LAT, longitude=DAEGU_LON)

    assert [r.name for r in outcome.results] == ["Real Clinic 이비인후과의원"]


async def test_naver_client_raises_on_bad_json():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not json")

    async with _client(handler) as http:
        naver = NaverLocalClient(http, client_id="id", client_secret="secret")
        with pytest.raises(NaverLocalClientError):
            await naver.search(query="병원")
