/**
 * The text size preference behind the Settings control (bugs.md F4).
 *
 * The load-bearing case is the last describe. A stored value that is missing,
 * zero, or unreadable has to come back as the default step, and the size that
 * reaches the document has to be a size a person can read. A missing value
 * that renders as a fine-looking wrong number is the `RISK_CLASS[level] ?? "low"`
 * failure in utils/format.ts, and it is worse here: an unreadable size is an
 * unreadable app, so the default is named rather than reached through a table
 * lookup miss.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  DEFAULT_TEXT_SIZE,
  TEXT_SIZE_STEPS,
  TEXT_SIZE_STORAGE_KEY,
  applyTextSize,
  isTextSizeId,
  readTextSize,
  resolveTextSize,
  rootFontSizeFor,
  storeTextSize,
} from "./textSize";

/** Everything a browser or an older build could plausibly leave in storage. */
const UNREADABLE: readonly (string | null | undefined)[] = [
  null,
  undefined,
  "",
  "   ",
  "0",
  "0%",
  "0px",
  "NaN",
  "-1",
  "1e999",
  "LARGER",
  "large%",
  "125",
  "true",
  "null",
  "toString",
  "constructor",
  "__proto__",
  "constructor.prototype",
];

const rootSize = () => document.documentElement.style.fontSize;

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  localStorage.clear();
  document.documentElement.style.fontSize = "";
  vi.restoreAllMocks();
});

describe("the size that reaches the document", () => {
  it("gives every step its own root font size", () => {
    const applied = TEXT_SIZE_STEPS.map((step) => {
      applyTextSize(step);
      return rootSize();
    });

    expect(applied).toEqual(["100%", "125%", "150%", "200%"]);
    // Two steps landing on the same size would make one of them a lie.
    expect(new Set(applied).size).toBe(TEXT_SIZE_STEPS.length);
  });

  it("reaches 200%, the size SC 1.4.4 asks for", () => {
    const largest = TEXT_SIZE_STEPS[TEXT_SIZE_STEPS.length - 1];

    applyTextSize(largest);

    expect(rootSize()).toBe("200%");
  });

  it("never builds a size out of arithmetic", () => {
    for (const step of TEXT_SIZE_STEPS) {
      const size = rootFontSizeFor(step);

      expect(size).toBe(`${step.percent}%`);
      expect(size).toMatch(/^\d+(\.\d+)?%$/);
      expect(size).not.toMatch(/NaN|px|undefined/);
      expect(step.percent).toBeGreaterThanOrEqual(100);
    }
  });

  it("applies the stored size when the module loads, before any screen mounts", async () => {
    // This is the reload path: main.tsx pulls in the settings route, so the
    // module is evaluated before the first paint.
    localStorage.setItem(TEXT_SIZE_STORAGE_KEY, "largest");
    document.documentElement.style.fontSize = "";
    vi.resetModules();

    await import("./textSize");

    expect(rootSize()).toBe("200%");
  });
});

describe("storing the choice", () => {
  it("round-trips every step through storage", () => {
    for (const step of TEXT_SIZE_STEPS) {
      storeTextSize(step);

      expect(localStorage.getItem(TEXT_SIZE_STORAGE_KEY)).toBe(step.id);
      expect(readTextSize()).toEqual(step);
    }
  });

  it("replaces the previous choice rather than keeping both", () => {
    storeTextSize(TEXT_SIZE_STEPS[TEXT_SIZE_STEPS.length - 1]);
    storeTextSize(DEFAULT_TEXT_SIZE);

    expect(readTextSize().id).toBe("normal");
    expect(localStorage.getItem(TEXT_SIZE_STORAGE_KEY)).toBe("normal");
  });
});

describe("an unreadable stored value", () => {
  it("resolves missing, zero and corrupt values to the default", () => {
    for (const value of UNREADABLE) {
      const step = resolveTextSize(value);

      expect(step.id).toBe(DEFAULT_TEXT_SIZE.id);
      expect(rootFontSizeFor(step)).toBe("100%");
    }
  });

  it("applies the default size, not an unreadable one, when storage holds junk", () => {
    for (const value of ["0", "0px", "NaN", "gigantic"]) {
      localStorage.setItem(TEXT_SIZE_STORAGE_KEY, value);
      applyTextSize(readTextSize());

      expect(rootSize()).toBe("100%");
      expect(rootSize()).not.toMatch(/NaN|0px/);
    }
  });

  it("does not accept a name it only has through the object prototype", () => {
    // The step table is an object, so `"toString" in table` would be true.
    expect(isTextSizeId("toString")).toBe(false);
    expect(resolveTextSize("toString").id).toBe("normal");
  });

  it("accepts every id the UI offers and nothing else", () => {
    for (const step of TEXT_SIZE_STEPS) {
      expect(isTextSizeId(step.id)).toBe(true);
      expect(resolveTextSize(step.id)).toEqual(step);
    }
    expect(isTextSizeId(100)).toBe(false);
    expect(isTextSizeId(null)).toBe(false);
  });

  it("takes a stored id with stray whitespace as the step it names", () => {
    // Padding is still that step, not a different one: this is the only
    // normalisation done on a stored value.
    expect(resolveTextSize("  large  ").id).toBe("large");
  });
});

describe("storage that refuses", () => {
  it("still applies the size when the write is refused", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("storage is full", "QuotaExceededError");
    });

    expect(() => storeTextSize(DEFAULT_TEXT_SIZE)).not.toThrow();

    applyTextSize(DEFAULT_TEXT_SIZE);
    expect(rootSize()).toBe("100%");
  });

  it("falls back to the default when the read is refused", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new DOMException("blocked", "SecurityError");
    });

    expect(readTextSize()).toEqual(DEFAULT_TEXT_SIZE);
  });
});