/**
 * Small display formatters used by the Today and Alerts screens. Pure
 * functions, so the tests are direct: no DOM, no fetch, no React.
 */
import { describe, expect, it } from "vitest";

import {
  ALLERGEN_OPTIONS,
  ALLERGY_SEVERITIES,
  formatAllergyLabel,
  formatDistance,
  formatPollen,
  formatPoints,
  formatRelativeTime,
  formatRisk,
  formatSeverityLabel,
  riskClass,
} from "./format";
import type { AllergySeverity } from "../api/types";

describe("formatRisk", () => {
  it("returns a human label per risk level", () => {
    expect(formatRisk("LOW")).toBe("Low");
    expect(formatRisk("MODERATE")).toBe("Moderate");
    expect(formatRisk("HIGH")).toBe("High");
    expect(formatRisk("EMERGENCY")).toBe("Emergency");
  });

  it("falls back to the raw value for unknowns so the UI never lies", () => {
    expect(formatRisk("UNKNOWN_AS_ANY" as never)).toBe("UNKNOWN_AS_ANY");
  });
});

describe("riskClass", () => {
  it("maps risk levels to the CSS class name used by theme.css", () => {
    expect(riskClass("LOW")).toBe("low");
    expect(riskClass("MODERATE")).toBe("moderate");
    expect(riskClass("HIGH")).toBe("high");
    expect(riskClass("EMERGENCY")).toBe("emergency");
  });
});

describe("formatPollen", () => {
  it("lowercases the level for the UI", () => {
    expect(formatPollen("LOW")).toBe("Low");
    expect(formatPollen("MODERATE")).toBe("Moderate");
    expect(formatPollen("HIGH")).toBe("High");
  });

  it("renders a dash for null pollen readings", () => {
    expect(formatPollen(null)).toBe("—");
  });
});

describe("formatDistance", () => {
  it("renders metres under one kilometre", () => {
    expect(formatDistance(0)).toBe("0 m");
    expect(formatDistance(350)).toBe("350 m");
  });

  it("switches to kilometres with one decimal above 1000 m", () => {
    expect(formatDistance(1000)).toBe("1.0 km");
    expect(formatDistance(1750)).toBe("1.8 km");
    expect(formatDistance(9999)).toBe("10.0 km");
  });

  it("renders a dash for null (Naver sometimes omits distance)", () => {
    expect(formatDistance(null)).toBe("—");
  });
});

describe("formatPoints", () => {
  it("returns the number as a string for the score chip", () => {
    expect(formatPoints(0)).toBe("0");
    expect(formatPoints(42)).toBe("42");
  });
});

describe("formatRelativeTime", () => {
  it("renders minutes for sub-hour ages", () => {
    const now = new Date("2026-09-11T12:00:00Z");
    const fiveMinAgo = new Date("2026-09-11T11:55:00Z").toISOString();
    expect(formatRelativeTime(fiveMinAgo, now)).toBe("5 min ago");
  });

  it("renders hours for sub-day ages", () => {
    const now = new Date("2026-09-11T12:00:00Z");
    const threeHoursAgo = new Date("2026-09-11T09:00:00Z").toISOString();
    expect(formatRelativeTime(threeHoursAgo, now)).toBe("3 h ago");
  });

  it("renders days for older timestamps", () => {
    const now = new Date("2026-09-11T12:00:00Z");
    const twoDaysAgo = new Date("2026-09-09T12:00:00Z").toISOString();
    expect(formatRelativeTime(twoDaysAgo, now)).toBe("2 d ago");
  });

  it("renders a dash for unparseable input", () => {
    expect(formatRelativeTime("not a date")).toBe("—");
  });
});

describe("formatAllergyLabel", () => {
  it("returns a human label for every allergen", () => {
    expect(formatAllergyLabel("TREE_POLLEN")).toBe("Tree pollen");
    expect(formatAllergyLabel("GRASS_POLLEN")).toBe("Grass pollen");
    expect(formatAllergyLabel("WEED_POLLEN")).toBe("Weed pollen");
    expect(formatAllergyLabel("PM25")).toBe("PM2.5");
    expect(formatAllergyLabel("PM10")).toBe("PM10");
    expect(formatAllergyLabel("DUST")).toBe("Dust");
    expect(formatAllergyLabel("MOLD")).toBe("Mold");
    expect(formatAllergyLabel("OTHER")).toBe("Other");
  });

  it("offers every allergen in the picker, in a fixed order", () => {
    // Guards the case where someone adds a member to the Allergen type and
    // forgets the picker list: the option would silently never appear.
    // Note this cannot be asserted as "label differs from the enum value",
    // because PM10's label really is "PM10".
    expect([...ALLERGEN_OPTIONS]).toEqual([
      "TREE_POLLEN",
      "GRASS_POLLEN",
      "WEED_POLLEN",
      "PM25",
      "PM10",
      "DUST",
      "MOLD",
      "OTHER",
    ]);
  });
});

describe("formatSeverityLabel", () => {
  it("returns a human label for every severity", () => {
    expect(formatSeverityLabel("MILD")).toBe("Mild");
    expect(formatSeverityLabel("MODERATE")).toBe("Moderate");
    expect(formatSeverityLabel("SEVERE")).toBe("Severe");
  });

  it("covers the whole AllergySeverity union", () => {
    expect(ALLERGY_SEVERITIES).toHaveLength(3);
    for (const severity of ALLERGY_SEVERITIES as readonly AllergySeverity[]) {
      expect(formatSeverityLabel(severity)).not.toBe(severity);
    }
  });
});
