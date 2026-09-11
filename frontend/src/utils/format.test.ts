/**
 * Small display formatters used by the Today and Alerts screens. Pure
 * functions, so the tests are direct: no DOM, no fetch, no React.
 */
import { describe, expect, it } from "vitest";

import {
  formatDistance,
  formatPollen,
  formatPoints,
  formatRelativeTime,
  formatRisk,
  riskClass,
} from "./format";

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
