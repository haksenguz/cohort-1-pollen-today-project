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
region (시/도 level, via an `areaNo` region code) — this is the one candidate
built for this country specifically rather than covering it incidentally.

**Species:** oak (참나무) and pine (소나무), each served April–June, plus a
combined weed (잡초류) category served August–October. This matches Korea's
actual pollen seasons — spring tree pollen, autumn weed/ragweed pollen — but
it does not report a grass category. That's a real gap against this app's
tree/grass/weed model: `grass` stays `null` on this provider, same as any
other "not measured" field already handled by `risk.score()`.

**Scale:** 4-level grade, 0=낮음(Low), 1=보통(Normal), 2=높음(High),
3=매우높음(Very High) — coarser than this app's 3-level `PollenLevel`, so 2
and 3 both fold into `HIGH`.

**Auth:** `serviceKey` query param, issued after applying for API access on
data.go.kr (free, near-instant approval for public APIs like this one — no
manual review queue). REST, JSON or XML.

**Rate limits:** 10,000 calls/day on a development-tier key; production-tier
keys can request a higher quota by registering the use case. No per-request
cost tiers — it's flat free.
[data.go.kr/data/15085289/openapi.do](https://www.data.go.kr/data/15085289/openapi.do).

**Cost:** free, no paid tier exists for this API.

**Known gap in this research:** the exact operation name and response field
names (e.g. whether the JSON node is `oak`/`pine`/`weed` or Korean-language
keys) sit behind data.go.kr's post-approval manual
(`꽃가루농도지수 조회서비스(3.0)_설명서 및 행정구역코드 정보_....zip`), which isn't
readable without an approved key. The client below is written defensively
(missing/renamed fields degrade to `None`, never a crash) specifically
because of this gap — confirm field names against the real manual once a key
is issued, before trusting non-null output in production.

## Recommendation

**KMA 꽃가루농도위험지수**, because it's the only candidate that is actually
built for Korea (government source, per-region), is unambiguously free with
a workable quota (10k/day), and tracks the species that drive Korean pollen
seasons (oak, pine, weed/ragweed) rather than a US-centric model. The
tradeoff — no grass reading, and a still-unconfirmed exact JSON shape until
a key is issued — is acceptable because the service already treats missing
per-allergen data as zero-contribution, not a failure.
