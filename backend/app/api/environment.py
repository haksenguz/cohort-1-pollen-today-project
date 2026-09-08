from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.core.enums import PollenLevel, RiskLevel
from app.services import risk

router = APIRouter(prefix="/api/environment", tags=["environment"])


class PollenBlock(BaseModel):
    tree: PollenLevel | None = None
    grass: PollenLevel | None = None
    weed: PollenLevel | None = None


class AirQualityBlock(BaseModel):
    pm25: float | None = None
    pm10: float | None = None


class WeatherBlock(BaseModel):
    temperature: float | None = None
    humidity: float | None = None
    wind: float | None = None


class EnvironmentResponse(BaseModel):
    latitude: float
    longitude: float
    pollen: PollenBlock
    air_quality: AirQualityBlock
    weather: WeatherBlock
    points: int
    risk: RiskLevel


def _stub_conditions(lat: float, lon: float) -> EnvironmentResponse:
    """Placeholder until pollen/AQI/weather providers are wired (Phase 1)."""
    pollen = PollenBlock(tree=PollenLevel.HIGH, grass=PollenLevel.MODERATE, weed=PollenLevel.LOW)
    aqi = AirQualityBlock(pm25=42, pm10=68)
    weather = WeatherBlock(temperature=25, humidity=55, wind=4.2)
    pts, level = risk.score(
        risk.EnvInput(
            tree_pollen=pollen.tree,
            grass_pollen=pollen.grass,
            weed_pollen=pollen.weed,
            pm25=aqi.pm25,
            pm10=aqi.pm10,
            wind_speed=weather.wind,
        )
    )
    return EnvironmentResponse(
        latitude=lat,
        longitude=lon,
        pollen=pollen,
        air_quality=aqi,
        weather=weather,
        points=pts,
        risk=level,
    )


@router.get("/current")
async def current(
    lat: Annotated[float, Query(ge=-90, le=90)],
    lon: Annotated[float, Query(ge=-180, le=180)],
) -> EnvironmentResponse:
    return _stub_conditions(lat, lon)
