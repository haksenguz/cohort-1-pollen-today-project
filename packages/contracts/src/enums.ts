import { z } from "zod";
import { RiskLevel } from "./graphql.js";

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

/** ISO date, `YYYY-MM-DD`. All dates in this system are KST calendar dates. */
export const IsoDate = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}$/, "expected YYYY-MM-DD");
export type IsoDate = z.infer<typeof IsoDate>;
