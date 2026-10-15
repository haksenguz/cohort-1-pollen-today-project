"""Pollen provider: real KMA data when keyed, flagged sample when not.

The point of these tests is the `is_sample` contract. A caller must be able to
tell fabricated data from real data, and "provider returned nothing" must never
be dressed up as the sample.

The KMA payloads below are the shapes confirmed live on 2026-10-15: three
separate operations, a `resultCode` header that reports out-of-season windows,
and a `today` grade that is blank when KMA published nothing. Each of those is
pinned here, because each one silently degrades to a wrong reading otherwise.
"""

import datetime as dt

import httpx
import pytest

from app.core.enums import PollenLevel
from app.services import pollen_service


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _row(**overrides) -> dict:
    row = {"code": "D08", "areaNo": "1100000000", "date": "2026101506"}
    row.update({"today": "0", "tomorrow": "0", "dayaftertomorrow": "0"})
    row.update(overrides)
    return row


def _ok_payload(**overrides) -> dict:
    return {
        "response": {
            "header": {"resultCode": "00", "resultMsg": "NORMAL_SERVICE"},
            "body": {"dataType": "JSON", "items": {"item": [_row(**overrides)]}},
        }
    }


def _out_of_season() -> dict:
    return {
        "response": {
            "header": {
                "resultCode": "99",
                "resultMsg": "해당지수자료 제공기간이 아닙니다! [자료제공기간 3월 ~ 6월]",
            }
        }
    }


@pytest.mark.asyncio
async def test_no_key_returns_the_flagged_sample() -> None:
    async with _client(lambda r: pytest.fail("must not call the provider")) as c:
        data = await pollen_service.fetch_pollen(37.5665, 126.9780, c, api_key="")

    assert data.is_sample is True
    assert data.tree == PollenLevel.HIGH


@pytest.mark.asyncio
async def test_real_data_is_never_flagged_as_a_sample() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["serviceKey"] == "test-key"
        # Seoul centroid -> the provider's 10-digit station code, not "11".
        assert request.url.params["areaNo"] == "1100000000"
        assert "time" in request.url.params
        return httpx.Response(200, json=_ok_payload(today="1"))

    async with _client(handler) as c:
        data = await pollen_service.fetch_pollen(37.5665, 126.9780, c, api_key="test-key")

    assert data.is_sample is False
    assert data.tree == PollenLevel.MODERATE
    assert data.weed == PollenLevel.MODERATE
    assert data.grass is None  # this provider reports no grass index


@pytest.mark.asyncio
async def test_tree_is_the_worse_of_oak_and_pine() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        today = "3" if request.url.path.endswith("PinePollenRiskIdxV3") else "1"
        return httpx.Response(200, json=_ok_payload(today=today))

    async with _client(handler) as c:
        data = await pollen_service.fetch_pollen(37.5665, 126.9780, c, api_key="k")

    assert data.tree == PollenLevel.HIGH  # max(oak=1, pine=3) -> HIGH


@pytest.mark.asyncio
async def test_out_of_season_reads_as_no_data_not_as_low() -> None:
    """October is weed season. The tree operations answer resultCode 99 and
    carry no body, which must not turn into 'Tree pollen: Low'."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("WeedsPollenRiskndxV3"):
            return httpx.Response(200, json=_ok_payload(today="2"))
        return httpx.Response(200, json=_out_of_season())

    async with _client(handler) as c:
        data = await pollen_service.fetch_pollen(37.5665, 126.9780, c, api_key="k")

    assert data.tree is None
    assert data.weed == PollenLevel.HIGH
    assert data.is_sample is False


@pytest.mark.asyncio
async def test_blank_today_reads_as_no_data_not_as_low() -> None:
    """KMA returns an empty string for an hour it has not published yet."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_ok_payload(today=""))

    async with _client(handler) as c:
        data = await pollen_service.fetch_pollen(37.5665, 126.9780, c, api_key="k")

    assert data.tree is None
    assert data.weed is None
    assert data.is_sample is False


@pytest.mark.asyncio
async def test_an_unpublished_hour_is_retried_one_hour_earlier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A blank `today` on the newest announcement is a publication gap, not
    'no pollen in Korea', so the previous stamp is tried before giving up.

    The candidate stamps are injected rather than derived from the wall clock:
    before 07:00 the service only has one candidate hour, so a test that
    computed them itself passed in the evening and failed in the morning.
    """
    stamps = ["2026101512", "2026101506"]
    monkeypatch.setattr(pollen_service, "_announce_candidates", lambda now: stamps)
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        stamp = request.url.params["time"]
        seen.append(stamp)
        return httpx.Response(200, json=_ok_payload(today="" if stamp == stamps[0] else "1"))

    async with _client(handler) as c:
        data = await pollen_service.fetch_pollen(37.5665, 126.9780, c, api_key="k")

    assert data.tree == PollenLevel.MODERATE
    assert seen == [stamps[0]] * 3 + [stamps[1]] * 3  # both operations per stamp


def test_announce_candidates_are_newest_published_hour_first() -> None:
    """KMA publishes on 06, 12 and 18, so the newest one already happened is
    the one to ask for. Before 06:00 there is nothing published today yet."""
    assert pollen_service._announce_candidates(dt.datetime(2026, 10, 15, 19, 5)) == [
        "2026101518",
        "2026101512",
    ]
    assert pollen_service._announce_candidates(dt.datetime(2026, 10, 15, 13, 0)) == [
        "2026101512",
        "2026101506",
    ]
    assert pollen_service._announce_candidates(dt.datetime(2026, 10, 15, 3, 0)) == ["2026101506"]


@pytest.mark.asyncio
async def test_provider_down_degrades_to_empty_not_to_the_sample() -> None:
    """The important one. An outage must not silently become fake data."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("upstream down")

    async with _client(handler) as c:
        data = await pollen_service.fetch_pollen(37.5665, 126.9780, c, api_key="test-key")

    assert data.is_sample is False
    assert data.tree is None
    assert data.weed is None


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 401, 500])
async def test_non_2xx_degrades_to_empty(status: int) -> None:
    async with _client(lambda r: httpx.Response(status, json={})) as c:
        data = await pollen_service.fetch_pollen(37.5665, 126.9780, c, api_key="k")

    assert data.is_sample is False
    assert data.tree is None


