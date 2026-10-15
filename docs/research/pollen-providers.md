---
status: current
owner: Ismoiljon
review-by: 2026-12-08
---

# Which pollen API actually covers Korea

Claim: for a Korea-only app, the Korea Meteorological Administration's own
pollen risk index is the only candidate with real Korea coverage, a real free
tier, and species that match what Korean allergy sufferers actually react to.
Everything keyless (Open-Meteo, used for weather/AQI) skips pollen entirely
outside North America/Europe, which is why `pollen_service.py` has been
faking it.

## Candidates checked

### Google Pollen API — no Korea coverage

Google's pollen overlays cover North America and Western Europe, plus
Japanese cedar/cypress in Japan since Sep 2024. Korea isn't listed anywhere
in the coverage docs or release notes.
[developers.google.com/maps/documentation/pollen](https://developers.google.com/maps/documentation/pollen),
[release notes](https://developers.google.com/maps/documentation/pollen/release-notes).
Ruled out: no coverage, full stop.

### Ambee Pollen API — coverage doesn't list Korea, no real free tier

Ambee advertises "150+ countries" but its own marketing narrows that to
Europe, North America, and ANZ for pollen specifically
([getambee.com/api/pollen](https://www.getambee.com/api/pollen)). There's no
Korea confirmation anywhere in their docs. The "free tier" is a 15-day trial,
not a standing free plan
([community.tempest.earth](https://community.tempest.earth/t/is-there-a-free-unlimited-pollen-api/23170)),
so it can't be the always-on fallback-free path this app needs.
Ruled out: unconfirmed Korea coverage, no permanent free tier.

### Tomorrow.io — has Korea data, but the free tier for pollen isn't confirmed and species are generic

Tomorrow.io does serve Seoul and other Korean points
([weather.tomorrow.io/KR/11/Seoul](https://weather.tomorrow.io/KR/11/Seoul/065498/health/)),
and the Pollen data layer reports `treeIndex`, `grassIndex`,
`grassGrassIndex`, `weedIndex`, `weedRagweedIndex` on a 0–5 scale
([docs.tomorrow.io/reference/data-layers-pollen](https://docs.tomorrow.io/reference/data-layers-pollen)).
Two problems: the public pricing page lists "Core Weather Data Layers" on
the free plan but doesn't say pollen is one of them, and support says premium
layers need a sales conversation
([tomorrow.io/weather-api/pricing](https://www.tomorrow.io/weather-api/pricing/)).
The species reported (ragweed, generic grass/tree) are US-modeled, not the
oak/pine/mugwort seasonality Korean forecasts actually track. Kept as a
credible backup if KMA integration stalls, not the pick.

### Google/Breezometer — folded into Google Pollen API

Breezometer was absorbed into Google's Maps Platform; there's no separate
Breezometer pollen product anymore. Same Korea gap as Google Pollen above.

### AirKorea (에어코리아) — air quality only, not pollen

AirKorea (airkorea.or.kr) publishes PM2.5/PM10/O3/NO2 station data, which
this app already gets from Open-Meteo. It does not publish a pollen index;
that's a separate KMA product (below). Not a pollen candidate.

### KMA 꽃가루농도위험지수 (Pollen Concentration Risk Index) — recommended

Korea's own national weather service publishes a pollen risk index as part
of its "보건기상지수" (health-weather-index) OpenAPI, listed on the public
data portal as **기상청_꽃가루농도위험지수 조회서비스(3.0)**:
[data.go.kr/data/15085289/openapi.do](https://www.data.go.kr/data/15085289/openapi.do),
mirrored on the KMA data portal:
[data.kma.go.kr/data/lwi/hwiRltmList.do?pgmNo=642&tabNo=2](https://data.kma.go.kr/data/lwi/hwiRltmList.do?pgmNo=642&tabNo=2).

**Coverage for Korea:** built for Korea, nationwide, by administrative
region. `areaNo` is a **10-digit KMA station code**, not a 2-digit 시도 code —
Seoul is `1100000000`, i.e. the standard KOSTAT 시도 code plus 8 zeros. The
station list is much finer than that: passing an empty `areaNo` returns all
3851 weed stations, most of them 시/군/읍/면/동 level.

**Provinces KMA does not serve.** The station list has **nothing** under the
standard codes for Gwangju (29), Gangwon (42), Jeonbuk (45) and Jeonnam (46).
Verified 2026-10-15 by pulling every station with an empty `areaNo`: the weed
rows cover prefixes 11, 12, 26, 27, 28, 30, 31, 36, 41, 43, 44, 47, 48, 50, 51
and 52, with zero rows under 29/42/45/46. The provider also uses station codes
that carry no province label (12/51/52) and whose 시/군 digits are not KOSTAT,
so which region they represent cannot be determined from the payload.

`pollen_service.py` therefore resolves a coordinate to its standard 시도 code and
returns "no data" for those four provinces, instead of falling back to the
nearest *served* province. The fallback would show one region's pollen under
another region's name, which for an allergy app is worse than an empty row.
Closing this gap needs a station code list with names and coordinates (KMA
publishes one via a separate FILE service), not a different key.

**Species:** oak (참나무) and pine (소나무), served 3–6월 — the provider's own
out-of-season message is `[자료제공기간 3월 ~ 6월]` — plus a combined weed
(잡초류) category. This matches Korea's actual pollen seasons, but it does not
report a grass category. That's a real gap against this app's tree/grass/weed
model: `grass` stays `null` on this provider, same as any other "not measured"
field already handled by `risk.score()`.

**Scale:** 4-level grade, 0=낮음(Low), 1=보통(Normal), 2=높음(High),
3=매우높음(Very High) — coarser than this app's 3-level `PollenLevel`, so 2
and 3 both fold into `HIGH`. An **empty string** in the row means KMA published
no value for that hour, which is `null`, never `LOW`.

**Auth:** `serviceKey` query param, issued after applying for API access on
data.go.kr (free, near-instant approval for public APIs like this one — no
manual review queue). REST, JSON or XML.

**Rate limits:** 10,000 calls/day on a development-tier key; production-tier
keys can request a higher quota by registering the use case. No per-request
cost tiers — it's flat free.
[data.go.kr/data/15085289/openapi.do](https://www.data.go.kr/data/15085289/openapi.do).

**Cost:** free, no paid tier exists for this API.

## The actual contract, confirmed live 2026-10-15

The earlier gap — operation and field names hidden behind a post-approval PDF —
is closed. The provider's OpenAPI page embeds its Swagger definition in the
page source, and a real key now confirms every detail
(`backend/scripts/verify_live_pollen.py` prints the provider's own answer and
exits non-zero if the parse ever stops matching):

- **Service name is `HealthWthrIdxServiceV3`** — "HealthWthr", not
  "HealthWeather". The plausible-looking
  `HealthWeatherIdxServiceV3/getPlrsIdxTodyList` does not exist and fails with
  HTTP 400 `NO_OPENAPI_SERVICE_ERROR`, reason code 12, whose own text is
  "check the call URL for a typo". An unauthenticated-looking 400 for a
  wrong-path call is the trap: it reads like a key problem.
- **Three separate operations, no single "today" endpoint:**
  `getOakPollenRiskIdxV3`, `getPinePollenRiskIdxV3`, `getWeedsPollenRiskndxV3`
  (lowercase `n` in that last one). `tree` is the worse of oak and pine.
- **Required params:** `serviceKey`, `numOfRows`, `pageNo`, `dataType`,
  `areaNo`, `time`. There is no `date` param.
- **`time` is the 발표시간 stamp** (YYYYMMDDHH), and it must be an hour KMA
  actually published. On 2026-10-15, 06 and 12 returned a populated `today`,
  while 18 returned a row with `today` blank. The service tries the newest
  published hour and falls back one hour rather than reporting no pollen for
  the first hours of the morning.
- **Response row:** `code`, `areaNo`, `date`, `today`, `tomorrow`,
  `dayaftertomorrow`, `twodaysaftertomorrow`. Note the last one is `twodays…`
  in the payload although the Swagger definition spells it
  `todaysaftertomorrow`; the service does not read that field, so the doc typo
  does not matter.
- **Out-of-season is a header, not an error status:** HTTP 200 with
  `resultCode: "99"` and no `body` key at all.

Observed for Seoul on 2026-10-15: `weeds → today: "0"` (LOW), oak and pine both
`resultCode 99`. That is the correct October answer — weed season, out of tree
season — and it is the shape the app now renders.

A verification live on 2026-10-15 at 19:00 KST:

```
AREA  lat=37.5665 lon=126.978 -> areaNo=1100000000
oak   HTTP 200  level=None   resultCode 99 해당지수자료 제공기간이 아닙니다! [자료제공기간 3월 ~ 6월]
pine  HTTP 200  level=None   resultCode 99 해당지수자료 제공기간이 아닙니다! [자료제공기간 3월 ~ 6월]
weeds HTTP 200  level=LOW    today="0" code="D08" areaNo="1100000000"
PARSED tree=None grass=None weed=LOW  is_sample=False
OK    real pollen levels returned
```

## Recommendation

**KMA 꽃가루농도위험지수**, because it's the only candidate that is actually
built for Korea (government source, per-region), is unambiguously free with
a workable quota (10k/day), and tracks the species that drive Korean pollen
seasons (oak, pine, weed/ragweed) rather than a US-centric model. The
tradeoff — no grass reading — is acceptable because the service already treats
missing per-allergen data as zero-contribution, not a failure.

The shape is no longer unconfirmed: it was verified against the live provider
on 2026-10-15 and the parser is pinned to it by `tests/test_pollen_service.py`.
`backend/scripts/verify_live_pollen.py` re-checks it in one command and is the
regression check to run if KMA changes an operation name.
