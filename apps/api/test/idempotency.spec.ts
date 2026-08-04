import { RISK_LEVELS_ORDERED, RiskLevel, riskAtLeast } from "@pollen/contracts";
import { describe, expect, it } from "vitest";
import { kstDatePlus, kstToday } from "../src/libs/kst";

describe("risk level ordering", () => {
  it("is ordered low to very high", () => {
    expect(RISK_LEVELS_ORDERED).toEqual([
      "LOW",
      "MODERATE",
      "HIGH",
      "VERY_HIGH",
    ]);
  });

  it("fires at or above the threshold", () => {
    expect(riskAtLeast(RiskLevel.HIGH, RiskLevel.HIGH)).toBe(true);
    expect(riskAtLeast(RiskLevel.VERY_HIGH, RiskLevel.HIGH)).toBe(true);
    expect(riskAtLeast(RiskLevel.MODERATE, RiskLevel.HIGH)).toBe(false);
    expect(riskAtLeast(RiskLevel.LOW, RiskLevel.HIGH)).toBe(false);
  });
});

describe("KST dates", () => {
  it("returns YYYY-MM-DD", () => {
    expect(kstToday()).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it("rolls the date over at 15:00 UTC, not at midnight UTC", () => {
    // 2026-08-04T15:30Z is 2026-08-05 00:30 in Seoul.
    expect(kstToday(new Date("2026-08-04T15:30:00Z"))).toBe("2026-08-05");
  });

  it("adds whole days", () => {
    const at = new Date("2026-08-04T01:00:00Z");
    expect(kstDatePlus(1, at)).toBe("2026-08-05");
    expect(kstDatePlus(3, at)).toBe("2026-08-07");
  });
});
