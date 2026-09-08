import httpx
import pytest

from app.core.enums import PollenLevel
from app.services import air_quality_service as aqs
from app.services import pollen_service as ps
from app.services import weather_service as ws


def _client(handler) -> httpx.AsyncClient:
    """Offline httpx.AsyncClient — every request is served by `handler`, no
    socket ever opens."""
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_parse_weather():
    payload = {"current": {"temperature_2m": 25, "relative_humidity_2m": 55, "wind_speed_10m": 4.2}}
    w = ws.parse_weather(payload)
    assert w.temperature == 25
    assert w.humidity == 55
    assert w.wind_speed == 4.2


def test_parse_weather_missing_current():
    assert ws.parse_weather({}).temperature is None


def test_parse_air_quality():
    a = aqs.parse_air_quality({"current": {"pm2_5": 42, "pm10": 68}})
    assert a.pm25 == 42
    assert a.pm10 == 68


def test_pollen_level_bands():
    assert ps.level_from_count(200, (15, 90)) is PollenLevel.HIGH
    assert ps.level_from_count(30, (15, 90)) is PollenLevel.MODERATE
    assert ps.level_from_count(2, (15, 90)) is PollenLevel.LOW
    assert ps.level_from_count(None, (15, 90)) is None


def test_pollen_sample_is_marked():
    p = ps.sample_pollen()
    assert p.is_sample is True
    assert p.tree is PollenLevel.HIGH


@pytest.mark.asyncio
async def test_fetch_weather_success_offline():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "current": {"temperature_2m": 21, "relative_humidity_2m": 60, "wind_speed_10m": 3}
            },
        )

    async with _client(handler) as client:
        w = await ws.fetch_weather(37.5, 127.0, client)
    assert w.temperature == 21
    assert w.wind_speed == 3


@pytest.mark.asyncio
async def test_fetch_weather_http_error_degrades_to_empty():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    async with _client(handler) as client:
        w = await ws.fetch_weather(37.5, 127.0, client)
    assert w == ws.WeatherData()


@pytest.mark.asyncio
async def test_fetch_weather_network_error_degrades_to_empty():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    async with _client(handler) as client:
        w = await ws.fetch_weather(37.5, 127.0, client)
    assert w == ws.WeatherData()


@pytest.mark.asyncio
async def test_fetch_air_quality_success_offline():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"current": {"pm2_5": 12, "pm10": 20}})

    async with _client(handler) as client:
        a = await aqs.fetch_air_quality(37.5, 127.0, client)
    assert a.pm25 == 12
    assert a.pm10 == 20


@pytest.mark.asyncio
async def test_fetch_air_quality_http_error_degrades_to_empty():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    async with _client(handler) as client:
        a = await aqs.fetch_air_quality(37.5, 127.0, client)
    assert a == aqs.AirQualityData()


@pytest.mark.asyncio
async def test_fetch_air_quality_timeout_degrades_to_empty():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    async with _client(handler) as client:
        a = await aqs.fetch_air_quality(37.5, 127.0, client)
    assert a == aqs.AirQualityData()


@pytest.mark.asyncio
async def test_fetch_pollen_unkeyed_returns_marked_sample():
    p = await ps.fetch_pollen(37.5, 127.0, api_key="")
    assert p.is_sample is True
