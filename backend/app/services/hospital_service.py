"""Nearby hospital finder: Naver Local Search client, specialty filter, and
distance ranking (docs §5, §12, §18).

The HTTP call is isolated behind `NaverLocalClient`, which takes an injected
`httpx.AsyncClient`. Tests build that client with `httpx.MockTransport`, so
nothing here ever touches the real network.

Naver Local Search (https://openapi.naver.com/v1/search/local.json) takes a
free-text keyword, not a center point + radius — there is no server-side
"nearby" concept and no "open now" field. We build the keyword from the
specialty and an optional `location_query` term, then rank whatever comes
back by haversine distance from the caller's lat/lon ourselves, exactly like
the old Places-based version did. `radius_m` is applied here as a
client-side post-filter on that distance; Naver never sees it.

Provider failure (timeout, non-2xx, bad JSON, an `errorMessage` body) is
caught and turned into an empty, clearly-flagged result — see
`HospitalSearchOutcome.provider_available`. The API layer must not let a dead
upstream turn into a 500.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)

NAVER_LOCAL_SEARCH_URL = "https://openapi.naver.com/v1/search/local.json"

# Naver Local Search hard caps — not configurable, not a client choice:
#   - `display` (results per call) maxes out at 5.
#   - `start` only accepts 1. Unlike Naver's other Search APIs (blog, news,
#     ...) where `start` goes up to 1000, Local Search has no pagination:
#     five results per keyword query is a hard ceiling, not a page size.
NAVER_MAX_DISPLAY = 5

DEFAULT_RADIUS_M = 5000
DEFAULT_LIMIT = 5  # can't ask Naver for more than NAVER_MAX_DISPLAY anyway

_TAG_RE = re.compile(r"<[^>]+>")

# WGS84 sanity bounds, used to defensively catch the legacy KATECH/TM128
# coordinate shape some older Naver Search responses used (see
# `_convert_coordinates`).
_WGS84_LAT_RANGE = (-90.0, 90.0)
_WGS84_LON_RANGE = (-180.0, 180.0)

# Specialty label -> Naver Local Search keyword. Local Search is a
# Korean-market product; Korean search terms return far better matches than
# their English equivalents did against Places. An unrecognized label is
# still sent through as free-text keyword rather than rejected, since Local
# Search accepts arbitrary keywords.
SPECIALTY_KEYWORDS: dict[str, str] = {
    "ENT": "이비인후과",
    "ALLERGY": "알레르기내과",
    "PULMONOLOGY": "호흡기내과",
    "DERMATOLOGY": "피부과",
    "PEDIATRICS": "소아과",
    "EMERGENCY": "응급실",
    "GENERAL": "병원",
}

DEFAULT_KEYWORD = "병원"


class NaverLocalClientError(Exception):
    """The Naver Local Search provider failed or returned something we can't use."""


class NaverLocalClient:
    """Thin, injectable wrapper around the Naver Developers Local Search API."""

    def __init__(self, http_client: httpx.AsyncClient, client_id: str, client_secret: str) -> None:
        self._http = http_client
        self._client_id = client_id
        self._client_secret = client_secret

    async def search(self, *, query: str, display: int = NAVER_MAX_DISPLAY) -> list[dict[str, Any]]:
        if not self._client_id or not self._client_secret:
            raise NaverLocalClientError("naver_client_id/naver_client_secret is not configured")

        params: dict[str, Any] = {
            "query": query,
            "display": min(display, NAVER_MAX_DISPLAY),
            "start": 1,  # the only value Local Search accepts — no paging.
            "sort": "random",
        }
        headers = {
            "X-Naver-Client-Id": self._client_id,
            "X-Naver-Client-Secret": self._client_secret,
        }

        try:
            resp = await self._http.get(NAVER_LOCAL_SEARCH_URL, params=params, headers=headers)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise NaverLocalClientError(f"Naver Local Search request failed: {exc}") from exc

        try:
            payload = resp.json()
        except ValueError as exc:
            raise NaverLocalClientError("Naver Local Search returned a non-JSON response") from exc

        if "errorMessage" in payload:
            raise NaverLocalClientError(
                f"Naver Local Search error {payload.get('errorCode')}: {payload['errorMessage']}"
            )

        return payload.get("items", [])


