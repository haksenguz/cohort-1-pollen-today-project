"""Pollen levels via KMA's 꽃가루농도위험지수 (pollen concentration risk index) —
see docs/research/pollen-providers.md for why this provider was picked over
Google Pollen, Ambee, and Tomorrow.io (none of which have confirmed, free,
Korea-specific coverage). Korea isn't covered by the keyless providers, so
this uses the keyed KMA provider when configured, and a clearly-marked
deterministic sample otherwise — never both at once.

The response envelope (`response.header`/`response.body.items.item`) follows
data.go.kr's platform-wide OpenAPI convention. The item-level field names
(`oak`/`pine`/`weed`) and the `areaNo` region-code scheme are the part not
yet confirmed against KMA's own manual (see the research doc) — that's why
parsing here is defensive: an unexpected shape degrades to empty data, same
as a network failure, rather than raising.
"""

import datetime as dt
import logging
from dataclasses import dataclass

import httpx

from app.core.enums import PollenLevel

logger = logging.getLogger(__name__)

# prototype grains/m3 cutoffs, used only by the deterministic sample below —
# the real KMA provider ships its own 4-level grade (see _level_from_grade).
_TREE = (15, 90)
_GRASS = (5, 20)
_WEED = (10, 50)

_KMA_URL = "https://apis.data.go.kr/1360000/HealthWeatherIdxServiceV3/getPlrsIdxTodyList"

# KOSTAT/행정안전부 법정동코드 시도 prefixes (the standard Korean top-level
# administrative region codes) used here as the KMA `areaNo`, with each
# region's approximate centroid so a lat/lon picks the nearest one. This
# platform-wide code scheme is well documented; whether this specific KMA
# service expects it verbatim is the one open question noted above.
_SIDO_CENTROIDS: tuple[tuple[str, float, float], ...] = (
    ("11", 37.5665, 126.9780),  # Seoul
    ("26", 35.1796, 129.0756),  # Busan
    ("27", 35.8714, 128.6014),  # Daegu
    ("28", 37.4563, 126.7052),  # Incheon
    ("29", 35.1595, 126.8526),  # Gwangju
    ("30", 36.3504, 127.3845),  # Daejeon
    ("31", 35.5384, 129.3114),  # Ulsan
    ("36", 36.4801, 127.2890),  # Sejong
    ("41", 37.4138, 127.5183),  # Gyeonggi
    ("42", 37.8228, 128.1555),  # Gangwon
    ("43", 36.6357, 127.4913),  # Chungbuk
    ("44", 36.5184, 126.8000),  # Chungnam
    ("45", 35.7175, 127.1530),  # Jeonbuk
    ("46", 34.8679, 126.9910),  # Jeonnam
    ("47", 36.4919, 128.8889),  # Gyeongbuk
    ("48", 35.4606, 128.2132),  # Gyeongnam
    ("50", 33.4996, 126.5312),  # Jeju
)


@dataclass
class PollenData:
    tree: PollenLevel | None = None
    grass: PollenLevel | None = None
    weed: PollenLevel | None = None
    is_sample: bool = False


def level_from_count(count: float | None, low_hi: tuple[int, int]) -> PollenLevel | None:
    if count is None:
        return None
    low, hi = low_hi
    if count > hi:
        return PollenLevel.HIGH
    if count >= low:
        return PollenLevel.MODERATE
    return PollenLevel.LOW


def parse_counts(tree: float | None, grass: float | None, weed: float | None) -> PollenData:
    return PollenData(
        tree=level_from_count(tree, _TREE),
        grass=level_from_count(grass, _GRASS),
        weed=level_from_count(weed, _WEED),
    )


def sample_pollen() -> PollenData:
    """Deterministic sample used when no provider key is configured."""
    return PollenData(
        tree=PollenLevel.HIGH,
        grass=PollenLevel.MODERATE,
        weed=PollenLevel.LOW,
        is_sample=True,
    )


def _nearest_area_no(lat: float, lon: float) -> str:
    return min(
        _SIDO_CENTROIDS,
        key=lambda region: (region[1] - lat) ** 2 + (region[2] - lon) ** 2,
    )[0]


def _grade_to_level(grade: object) -> PollenLevel | None:
    """KMA's 4-level grade (0 low .. 3 very high) folded onto this app's
    3-level PollenLevel — grades 2 and 3 both read as HIGH."""
    try:
        g = int(grade)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if g <= 0:
        return PollenLevel.LOW
    if g == 1:
        return PollenLevel.MODERATE
    return PollenLevel.HIGH


def _max_grade(*grades: object) -> object:
    """Highest of the given raw grades, ignoring any that don't parse (e.g.
    a species out of season, which KMA omits or leaves blank)."""
    parsed = []
    for g in grades:
        try:
            parsed.append(int(g))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
    return max(parsed) if parsed else None


def parse_kma_pollen(payload: dict) -> PollenData:
    """Parse a KMA HealthWeatherIdxService response. Never raises: any shape
    this doesn't recognize (empty items, a missing envelope key, a single
    item returned as an object instead of a list) degrades to an all-None
    PollenData rather than an exception, matching weather/air-quality."""
    try:
        items = payload["response"]["body"]["items"]["item"]
    except (KeyError, TypeError):
        return PollenData()

    if isinstance(items, dict):
        items = [items]
    if not items:
        return PollenData()

    row = items[0]
    if not isinstance(row, dict):
        return PollenData()

    tree_grade = _max_grade(row.get("oak"), row.get("pine"))
    return PollenData(
        tree=_grade_to_level(tree_grade),
        grass=None,  # not reported by this provider — see research doc
        weed=_grade_to_level(row.get("weed")),
        is_sample=False,
    )


async def _fetch_kma(lat: float, lon: float, api_key: str, client: httpx.AsyncClient) -> PollenData:
    """Fetch the real KMA pollen risk index. Never raises: on any provider
    failure (network, timeout, non-2xx, bad JSON) this degrades to an
    all-None PollenData — `is_sample` stays False, since a real "no data"
    response (e.g. off pollen season, or a provider outage) is not the
    fabricated sample and must never be mistaken for it."""
    try:
        r = await client.get(
            _KMA_URL,
            params={
                "serviceKey": api_key,
                "areaNo": _nearest_area_no(lat, lon),
                "date": dt.date.today().strftime("%Y%m%d"),
                "dataType": "JSON",
                "numOfRows": 10,
                "pageNo": 1,
            },
            timeout=8.0,
        )
        r.raise_for_status()
        return parse_kma_pollen(r.json())
    except (httpx.HTTPError, ValueError):  # network/timeout/HTTP-status/bad JSON
        logger.warning("pollen provider unavailable, degrading to empty data", exc_info=True)
        return PollenData()


async def fetch_pollen(
    lat: float, lon: float, client: httpx.AsyncClient, api_key: str = ""
) -> PollenData:
    """Real KMA data when `api_key` is set, a clearly-flagged deterministic
    sample otherwise. The two are never blended: callers can trust
    `is_sample` to say which one they got."""
    if not api_key:
        return sample_pollen()
    return await _fetch_kma(lat, lon, api_key, client)
