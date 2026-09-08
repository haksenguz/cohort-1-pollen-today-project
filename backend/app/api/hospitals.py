from collections.abc import AsyncGenerator
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.services.hospital_service import (
    DEFAULT_RADIUS_M,
    HospitalResultData,
    PlacesClient,
    find_nearby_hospitals,
)

router = APIRouter(prefix="/api/hospitals", tags=["hospitals"])


async def get_http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        yield client


HttpClientDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


class HospitalOut(BaseModel):
    place_id: str | None = None
    name: str
    address: str | None = None
    distance_m: int | None = None
    specialty: str | None = None
    is_open: bool | None = None
    phone: str | None = None
    rank: int


def _to_out(result: HospitalResultData) -> HospitalOut:
    return HospitalOut(
        place_id=result.place_id,
        name=result.name,
        address=result.address,
        distance_m=result.distance_m,
        specialty=result.specialty,
        is_open=result.is_open,
        phone=result.phone,
        rank=result.rank,
    )


class HospitalNearbyResponse(BaseModel):
    latitude: float
    longitude: float
    specialty: str | None
    provider_available: bool
    count: int
    results: list[HospitalOut]


@router.get("/nearby")
async def nearby(
    http_client: HttpClientDep,
    settings: SettingsDep,
    lat: Annotated[float, Query(ge=-90, le=90)],
    lon: Annotated[float, Query(ge=-180, le=180)],
    specialty: Annotated[str | None, Query(max_length=40)] = None,
    radius_m: Annotated[int, Query(ge=100, le=50000)] = DEFAULT_RADIUS_M,
    open_now: bool | None = None,
) -> HospitalNearbyResponse:
    """Nearby medical facilities, filtered by specialty/opening status and
    ranked by distance (docs §5, §12). Never 500s on a dead upstream: a
    provider failure comes back as a normal response with
    `provider_available=false` and an empty `results` list.
    """
    places_client = PlacesClient(http_client, settings.google_maps_api_key)
    outcome = await find_nearby_hospitals(
        places_client,
        latitude=lat,
        longitude=lon,
        specialty=specialty,
        radius_m=radius_m,
        open_now=open_now,
    )
    return HospitalNearbyResponse(
        latitude=lat,
        longitude=lon,
        specialty=specialty.upper() if specialty else None,
        provider_available=outcome.provider_available,
        count=len(outcome.results),
        results=[_to_out(r) for r in outcome.results],
    )
