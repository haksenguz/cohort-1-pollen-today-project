"""Pollen levels via KMA's 꽃가루농도위험지수 (pollen risk index).

Provider facts, all confirmed live on 2026-10-15 against a real key (see
`backend/scripts/verify_live_pollen.py` and docs/research/pollen-providers.md):

- The service is `HealthWthrIdxServiceV3` — "HealthWthr", not "HealthWeather".
  The plausible-looking `HealthWeatherIdxServiceV3/getPlrsIdxTodyList` does not
  exist; data.go.kr answers HTTP 400 with `NO_OPENAPI_SERVICE_ERROR` (reason
  code 12, "check the call URL for a typo") rather than an auth error.
- There is no single "today" endpoint. Tree and weeds are three separate
  operations: `getOakPollenRiskIdxV3`, `getPinePollenRiskIdxV3`,
  `getWeedsPollenRiskndxV3` (note the lowercase "n" in that last one).
- `areaNo` is a 10-digit KMA station code, not a 2-digit 시도 code. Province
  level codes are the 2-digit code plus 8 zeros (Seoul = `1100000000`).
- Required params are `numOfRows`, `pageNo`, `dataType`, `areaNo`, `time`.
  `time` is the 발표시간 stamp (YYYYMMDDHH) and must be an hour KMA actually
  published; an unpublished hour comes back with an empty `today`.
- Each response row carries `today`/`tomorrow`/`dayaftertomorrow` as a 4-level
  grade (0 low, 1 moderate, 2 high, 3 very high), and an empty string means KMA
  published no value.
- Seasonality is enforced by the provider: tree pollen is served 3–6월, weeds
  8–10월. Outside its window an operation returns `resultCode: "99"` with no
  body at all. That is "no data", never a low reading.

Real data and the deterministic sample are never blended: callers trust
`is_sample` to say which one they got, and every provider failure degrades to
all-None rather than to fabricated numbers.
"""

import asyncio
import datetime as dt
import logging
from dataclasses import dataclass

import httpx

from app.core.enums import PollenLevel

logger = logging.getLogger(__name__)

# prototype grains/m3 cutoffs, used only by the deterministic sample below —
# the real KMA provider ships its own 4-level grade (see _grade_to_level).
_TREE = (15, 90)
_GRASS = (5, 20)
_WEED = (10, 50)

_KMA_BASE = "https://apis.data.go.kr/1360000/HealthWthrIdxServiceV3"
_KMA_OAK = f"{_KMA_BASE}/getOakPollenRiskIdxV3"
_KMA_PINE = f"{_KMA_BASE}/getPinePollenRiskIdxV3"
_KMA_WEEDS = f"{_KMA_BASE}/getWeedsPollenRiskndxV3"

# The hours KMA publishes on. A `time` outside this set returns a row whose
# `today` is blank, which would otherwise be indistinguishable from "no pollen".
_ANNOUNCE_HOURS = (6, 12, 18)

# The standard KOSTAT 시도 codes with each region's administrative centroid, so
# a lat/lon resolves to the province the user is actually in.
_STANDARD_SIDOS: tuple[tuple[str, float, float], ...] = (
    ("11", 37.5665, 126.9780),  # Seoul
    ("26", 35.1796, 129.0756),  # Busan
    ("27", 35.8714, 128.6014),  # Daegu
    ("28", 37.4563, 126.7052),  # Incheon
    ("29", 35.1595, 126.8526),  # Gwangju
    ("30", 36.3504, 127.3845),  # Daejeon
    ("31", 35.5384, 129.3114),  # Ulsan
    ("36", 36.4801, 127.2890),  # Sejong
    ("41", 37.4138, 127.5183),  # Gyeonggi (Suwon)
    ("42", 37.8228, 128.1555),  # Gangwon
    ("43", 36.6357, 127.4913),  # Chungbuk
    ("44", 36.5184, 126.8000),  # Chungnam
    ("45", 35.7175, 127.1530),  # Jeonbuk
    ("46", 34.8679, 126.9910),  # Jeonnam
    ("47", 36.4919, 128.8889),  # Gyeongbuk
    ("48", 35.4606, 128.2132),  # Gyeongnam
    ("50", 33.4996, 126.5312),  # Jeju
)

