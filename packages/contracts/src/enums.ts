import { z } from "zod";

/**
 * The four risk levels published daily by the Korea Meteorological Administration.
 * Ordered — comparisons rely on the index, so do not reorder.
 */
export const RISK_LEVELS = ["LOW", "MODERATE", "HIGH", "VERY_HIGH"] as const;
export const RiskLevel = z.enum(RISK_LEVELS);
export type RiskLevel = z.infer<typeof RiskLevel>;

export function riskAtLeast(level: RiskLevel, threshold: RiskLevel): boolean {
  return RISK_LEVELS.indexOf(level) >= RISK_LEVELS.indexOf(threshold);
}

/**
 * Pollen types KMA publishes. Oak and pine run April–June and are off-season
 * during this build; weeds/ragweed run August–October and are live.
 */
export const POLLEN_TYPES = ["OAK", "PINE", "WEEDS"] as const;
export const PollenType = z.enum(POLLEN_TYPES);
export type PollenType = z.infer<typeof PollenType>;

/**
 * PLACEHOLDER — blocked on the canonical KMA region list.
 * See docs/OPEN_QUESTIONS.md §2.4. Every slice keys off this enum: forecasts,
 * charts, and Telegram channels. Replacing it is a contract change and needs
 * all three owners to agree in writing.
 */
export const REGIONS = [
  "SEOUL",
  "BUSAN",
  "DAEGU",
  "INCHEON",
  "GWANGJU",
  "DAEJEON",
  "ULSAN",
  "JEJU",
] as const;
export const Region = z.enum(REGIONS);
export type Region = z.infer<typeof Region>;

/** ISO date, `YYYY-MM-DD`. All dates in this system are KST calendar dates. */
export const IsoDate = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}$/, "expected YYYY-MM-DD");
export type IsoDate = z.infer<typeof IsoDate>;
