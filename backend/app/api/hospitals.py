from collections.abc import AsyncGenerator
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.services.hospital_service import (
    DEFAULT_RADIUS_M,
    HospitalResultData,
    NaverLocalClient,
    find_nearby_hospitals,
)

router = APIRouter(prefix="/api/hospitals", tags=["hospitals"])


async def get_http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        yield client


HttpClientDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


class HospitalOut(BaseModel):
    name: str
    address: str | None = None
    distance_m: int | None = None
    specialty: str | None = None
    category: str | None = None
    phone: str | None = None
    rank: int


def _to_out(result: HospitalResultData) -> HospitalOut:
    return HospitalOut(
        name=result.name,
        address=result.address,
        distance_m=result.distance_m,
        specialty=result.specialty,
        category=result.category,
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
    location_query: Annotated[
        str | None,
        Query(
            max_length=80,
            description=(
                "Free-text place/area name (e.g. a city or district) mixed into the "
                "Naver Local Search keyword. Naver has no coordinate-radius search, "
                "so without this the keyword is specialty-only and results are "
                "ranked by distance but may come from anywhere in the country."
            ),
        ),
    ] = None,
    radius_m: Annotated[
        int,
        Query(
            ge=100,
            le=50000,
            description=(
                "Client-side distance filter applied after ranking. Naver Local "
                "Search has no radius parameter of its own — this never reaches "
                "the upstream request."
            ),
        ),
    ] = DEFAULT_RADIUS_M,
) -> HospitalNearbyResponse:
    """Nearby medical facilities, filtered by specialty and ranked by
    distance (docs §5, §12). Never 500s on a dead upstream: a provider
    failure comes back as a normal response with `provider_available=false`
    and an empty `results` list.

    Two honest limitations inherited from the Naver Local Search API:

    - **At most 5 results.** Local Search caps `display` at 5 and only
      accepts `start=1` — there is no pagination to fetch more.
    - **No opening-hours data.** Naver Local Search does not return an
      "open now" equivalent, so there is no `open_now` filter here (the
      Places-based version had one; it was removed, not faked).
    """
    naver_client = NaverLocalClient(
        http_client, settings.naver_client_id, settings.naver_client_secret
    )
    outcome = await find_nearby_hospitals(
        naver_client,
        latitude=lat,
        longitude=lon,
        specialty=specialty,
        location_query=location_query,
        radius_m=radius_m,
    )
    return HospitalNearbyResponse(
        latitude=lat,
        longitude=lon,
        specialty=specialty.upper() if specialty else None,
        provider_available=outcome.provider_available,
        count=len(outcome.results),
        results=[_to_out(r) for r in outcome.results],
    )
