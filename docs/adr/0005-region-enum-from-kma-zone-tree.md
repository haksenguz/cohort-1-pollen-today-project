# ADR 0005 — Region is the 16 KMA top-level 시/도

Date: 2026-08-04
Status: Accepted
Decider: Ismoiljon (Tech Lead)
Contract change — needs Jamshid's and Giyos's sign-off before merge

## Context

`Region` shipped in Week 0 as eight placeholder metro names, explicitly marked
blocked on the canonical list (OPEN_QUESTIONS §2.4). The mentor has now supplied
the KMA DFS zone tree (`dfs-zone-tree_excel_20260701.xlsx`, 3,839 rows) and the
V3 API code manual.

The KMA endpoints take an `areaNo`. Without the real codes nothing can call the
API, so this blocks Slice A entirely.

## Decision

`Region` is the 16 top-level 시/도 rows of the zone tree — those whose
`행정구역코드` ends in `00000000`. The `Region → areaNo` mapping lives in
`REGION_AREA_NO` in `@pollen/contracts`, not in the SDL, because GraphQL enums
carry no payload.

Korean display names are in `REGION_LABEL_KO`, sourced from the same file, so
alert text never hand-writes a region name.

## Why 시/도 and not finer

The zone tree goes down to 동 level. Slide 15 says "KMA region granularity only,
no location permission prompts", and the delivery model is one public Telegram
channel per region. 3,839 channels is not a product. Sixteen is already more
than the three the milestones require.

## The Gwangju trap

`1200000000` is **전남광주통합특별시** — Gwangju and Jeollanam-do merged. The
zone tree has no separate 전라남도 row, and the old Gwangju code is not in the
file. The enum member is therefore `GWANGJU_JEONNAM`, not `GWANGJU`. Anyone
carrying the old code forward from the placeholder list will get empty responses
rather than an error, which is the worst kind of failure.

## Alternatives considered

- **Keep eight metros.** Rejected: arbitrary, and excludes 경기도, the most
  populous region in the country.
- **Store `areaNo` as the enum value** (`AREA_1100000000`). Rejected: unreadable
  in the schema, in the URL, and in a Telegram channel name.
- **Put the mapping in the SDL as a field.** Rejected: it is not data any client
  needs. Clients ask for `SEOUL`; only the ingest job cares what KMA calls it.

## Consequences

- Region is no longer a placeholder. Changing it from here is a real contract
  change under the Week-1 freeze.
- Slice A can call the API as soon as the key is issued.
- Telegram channels are configured per region via `TELEGRAM_CHANNELS`, so
  supporting all 16 is a config change, not a code change.
- `KMA_INDEX_TO_RISK_LEVEL` is added alongside: KMA publishes the index as an
  integer 0–3, confirmed identical for oak, pine and weeds in the V3 manual.
