"""Air quality via Open-Meteo Air Quality API (no API key needed). Spec §2, §8."""

from dataclasses import dataclass

import httpx

_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"


@dataclass
class AirQualityData:
    pm25: float | None = None
    pm10: float | None = None


def parse_air_quality(payload: dict) -> AirQualityData:
    cur = payload.get("current", {})
    return AirQualityData(pm25=cur.get("pm2_5"), pm10=cur.get("pm10"))


async def fetch_air_quality(lat: float, lon: float, client: httpx.AsyncClient) -> AirQualityData:
    r = await client.get(
        _URL,
        params={"latitude": lat, "longitude": lon, "current": "pm2_5,pm10"},
        timeout=8.0,
    )
    r.raise_for_status()
    return parse_air_quality(r.json())
