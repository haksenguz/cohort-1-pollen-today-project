"""Endpoint-level tests for /api/environment/current. Fully offline: the HTTP
providers are monkeypatched at the app.api.environment module boundary, so no
socket is ever opened."""

from fastapi.testclient import TestClient

from app.api import environment
from app.core.enums import PollenLevel
from app.main import app
from app.services.air_quality_service import AirQualityData
from app.services.pollen_service import PollenData
from app.services.weather_service import WeatherData

client = TestClient(app)


async def _ok_weather(lat, lon, http_client):
    return WeatherData(temperature=22, humidity=50, wind_speed=3.5)


async def _ok_air(lat, lon, http_client):
    return AirQualityData(pm25=10, pm10=20)


async def _ok_pollen(lat, lon, http_client, api_key=""):
    return PollenData(tree=PollenLevel.HIGH, grass=PollenLevel.LOW, weed=PollenLevel.LOW)


async def _failing_weather(lat, lon, http_client):
    raise RuntimeError("boom")


def test_current_returns_populated_response_when_all_providers_succeed(monkeypatch):
    monkeypatch.setattr(environment.ws, "fetch_weather", _ok_weather)
    monkeypatch.setattr(environment.aqs, "fetch_air_quality", _ok_air)
    monkeypatch.setattr(environment.ps, "fetch_pollen", _ok_pollen)

    resp = client.get("/api/environment/current", params={"lat": 37.5, "lon": 127.0})

    assert resp.status_code == 200
    body = resp.json()
    assert body["weather"]["temperature"] == 22
    assert body["air_quality"]["pm25"] == 10
    assert body["pollen"]["tree"] == "HIGH"
    assert body["pollen_is_sample"] is False
    assert body["risk"] in ("LOW", "MODERATE", "HIGH")
    assert body["risk_available"] is True


def test_current_reports_no_risk_when_every_provider_is_silent(monkeypatch):
    """Nothing answered, so there is nothing to score.

    The score of that state is zero points, which is LOW. Reporting LOW says
    "you are fine today" on a day the app could not ask anybody.
    """

    async def _empty_weather(lat, lon, http_client):
        return WeatherData()

    async def _empty_air(lat, lon, http_client):
        return AirQualityData()

    async def _empty_pollen(lat, lon, http_client, api_key=""):
        return PollenData()

    monkeypatch.setattr(environment.ws, "fetch_weather", _empty_weather)
    monkeypatch.setattr(environment.aqs, "fetch_air_quality", _empty_air)
    monkeypatch.setattr(environment.ps, "fetch_pollen", _empty_pollen)

    resp = client.get("/api/environment/current", params={"lat": 37.5, "lon": 127.0})

    assert resp.status_code == 200
    body = resp.json()
    assert body["risk"] is None
    assert body["risk_available"] is False


def test_current_does_not_score_the_sample_pollen(monkeypatch):
    """The unkeyed sample must not push the score up.

    The sample says tree pollen is HIGH, so a scorer that counted it reported
    "moderate" while the UI said the pollen was being withheld.
    """

    async def _ok_weather(lat, lon, http_client):
        return WeatherData(temperature=22, humidity=50, wind_speed=1.0)

    async def _empty_air(lat, lon, http_client):
        return AirQualityData()

    async def _sample_pollen(lat, lon, http_client, api_key=""):
        return PollenData(tree=PollenLevel.HIGH, is_sample=True)

    monkeypatch.setattr(environment.ws, "fetch_weather", _ok_weather)
    monkeypatch.setattr(environment.aqs, "fetch_air_quality", _empty_air)
    monkeypatch.setattr(environment.ps, "fetch_pollen", _sample_pollen)

    resp = client.get("/api/environment/current", params={"lat": 37.5, "lon": 127.0})

    body = resp.json()
    assert body["pollen_is_sample"] is True
    assert body["points"] == 0
    assert body["risk"] == "LOW"
    assert body["risk_available"] is True


def test_current_degrades_instead_of_500_when_a_provider_raises(monkeypatch):
    """A provider failure (network down, unhandled exception, ...) must still
    yield a 200 with the other blocks populated and the failed block empty —
    never a 500."""
    monkeypatch.setattr(environment.ws, "fetch_weather", _failing_weather)
    monkeypatch.setattr(environment.aqs, "fetch_air_quality", _ok_air)
    monkeypatch.setattr(environment.ps, "fetch_pollen", _ok_pollen)

    resp = client.get("/api/environment/current", params={"lat": 37.5, "lon": 127.0})

    assert resp.status_code == 200
    body = resp.json()
    assert body["weather"] == {"temperature": None, "humidity": None, "wind": None}
    assert body["air_quality"]["pm25"] == 10
    assert body["pollen"]["tree"] == "HIGH"
