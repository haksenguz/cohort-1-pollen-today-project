---
status: active
owner: Ismoiljon
review-by: 2026-09-01
verified: 2026-08-09 against the live service with a real key
---

# 0001 — KMA HealthWthrIdxServiceV3: what it actually serves

Every claim below was tested against the live endpoint, not read from the
manual. Where the manual disagrees with the service, the service wins and the
disagreement is noted.

## Endpoints

`http://apis.data.go.kr/1360000/HealthWthrIdxServiceV3/<operation>`

| Operation | Pollen | Season (per the service) |
| --- | --- | --- |
| `getOakPollenRiskIdxV3` | 참나무 oak | Mar–Jun |
| `getPinePollenRiskIdxV3` | 소나무 pine | Mar–Jun |
| `getWeedsPollenRiskndxV3` | 잡초류 weeds | **Aug–Oct — live now** |

**Two manual errors, both verified:**

1. The manual lists the weeds operation as `getWddesPollenRiskIdxV3`. That name
   returns `해당 오픈API 서비스가 없거나 폐기됨`. The working name is
   `getWeedsPollenRiskndxV3` — note the missing `I` in `ndx`. It is a typo in
   the official docs that is also the real endpoint name.
2. The manual says oak/pine run 4월~6월. The service says
   `자료제공기간 3월 ~ 6월` — March.

## Parameters

`serviceKey`, `pageNo`, `numOfRows`, `dataType` (`JSON`|`XML`), `areaNo`,
`time` (`YYYYMMDDHH`). Limits: 30 TPS, ~4000 byte response, ~500 ms.

## Response

```json
{"response":{
  "header":{"resultCode":"00","resultMsg":"NORMAL_SERVICE"},
  "body":{"dataType":"JSON","items":{"item":[{
    "code":"D08","areaNo":"1100000000","date":"2026080906",
    "today":"0","tomorrow":"0","dayaftertomorrow":"0",
    "twodaysaftertomorrow":""}]},
  "pageNo":1,"numOfRows":10,"totalCount":1}}}
```

Three properties that shape our code:

- **Errors are HTTP 200.** `resultCode` `"99"` with no `body` at all. The status
  line tells you nothing; parse the header.
- **Index values are strings** `"0".."3"` — 낮음/보통/높음/매우높음. Confirmed
  identical across all three pollen types.
- **Unpublished slots are `""`**, not null and not absent. Coercing `""` to `0`
  would publish a fake all-clear. This is the single most dangerous bug
  available in this integration.

`date` is the **bulletin stamp**, not the day being described. The four fields
are +0…+3 days from that stamp's calendar date.

## Bulletin hour changes which fields are filled

| `time` | `today` populated? |
| --- | --- |
| 00, 03 | no |
| 06, 09, 12, 15 | yes |
| 18, 21 | no |

All return `resultCode 00`. The 07:00 KST job should therefore request the `06`
bulletin and read `tomorrow`.

## Region granularity

`areaNo` accepts every level of the DFS zone tree — verified at 시/도
(`1100000000`), 구 (`1111000000`) and 동 (`1111051500`), all `resultCode 00`.

We use the 16 top-level 시/도 codes (ADR 0005). Whether finer codes return
*different* values is **unverified** — the index was `0` nationwide on the test
date, so there was no variance to observe. Re-check once the season ramps.

## The limitation that reshapes the project

```
resultCode 99 — 최근 1일 간의 자료만 제공합니다
```

**One day.** Requests for 2025 and for three days ago both return it. There is
no historical series, and no observation series either — every value this API
returns is a KMA *forecast*.

Consequences are tracked in [headache/0001](../headache/0001-kma-serves-one-day-of-history.md).

## Reproduce

```bash
curl -s "http://apis.data.go.kr/1360000/HealthWthrIdxServiceV3/getWeedsPollenRiskndxV3?serviceKey=$KMA_API_KEY&pageNo=1&numOfRows=10&dataType=JSON&areaNo=1100000000&time=$(date +%Y%m%d)06"
```
