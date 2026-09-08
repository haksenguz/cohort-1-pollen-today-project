"""Nearby hospital finder: Google Places client, specialty filter, distance
ranking, opening status (docs §5, §12, §18).

The Places HTTP call is isolated behind `PlacesClient`, which takes an
injected `httpx.AsyncClient`. Tests build that client with
`httpx.MockTransport`, so nothing here ever touches the real network.

Provider failure (timeout, non-2xx, bad JSON, API-level error status) is
caught and turned into an empty, clearly-flagged result — see
`HospitalSearchOutcome.provider_available`. The API layer must not let a dead
upstream turn into a 500.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)

PLACES_NEARBY_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"

DEFAULT_RADIUS_M = 5000
DEFAULT_LIMIT = 10

# Specialty label -> Places `keyword` search term. An unrecognized label is
# still sent through as free-text keyword rather than rejected, since Places
# accepts arbitrary keywords (docs §5 "Relevant specialty" is open-ended).
SPECIALTY_KEYWORDS: dict[str, str] = {
    "ENT": "ENT clinic",
    "ALLERGY": "allergy clinic",
    "PULMONOLOGY": "pulmonology",
    "DERMATOLOGY": "dermatology clinic",
    "PEDIATRICS": "pediatric clinic",
    "EMERGENCY": "emergency room",
    "GENERAL": "hospital",
}


class PlacesClientError(Exception):
    """The Places provider failed or returned something we can't use."""


class PlacesClient:
    """Thin, injectable wrapper around the Google Places Nearby Search API."""

    def __init__(self, http_client: httpx.AsyncClient, api_key: str) -> None:
        self._http = http_client
        self._api_key = api_key

    async def nearby_search(
        self,
        *,
        latitude: float,
        longitude: float,
        radius_m: int,
        keyword: str | None,
    ) -> list[dict[str, Any]]:
        if not self._api_key:
            raise PlacesClientError("google_maps_api_key is not configured")

        params: dict[str, Any] = {
            "location": f"{latitude},{longitude}",
            "radius": radius_m,
            "type": "hospital",
            "key": self._api_key,
        }
        if keyword:
            params["keyword"] = keyword

        try:
            resp = await self._http.get(PLACES_NEARBY_URL, params=params)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise PlacesClientError(f"Places API request failed: {exc}") from exc

        try:
            payload = resp.json()
        except ValueError as exc:
            raise PlacesClientError("Places API returned a non-JSON response") from exc

        status = payload.get("status")
        if status not in ("OK", "ZERO_RESULTS"):
            message = payload.get("error_message", "")
            raise PlacesClientError(f"Places API status={status}: {message}")

        return payload.get("results", [])


@dataclass
class HospitalResultData:
    place_id: str | None
    name: str
    address: str | None
    distance_m: int | None
    specialty: str | None
    is_open: bool | None
    phone: str | None
    rank: int = 0


@dataclass
class HospitalSearchOutcome:
    results: list[HospitalResultData] = field(default_factory=list)
    provider_available: bool = True
    error: str | None = None


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    """Great-circle distance in meters between two lat/lon points."""
    earth_radius_m = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return round(2 * earth_radius_m * math.asin(math.sqrt(a)))


def _parse_place(
    raw: dict[str, Any], origin_lat: float, origin_lon: float, specialty: str | None
) -> HospitalResultData | None:
    name = raw.get("name")
    if not name:
        return None

    location = raw.get("geometry", {}).get("location", {})
    lat, lon = location.get("lat"), location.get("lng")
    distance_m = (
        _haversine_m(origin_lat, origin_lon, lat, lon)
        if lat is not None and lon is not None
        else None
    )

    opening_hours = raw.get("opening_hours") or {}

    return HospitalResultData(
        place_id=raw.get("place_id"),
        name=name,
        address=raw.get("vicinity") or raw.get("formatted_address"),
        distance_m=distance_m,
        specialty=specialty.upper() if specialty else None,
        is_open=opening_hours.get("open_now"),
        phone=raw.get("formatted_phone_number") or raw.get("international_phone_number"),
    )


async def find_nearby_hospitals(
    client: PlacesClient,
    *,
    latitude: float,
    longitude: float,
    specialty: str | None = None,
    radius_m: int = DEFAULT_RADIUS_M,
    open_now: bool | None = None,
    limit: int = DEFAULT_LIMIT,
) -> HospitalSearchOutcome:
    """Search, filter by specialty/opening status, and rank by distance.

    Never raises: a provider failure comes back as
    `HospitalSearchOutcome(provider_available=False, error=...)` with an empty
    result list so the caller can return a normal (200) response.
    """
    keyword = SPECIALTY_KEYWORDS.get(specialty.upper(), specialty) if specialty else None

    try:
        raw_places = await client.nearby_search(
            latitude=latitude, longitude=longitude, radius_m=radius_m, keyword=keyword
        )
    except PlacesClientError as exc:
        logger.warning("hospital provider unavailable: %s", exc)
        return HospitalSearchOutcome(results=[], provider_available=False, error=str(exc))

    parsed = [
        place
        for raw in raw_places
        if (place := _parse_place(raw, latitude, longitude, specialty)) is not None
    ]

    if open_now is not None:
        parsed = [p for p in parsed if p.is_open == open_now]

    parsed.sort(key=lambda p: (p.distance_m is None, p.distance_m or 0))
    ranked = parsed[:limit]
    for i, place in enumerate(ranked, start=1):
        place.rank = i

    return HospitalSearchOutcome(results=ranked, provider_available=True)
