"""Pollen provider: real KMA data when keyed, flagged sample when not.

The point of these tests is the `is_sample` contract. A caller must be able to
tell fabricated data from real data, and "provider returned nothing" must never
be dressed up as the sample.

Field names in the KMA payload are not yet confirmed against the provider's own
manual, see docs/research/pollen-providers.md, so the parser is deliberately
forgiving. That is pinned here too.
"""

import httpx
import pytest

from app.core.enums import PollenLevel
from app.services import pollen_service


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _kma_payload(**item) -> dict:
    return {"response": {"body": {"items": {"item": [item]}}}}


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
        # Seoul centroid -> sido code 11
        assert request.url.params["areaNo"] == "11"
        return httpx.Response(200, json=_kma_payload(oak="1", pine="3", weed="0"))

    async with _client(handler) as c:
        data = await pollen_service.fetch_pollen(37.5665, 126.9780, c, api_key="test-key")

    assert data.is_sample is False
    assert data.tree == PollenLevel.HIGH  # max(oak=1, pine=3) -> HIGH
    assert data.weed == PollenLevel.LOW
    assert data.grass is None  # provider reports no grass


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
@pytest.mark.parametrize("status", [401, 500])
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


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"response": {}},
        {"response": {"body": {"items": {"item": []}}}},
        {"response": {"body": {"items": {"item": "unexpected"}}}},
    ],
)
def test_unrecognised_shapes_parse_to_empty(payload: dict) -> None:
    """Field names are unconfirmed, so an unexpected envelope must not raise."""
    data = pollen_service.parse_kma_pollen(payload)
    assert data == pollen_service.PollenData()


def test_a_single_item_may_arrive_as_an_object() -> None:
    payload = {"response": {"body": {"items": {"item": {"oak": "2", "weed": "1"}}}}}
    data = pollen_service.parse_kma_pollen(payload)
    assert data.tree == PollenLevel.HIGH
    assert data.weed == PollenLevel.MODERATE


def test_unparseable_grades_are_ignored_not_zeroed() -> None:
    """KMA omits or blanks a species out of season. Blank is not 'low'."""
    data = pollen_service.parse_kma_pollen(_kma_payload(oak="", pine=None, weed="2"))
    assert data.tree is None
    assert data.weed == PollenLevel.HIGH


def test_nearest_region_code() -> None:
    assert pollen_service._nearest_area_no(37.5665, 126.9780) == "11"  # Seoul
    assert pollen_service._nearest_area_no(35.1796, 129.0756) == "26"  # Busan
    assert pollen_service._nearest_area_no(33.4996, 126.5312) == "50"  # Jeju
