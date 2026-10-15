"""Live-check the KMA pollen risk index against the real provider.

Why this exists
---------------
`pollen_service.py` is written against KMA's real request and response shapes,
but those shapes are only knowable by calling the provider. A silent mismatch
does not fail loudly: the parser degrades to empty data, which the app renders
as "Pollen: Unavailable" — indistinguishable from "no pollen in Korea today".

So this script prints what the provider actually answered and asserts the parse
produced real levels. Run it after adding or rotating `POLLEN_API_KEY`, and
after any change to the KMA contract:

    uv run python -m scripts.verify_live_pollen

Exit codes: 0 = real levels returned. 1 = no key, no data for the region, or a
payload shape the parser no longer understands. In every failure case the
provider's own answer is printed first, because that message is the diagnosis.

Seasons matter when reading the result: tree pollen (oak/pine) is served 3–6월
and weeds 8–10월, so a run in, say, January correctly returns nothing at all.
"""

import asyncio
import datetime as dt
import json
import os
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # the provider speaks Korean

from dotenv import load_dotenv  # noqa: E402

from app.services.pollen_service import (  # noqa: E402
    _KMA_BASE,
    _KMA_OAK,
    _KMA_PINE,
    _KMA_WEEDS,
    _announce_candidates,
    _nearest_area_no,
    fetch_pollen,
    parse_kma_today,
)

# Seoul. The region is picked from these coordinates by the service itself.
LAT, LON = 37.5665, 126.9780

OPS = {
    "oak (tree)": _KMA_OAK,
    "pine (tree)": _KMA_PINE,
    "weeds": _KMA_WEEDS,
}


def _redact(payload: object, secret: str) -> object:
    """The provider echoes nothing back, but a 400 body can quote the request,
    so scrub before printing."""
    if not secret:
        return payload
    return json.loads(json.dumps(payload).replace(secret, "<redacted>"))


async def main() -> int:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    key = os.getenv("POLLEN_API_KEY", "").strip()
    if not key:
        print("FAIL  POLLEN_API_KEY is not set")
        print("      Without it the Today screen shows 'Pollen: Unavailable'.")
        return 1

    area = _nearest_area_no(LAT, LON)
    print(f"KEY   set ({len(key)} chars)")
    print(f"AREA  lat={LAT} lon={LON} -> areaNo={area}")
    print("      KMA publishes no station for Gwangju/Gangwon/Jeonbuk/Jeonnam;")
    print("      for those provinces a correct run also has nothing to show.")
    if area is None:
        print("OK    this region has no provider station, so 'no data' is correct")
        return 0

    stamp = _announce_candidates(dt.datetime.now())[0]
    print(f"TIME  {stamp}  (KMA publishes on 06/12/18; an unpublished hour blanks 'today')")

    async with httpx.AsyncClient() as http:
        print()
        for label, url in OPS.items():
            try:
                r = await http.get(
                    url,
                    params={
                        "serviceKey": key,
                        "areaNo": area,
                        "time": stamp,
                        "dataType": "JSON",
                        "numOfRows": 10,
                        "pageNo": 1,
                    },
                    timeout=10.0,
                )
            except httpx.HTTPError as exc:
                print(f"{label:<11} request failed: {type(exc).__name__}")
                continue

            try:
                payload = r.json()
            except ValueError:
                print(f"{label:<11} HTTP {r.status_code} non-JSON body")
                continue

            shown = json.dumps(_redact(payload, key), ensure_ascii=False)
            level = parse_kma_today(payload)
            msg = payload.get("response", {}).get("header", {}).get("resultMsg", "")
            print(f"{label:<11} HTTP {r.status_code}  level={level}  {shown[:220]}")
            if level is None and msg:
                print(f"{'':<11} provider says: {msg}")

        print()
        data = await fetch_pollen(LAT, LON, http, key)

    print(f"PARSED tree={data.tree} grass={data.grass} weed={data.weed}")
    print(f"       is_sample={data.is_sample}")
    print(f"       url base: {_KMA_BASE}")

    if data.is_sample:
        print("FAIL  got the deterministic sample, not provider data")
        return 1
    if data.tree is None and data.weed is None:
        month = dt.date.today().month
        if month in (3, 4, 5, 6):
            print("FAIL  nothing parsed during tree season (3-6월)")
        elif month in (8, 9, 10):
            print("FAIL  nothing parsed during weed season (8-10월)")
        else:
            print("OK    off pollen season, every level is correctly absent")
        return 1 if month in (3, 4, 5, 6, 8, 9, 10) else 0

    print("OK    real pollen levels returned")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