# Province-level station codes the provider actually serves (시도 code + 8
# zeros), each with the centroid above.
#
# Gwangju (29), Gangwon (42), Jeonbuk (45) and Jeonnam (46) are deliberately
# absent. Those 표준 시도 codes have zero stations in KMA's own station list —
# verified by pulling every station with an empty areaNo: the 3851 weed rows
# cover prefixes 11, 12, 26, 27, 28, 30, 31, 36, 41, 43, 44, 47, 48, 50, 51
# and 52, and nothing under 29/42/45/46. The provider also uses station codes
# we cannot name from the payload (12/51/52 carry no province label, and their
# 시/군 digits are not KOSTAT), so guessing which region they belong to would
# put one region's pollen on another region's screen.
_SERVED_CODES = frozenset(
    {"11", "26", "27", "28", "30", "31", "36", "41", "43", "44", "47", "48", "50"}
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


def _nearest_area_no(lat: float, lon: float) -> str | None:
    """The provider's station code for the province this coordinate is in.

    Returns None — meaning "KMA publishes nothing for this user's region" — when
    the nearest province is one the provider does not serve. Falling back to the
    nearest *served* province instead would put a neighbour's pollen on screen
    with no label saying so.
    """
    sido = min(
        _STANDARD_SIDOS,
        key=lambda region: (region[1] - lat) ** 2 + (region[2] - lon) ** 2,
    )[0]
    if sido not in _SERVED_CODES:
        return None
    return f"{sido}00000000"


def _grade_to_level(grade: object) -> PollenLevel | None:
    """KMA's 4-level grade (0 low .. 3 very high) folded onto this app's
    3-level PollenLevel — grades 2 and 3 both read as HIGH. An empty string
    means "not published", which is None, never LOW."""
    try:
        g = int(grade)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if g <= 0:
        return PollenLevel.LOW
    if g == 1:
        return PollenLevel.MODERATE
    return PollenLevel.HIGH


def _max_level(*levels: PollenLevel | None) -> PollenLevel | None:
    """Highest of the given levels, ignoring the ones with no data."""
    present = [level for level in levels if level is not None]
    if not present:
        return None
    return max(present, key=list(PollenLevel).index)


def _announce_candidates(now: dt.datetime) -> list[str]:
    """Most recent published `time` stamp first, then the one before it.

    The fallback matters at the edges of a publication window: asking for an
    hour KMA has not published yet returns a row with a blank `today`, and
    without the retry the app would show no pollen for the first hours of the
    morning.
    """
    hours = [h for h in _ANNOUNCE_HOURS if h < now.hour]
    if not hours and now.hour <= _ANNOUNCE_HOURS[0]:
        hours = [_ANNOUNCE_HOURS[0]]
    day = now.strftime("%Y%m%d")
    # reversed() before the slice, so the two candidates are genuinely the two
    # most recent publication hours. Slicing first silently drops 18시.
    return [f"{day}{h:02d}" for h in list(reversed(hours))[:2]]


def parse_kma_today(payload: object) -> PollenLevel | None:
    """Today's level from one KMA pollen operation. Never raises: an out-of-
    season response, a missing envelope, a single item returned as an object,
    or a blank `today` all read as "no data"."""
    if not isinstance(payload, dict):
        return None
    response = payload.get("response")
    if not isinstance(response, dict):
        return None

    header = response.get("header")
    if isinstance(header, dict):
        code = str(header.get("resultCode", "00"))
        if code != "00":
            # 99 = 해당지수자료 제공기간이 아닙니다 (outside the data window).
            return None

    body = response.get("body")
    items = body.get("items", {}).get("item") if isinstance(body, dict) else None
    if isinstance(items, dict):
        items = [items]
    if not items or not isinstance(items, list):
        return None

    row = items[0]
    if not isinstance(row, dict):
        return None
    return _grade_to_level(row.get("today"))


async def _fetch_grade(
    client: httpx.AsyncClient, url: str, area: str, stamp: str, api_key: str
) -> PollenLevel | None:
    try:
        r = await client.get(
            url,
            params={
                "serviceKey": api_key,
                "areaNo": area,
                "time": stamp,
                "dataType": "JSON",
                "numOfRows": 10,
                "pageNo": 1,
            },
            timeout=8.0,
        )
        if r.status_code != 200:
            # Logged without exc_info on purpose: httpx exception text carries
            # the full request URL, which includes serviceKey in the query
            # string. A degraded read must never cost us the key.
            logger.warning(
                "pollen provider %s returned HTTP %s (area=%s time=%s)",
                url.rsplit("/", 1)[-1],
                r.status_code,
                area,
                stamp,
            )
            return None
        return parse_kma_today(r.json())
    except (httpx.HTTPError, ValueError):
        logger.warning(
            "pollen provider %s unreachable (area=%s time=%s)",
            url.rsplit("/", 1)[-1],
            area,
            stamp,
            exc_info=False,
        )
        return None


async def fetch_pollen(
    lat: float, lon: float, client: httpx.AsyncClient, api_key: str = ""
) -> PollenData:
    """Real KMA data when `api_key` is set, a clearly-flagged deterministic
    sample otherwise. The two are never blended: callers can trust
    `is_sample` to say which one they got."""
    if not api_key:
        return sample_pollen()

    area = _nearest_area_no(lat, lon)
    if area is None:
        logger.info("no KMA pollen station covers this location")
        return PollenData()

    for stamp in _announce_candidates(dt.datetime.now()):
        oak, pine, weeds = await asyncio.gather(
            _fetch_grade(client, _KMA_OAK, area, stamp, api_key),
            _fetch_grade(client, _KMA_PINE, area, stamp, api_key),
            _fetch_grade(client, _KMA_WEEDS, area, stamp, api_key),
        )
        if any(level is not None for level in (oak, pine, weeds)):
            return PollenData(
                tree=_max_level(oak, pine),
                grass=None,  # this provider reports no grass index
                weed=weeds,
                is_sample=False,
            )

    return PollenData()