@dataclass
class HospitalResultData:
    name: str
    address: str | None
    distance_m: int | None
    specialty: str | None
    category: str | None
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


def _strip_tags(text: str) -> str:
    """Naver titles carry <b> tags around the matched keyword — strip them."""
    return _TAG_RE.sub("", text).strip()


def _convert_coordinates(
    mapx: str | float | None, mapy: str | float | None
) -> tuple[float, float] | None:
    """`mapx`/`mapy` are stringified WGS84 longitude/latitude multiplied by
    1e7 (mapx = longitude, mapy = latitude). Some historical Naver Search
    responses used KATECH/TM128 map units instead, which do not divide down
    into valid WGS84 ranges — if that happens here we log it and drop the
    point rather than plot a bogus location.
    """
    if mapx is None or mapy is None:
        return None
    try:
        lon = float(mapx) / 1e7
        lat = float(mapy) / 1e7
    except (TypeError, ValueError):
        return None

    if not (_WGS84_LAT_RANGE[0] <= lat <= _WGS84_LAT_RANGE[1]) or not (
        _WGS84_LON_RANGE[0] <= lon <= _WGS84_LON_RANGE[1]
    ):
        logger.warning(
            "naver local search returned out-of-range WGS84 coords "
            "(legacy KATECH/TM128 format?): mapx=%r mapy=%r",
            mapx,
            mapy,
        )
        return None

    return lat, lon


def _parse_place(
    raw: dict[str, Any], origin_lat: float, origin_lon: float, specialty: str | None
) -> HospitalResultData | None:
    title = raw.get("title")
    if not title:
        return None
    name = _strip_tags(title)
    if not name:
        return None

    coords = _convert_coordinates(raw.get("mapx"), raw.get("mapy"))
    distance_m = _haversine_m(origin_lat, origin_lon, coords[0], coords[1]) if coords else None

    return HospitalResultData(
        name=name,
        address=raw.get("roadAddress") or raw.get("address") or None,
        distance_m=distance_m,
        specialty=specialty.upper() if specialty else None,
        category=raw.get("category") or None,
        phone=raw.get("telephone") or None,
    )


async def find_nearby_hospitals(
    client: NaverLocalClient,
    *,
    latitude: float,
    longitude: float,
    specialty: str | None = None,
    location_query: str | None = None,
    radius_m: int = DEFAULT_RADIUS_M,
    limit: int = DEFAULT_LIMIT,
) -> HospitalSearchOutcome:
    """Search, tag by specialty, filter to `radius_m`, and rank by distance.

    Naver Local Search takes a keyword, not a center point + radius: there is
    no upstream "nearby" concept. `radius_m` is applied here as a
    client-side post-filter on the haversine distance from
    (latitude, longitude) — it is never sent to Naver. Without
    `location_query` the search keyword is specialty-only, so results are
    still ranked by distance but may come from anywhere the keyword matches
    nationally; pass `location_query` (e.g. a city or district name) to bias
    the keyword toward the caller's area.

    Never raises: a provider failure comes back as
    `HospitalSearchOutcome(provider_available=False, error=...)` with an
    empty result list so the caller can return a normal (200) response.
    """
    specialty_term = (
        SPECIALTY_KEYWORDS.get(specialty.upper(), specialty) if specialty else DEFAULT_KEYWORD
    )
    query = f"{location_query} {specialty_term}".strip() if location_query else specialty_term

    try:
        raw_items = await client.search(query=query, display=NAVER_MAX_DISPLAY)
    except NaverLocalClientError as exc:
        logger.warning("hospital provider unavailable: %s", exc)
        return HospitalSearchOutcome(results=[], provider_available=False, error=str(exc))

    parsed = [
        place
        for raw in raw_items
        if (place := _parse_place(raw, latitude, longitude, specialty)) is not None
    ]

    parsed = [p for p in parsed if p.distance_m is None or p.distance_m <= radius_m]

    parsed.sort(key=lambda p: (p.distance_m is None, p.distance_m or 0))
    ranked = parsed[:limit]
    for i, place in enumerate(ranked, start=1):
        place.rank = i

    return HospitalSearchOutcome(results=ranked, provider_available=True)
