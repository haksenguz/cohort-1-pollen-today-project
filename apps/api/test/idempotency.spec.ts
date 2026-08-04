import {
  AlertIdempotencyKey,
  RISK_LEVELS,
  riskAtLeast,
} from "@pollen/contracts";
import { describe, expect, it } from "vitest";
import { kstDatePlus, kstToday } from "../src/libs/kst";

describe("risk level ordering", () => {
  it("is ordered low to very high", () => {
    expect(RISK_LEVELS).toEqual(["LOW", "MODERATE", "HIGH", "VERY_HIGH"]);
  });

  it("fires at or above the threshold", () => {
    expect(riskAtLeast("HIGH", "HIGH")).toBe(true);
    expect(riskAtLeast("VERY_HIGH", "HIGH")).toBe(true);
    expect(riskAtLeast("MODERATE", "HIGH")).toBe(false);
    expect(riskAtLeast("LOW", "HIGH")).toBe(false);
  });
});

describe("KST dates", () => {
  it("returns YYYY-MM-DD", () => {
    expect(kstToday()).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it("rolls the date over at 15:00 UTC, not at midnight UTC", () => {
    // 2026-08-04T15:30Z is 2026-08-05 00:30 in Seoul.
    const late = new Date("2026-08-04T15:30:00Z");
    expect(kstToday(late)).toBe("2026-08-05");
  });

  it("adds whole days", () => {
    const at = new Date("2026-08-04T01:00:00Z");
    expect(kstDatePlus(1, at)).toBe("2026-08-05");
    expect(kstDatePlus(3, at)).toBe("2026-08-07");
  });
});

describe("idempotency key", () => {
  it("accepts a well-formed key", () => {
    const parsed = AlertIdempotencyKey.parse({
      channel: "@pollen_seoul",
      region: "SEOUL",
      pollenType: "WEEDS",
      targetDate: "2026-08-05",
    });
    expect(parsed.region).toBe("SEOUL");
  });

  it("rejects a malformed date", () => {
    expect(() =>
      AlertIdempotencyKey.parse({
        channel: "@pollen_seoul",
        region: "SEOUL",
        pollenType: "WEEDS",
        targetDate: "05-08-2026",
      }),
    ).toThrow();
  });
});
