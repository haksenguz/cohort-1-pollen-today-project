/**
 * Every shared enum, in one import.
 *
 * These are DECLARED in `src/schema/common.graphql` and generated into
 * `graphql.generated.ts`. This file is a barrel, not a second definition —
 * re-declaring them here as TypeScript enums would be exactly the drift the
 * schema-first decision exists to prevent (ADR 0004).
 *
 * To add or change an enum value, edit the SDL and regenerate:
 *   pnpm --filter @pollen/api schema:generate
 */
export {
  JobStatus,
  PollenType,
  Region,
  RiskLevel,
} from "../../graphql.generated";

import { RiskLevel } from "../../graphql.generated";

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
