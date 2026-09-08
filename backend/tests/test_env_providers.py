from app.core.enums import PollenLevel
from app.services import air_quality_service as aqs
from app.services import pollen_service as ps
from app.services import weather_service as ws


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
