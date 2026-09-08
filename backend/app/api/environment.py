import asyncio
import logging
from typing import Annotated

import httpx
from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.enums import PollenLevel, RiskLevel
from app.services import air_quality_service as aqs
from app.services import pollen_service as ps
from app.services import risk
from app.services import weather_service as ws

logger = logging.getLogger(__name__)

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
    pollen_is_sample: bool


async def _gather(lat: float, lon: float) -> EnvironmentResponse:
    """Fetch pollen/AQI/weather concurrently and feed the deterministic risk
    scorer. Each provider degrades independently (see the *_service modules)
    so one being down/unkeyed never 500s this endpoint; return_exceptions here
    is a second line of defense in case a provider's own guard is bypassed —
    an unexpected failure just becomes an empty block instead of a 500."""
    key = get_settings().pollen_api_key
    async with httpx.AsyncClient() as client:
        weather, air, pollen = await asyncio.gather(
            ws.fetch_weather(lat, lon, client),
            aqs.fetch_air_quality(lat, lon, client),
            ps.fetch_pollen(lat, lon, key),
            return_exceptions=True,
        )
    if isinstance(weather, BaseException):
        logger.warning("weather provider raised unexpectedly", exc_info=weather)
        weather = ws.WeatherData()
    if isinstance(air, BaseException):
        logger.warning("air quality provider raised unexpectedly", exc_info=air)
        air = aqs.AirQualityData()
    if isinstance(pollen, BaseException):
        logger.warning("pollen provider raised unexpectedly", exc_info=pollen)
        pollen = ps.PollenData()
    pts, level = risk.score(
        risk.EnvInput(
            tree_pollen=pollen.tree,
            grass_pollen=pollen.grass,
            weed_pollen=pollen.weed,
            pm25=air.pm25,
            pm10=air.pm10,
            wind_speed=weather.wind_speed,
        )
    )
    return EnvironmentResponse(
        latitude=lat,
        longitude=lon,
        pollen=PollenBlock(tree=pollen.tree, grass=pollen.grass, weed=pollen.weed),
        air_quality=AirQualityBlock(pm25=air.pm25, pm10=air.pm10),
        weather=WeatherBlock(
            temperature=weather.temperature,
            humidity=weather.humidity,
            wind=weather.wind_speed,
        ),
        points=pts,
        risk=level,
        pollen_is_sample=pollen.is_sample,
    )


@router.get("/current")
async def current(
    lat: Annotated[float, Query(ge=-90, le=90)],
    lon: Annotated[float, Query(ge=-180, le=180)],
) -> EnvironmentResponse:
    return await _gather(lat, lon)