@pytest.mark.asyncio
async def test_malformed_json_degrades_to_empty() -> None:
    async with _client(lambda r: httpx.Response(200, text="<html>not json</html>")) as c:
        data = await pollen_service.fetch_pollen(37.5665, 126.9780, c, api_key="k")

    assert data.is_sample is False
    assert data.tree is None


@pytest.mark.asyncio
async def test_an_unserved_province_is_not_called_at_all() -> None:
    """Gwangju/Gangwon/Jeonbuk/Jeonnam have no station in KMA's index. A
    coordinate there must read as no data, not as a neighbour's pollen."""
    async with _client(lambda r: pytest.fail("must not call the provider")) as c:
        data = await pollen_service.fetch_pollen(35.1595, 126.8526, c, api_key="k")  # Gwangju

    assert data == pollen_service.PollenData()
    assert data.is_sample is False


def test_the_key_never_reaches_the_logs(caplog) -> None:
    """httpx exception text carries the full request URL, serviceKey included,
    so the degrade paths log without it."""

    async def run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("boom")

        async with _client(handler) as c:
            await pollen_service.fetch_pollen(37.5665, 126.9780, c, api_key="super-secret-key")

    with caplog.at_level("WARNING"):
        import asyncio

        asyncio.run(run())

    assert "super-secret-key" not in caplog.text


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"response": {}},
        {"response": {"body": {"items": {"item": []}}}},
        {"response": {"body": {"items": {"item": "unexpected"}}}},
        {"response": {"header": {"resultCode": "30"}}},
        {"response": {"body": {"items": {"item": {"today": "매우높음"}}}}},
        [],
        None,
    ],
)
def test_unrecognised_shapes_parse_to_empty(payload: object) -> None:
    """The provider changes shape between seasons, so anything unexpected must
    parse to 'no data' instead of raising."""
    assert pollen_service.parse_kma_today(payload) is None


def test_a_single_item_may_arrive_as_an_object() -> None:
    payload = {"response": {"body": {"items": {"item": {"today": "2"}}}}}
    assert pollen_service.parse_kma_today(payload) == PollenLevel.HIGH


def test_unparseable_grades_are_ignored_not_zeroed() -> None:
    assert pollen_service.parse_kma_today(_ok_payload(today=None)) is None
    assert pollen_service.parse_kma_today(_ok_payload(today="  ")) is None


def test_grade_folds_onto_three_levels() -> None:
    assert pollen_service._grade_to_level("0") == PollenLevel.LOW
    assert pollen_service._grade_to_level("1") == PollenLevel.MODERATE
    assert pollen_service._grade_to_level("2") == PollenLevel.HIGH
    assert pollen_service._grade_to_level("3") == PollenLevel.HIGH  # 매우높음 reads as HIGH


@pytest.mark.parametrize(
    ("lat", "lon", "expected"),
    [
        (37.5665, 126.9780, "1100000000"),  # Seoul
        (35.1796, 129.0756, "2600000000"),  # Busan
        (33.4996, 126.5312, "5000000000"),  # Jeju
        (35.5384, 129.3114, "3100000000"),  # Ulsan
        (37.4138, 127.5183, "4100000000"),  # Suwon -> Gyeonggi
    ],
)
def test_nearest_region_code(lat: float, lon: float, expected: str) -> None:
    assert pollen_service._nearest_area_no(lat, lon) == expected


@pytest.mark.parametrize(
    ("lat", "lon", "name"),
    [
        (35.1595, 126.8526, "Gwangju"),
        (37.8228, 128.1555, "Gangwon"),
        (35.7175, 127.1530, "Jeonbuk"),
        (34.8679, 126.9910, "Jeonnam"),
    ],
)
def test_provinces_the_provider_does_not_serve_have_no_code(
    lat: float, lon: float, name: str
) -> None:
    """KMA's station list has nothing under 29/42/45/46."""
    assert pollen_service._nearest_area_no(lat, lon) is None, name


def test_the_three_endpoints_are_the_ones_the_provider_serves() -> None:
    """Guessing the service name is how this got here: the plausible-looking
    HealthWeatherIdxServiceV3/getPlrsIdxTodyList answers 400 NO_OPENAPI_SERVICE."""
    assert pollen_service._KMA_OAK.endswith("HealthWthrIdxServiceV3/getOakPollenRiskIdxV3")
    assert pollen_service._KMA_PINE.endswith("HealthWthrIdxServiceV3/getPinePollenRiskIdxV3")
    assert pollen_service._KMA_WEEDS.endswith("HealthWthrIdxServiceV3/getWeedsPollenRiskndxV3")
