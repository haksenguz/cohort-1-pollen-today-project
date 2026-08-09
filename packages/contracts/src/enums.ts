import { z } from "zod";
import { Region, RiskLevel } from "./graphql.js";

/**
 * Enums are DECLARED in apps/api/src/schema/common.graphql and generated into
 * ./graphql.ts. Import `Region`, `PollenType`, `RiskLevel` and `JobStatus` from
 * this package — never redeclare them.
 *
 * What lives here is what the SDL cannot express: ordering, and the Zod schemas
 * for data arriving from outside the system.
 */

/**
 * Risk levels in published order, low to very high.
 * Ordering is semantic — `riskAtLeast` depends on it, so do not sort this.
 */
export const RISK_LEVELS_ORDERED = [
  RiskLevel.LOW,
  RiskLevel.MODERATE,
  RiskLevel.HIGH,
  RiskLevel.VERY_HIGH,
] as const;

/** True when `level` is at or above `threshold`. Drives the alert cutoff. */
export function riskAtLeast(level: RiskLevel, threshold: RiskLevel): boolean {
  return (
    RISK_LEVELS_ORDERED.indexOf(level) >= RISK_LEVELS_ORDERED.indexOf(threshold)
  );
}

/**
 * Region → KMA `areaNo`, the code the data.go.kr endpoints take.
 *
 * Source: the KMA DFS zone tree (dfs-zone-tree, 2026-07-01), filtered to the
 * 16 top-level 시/도 rows. The SDL cannot carry this mapping, which is why it
 * lives here rather than in the schema.
 *
 * `1200000000` is 전남광주통합특별시 — Gwangju and Jeollanam-do merged, and the
 * zone tree has no separate 전라남도 row. Using the old Gwangju code returns
 * nothing.
 */
export const REGION_AREA_NO: Record<Region, string> = {
  [Region.SEOUL]: "1100000000",
  [Region.GWANGJU_JEONNAM]: "1200000000",
  [Region.BUSAN]: "2600000000",
  [Region.DAEGU]: "2700000000",
  [Region.INCHEON]: "2800000000",
  [Region.DAEJEON]: "3000000000",
  [Region.ULSAN]: "3100000000",
  [Region.SEJONG]: "3600000000",
  [Region.GYEONGGI]: "4100000000",
  [Region.CHUNGBUK]: "4300000000",
  [Region.CHUNGNAM]: "4400000000",
  [Region.GYEONGBUK]: "4700000000",
  [Region.GYEONGNAM]: "4800000000",
  [Region.JEJU]: "5000000000",
  [Region.GANGWON]: "5100000000",
  [Region.JEONBUK]: "5200000000",
};

/** Every region, in a stable order. Use instead of `Object.values` at call sites. */
export const ALL_REGIONS = Object.keys(REGION_AREA_NO) as Region[];

/** Korean display names, as published in the zone tree. */
export const REGION_LABEL_KO: Record<Region, string> = {
  [Region.SEOUL]: "서울특별시",
  [Region.GWANGJU_JEONNAM]: "전남광주통합특별시",
  [Region.BUSAN]: "부산광역시",
  [Region.DAEGU]: "대구광역시",
  [Region.INCHEON]: "인천광역시",
  [Region.DAEJEON]: "대전광역시",
  [Region.ULSAN]: "울산광역시",
  [Region.SEJONG]: "세종특별자치시",
  [Region.GYEONGGI]: "경기도",
  [Region.CHUNGBUK]: "충청북도",
  [Region.CHUNGNAM]: "충청남도",
  [Region.GYEONGBUK]: "경상북도",
  [Region.GYEONGNAM]: "경상남도",
  [Region.JEJU]: "제주특별자치도",
  [Region.GANGWON]: "강원특별자치도",
  [Region.JEONBUK]: "전북특별자치도",
};

/**
 * KMA publishes the risk index as an integer 0–3. Source: the V3 API code
 * manual, "단계 및 범위" table — identical for oak, pine and weeds.
 */
export const KMA_INDEX_TO_RISK_LEVEL: Record<number, RiskLevel> = {
  0: RiskLevel.LOW,
  1: RiskLevel.MODERATE,
  2: RiskLevel.HIGH,
  3: RiskLevel.VERY_HIGH,
};

/** ISO date, `YYYY-MM-DD`. All dates in this system are KST calendar dates. */
export const IsoDate = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}$/, "expected YYYY-MM-DD");
export type IsoDate = z.infer<typeof IsoDate>;
