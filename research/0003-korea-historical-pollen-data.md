---
status: active
owner: Ismoiljon → hand to Jamshid (Slice A)
review-by: 2026-08-23
verified: partially — the datasets are documented; access is NOT yet confirmed
---

# 0003 — Historical Korean pollen data: it exists, just not on our API

[headache/0001](../headache/0001-kma-serves-one-day-of-history.md) established
that `HealthWthrIdxServiceV3` serves one day. That is a property of *that
service*, not of Korean pollen data as a whole.

## What exists

**A national pollen observation network.** Airborne pollen has been collected at
**8 stations** since 2007, covering **13 allergenic taxa** — alder, Japanese
cedar, birch, hazelnut, oak, elm, pine, ginkgo, chestnut, grasses, **ragweed**,
mugwort and Japanese hop. Forecast models and operational services are built on
this national pollen database.

Published observation windows found so far: **2007–2017** in the peer-reviewed
literature, and **2014–2024** as the basis of the current pollen calendar.

**꽃가루 달력 (the pollen calendar), 국립기상과학원 (NIMS).** Built from
2014–2024 observations across 8 cities, giving per-taxon seasonal levels in the
same 4 bands we already use. Published at `nims.go.kr` under
기상기후이야기 > 꽃가루.

**기상자료개방포털 (`data.kma.go.kr`).** KMA's bulk data portal — 30 data types
plus 100+ years of climate statistics. This is the natural home for both the
pollen observations and the **weather observations** Slice A needs as model
features, which our current API does not provide at all.

## The station/region mismatch — important

The 8 observation cities are **서울, 강릉, 대전, 전주, 광주, 대구, 부산, 제주**.

Our `Region` enum is the 16 top-level 시/도 (ADR 0005). These do not line up:
강릉 and 전주 are cities inside 강원 and 전북, and there is no observation
station for most 시/도.

So historical analysis is possible for **8 points**, while the forecast index is
published for **all 16 regions**. Slice B's charts must say which they are
showing. Silently mixing the two would produce a chart that is wrong in a way
nobody would notice.

## What is NOT verified

- **Access method.** `data.kma.go.kr/data/climate/selectPollenList.do` currently
  returns `컨텐츠 내용이 준비가 되지 않았습니다` — content not prepared. Either
  the pollen section moved or it is not published there. Somebody has to browse
  the portal properly rather than guess URLs.
- **Whether it needs its own key.** 기상자료개방포털 registration is separate
  from data.go.kr. Assume yes; budget a day.
- **Licensing for redistribution**, which is a live question because we
  republish to public channels.
- **Granularity** — daily counts, or only seasonal summaries? A calendar is not
  a time series. If only the calendar is public, it supports Slice B's
  season-shift question but *not* Slice A's training set.

## What this changes

`headache/0001` moves from "no history exists" to "history exists; access
unconfirmed". That is a materially better position and it changes the ask to the
mentor from *rescope the project* to *help us reach this portal*.

It does not remove the urgency of daily ingest: even with historical
observations, the (forecast → outcome) pairs needed to measure *forecast
accuracy* only accumulate from the day ingest starts.

## Next actions

1. Browse 기상자료개방포털 and NIMS properly — find the actual pollen dataset
   page, note format, range and access. **Jamshid, ~1 hour.**
2. Ask the mentor whether he already has this data or a contact. Cheaper than
   any amount of searching.
3. Read *Forecast for Pollen Allergy: A Review from Field Observation to
   Modeling and Services in Korea* (PubMed 33228869) — it describes the
   observation network and operational model, i.e. exactly what Slice A is
   rebuilding, and names the data sources.

## Sources

- [KMA press — 2025 꽃가루 달력](https://www.kma.go.kr/kma/news/press.jsp?mode=view&num=1194479)
- [국립기상과학원 — 꽃가루 달력](http://www.nims.go.kr/?sub_num=1031)
- [기상자료개방포털](https://data.kma.go.kr/)
- [Forecast for Pollen Allergy in Korea (review)](https://pubmed.ncbi.nlm.nih.gov/33228869/)
- [Allergenic Pollen Calendar in Korea](https://e-aair.org/DOIx.php?id=10.4168%2Faair.2020.12.2.259)
