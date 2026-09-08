"""Weather via Open-Meteo (no API key needed). Spec §2, §8."""

from dataclasses import dataclass

import httpx

_URL = "https://api.open-meteo.com/v1/forecast"


@dataclass
class WeatherData:
    temperature: float | None = None
    humidity: float | None = None
    wind_speed: float | None = None


def parse_weather(payload: dict) -> WeatherData:
    cur = payload.get("current", {})
    return WeatherData(
        temperature=cur.get("temperature_2m"),
        humidity=cur.get("relative_humidity_2m"),
        wind_speed=cur.get("wind_speed_10m"),
    )


async def fetch_weather(lat: float, lon: float, client: httpx.AsyncClient) -> WeatherData:
    r = await client.get(
        _URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m",
            "wind_speed_unit": "ms",
        },
        timeout=8.0,
    )
    r.raise_for_status()
    return parse_weather(r.json())
