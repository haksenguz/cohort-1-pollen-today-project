import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ageLabel, fetchAndCache, readCache } from "./swrCache";

beforeEach(() => {
  localStorage.clear();
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("swrCache", () => {
  it("stores a fetched value and reads it back", async () => {
    await fetchAndCache("k", async () => ({ pm25: 14 }));
    expect(readCache<{ pm25: number }>("k", 60_000)?.data).toEqual({ pm25: 14 });
  });

  it("drops an entry older than the max age", async () => {
    await fetchAndCache("k", async () => 1);
    vi.advanceTimersByTime(7 * 3_600_000);
    expect(readCache("k", 6 * 3_600_000)).toBeNull();
  });

  it("shares one request between callers of the same key", async () => {
    const fetcher = vi.fn(async () => 42);
    await Promise.all([fetchAndCache("same", fetcher), fetchAndCache("same", fetcher)]);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("labels the age of a reading", () => {
    const now = Date.now();
    expect(ageLabel(now)).toBe("just now");
    expect(ageLabel(now - 12 * 60_000)).toBe("12 min ago");
    expect(ageLabel(now - 3 * 3_600_000)).toBe("3 h ago");
    expect(ageLabel(null)).toBe("");
  });
});

describe("useSwr", () => {
  it("shows the cached reading at once and swaps in the new one", async () => {
    // Real timers first: React's scheduler must not capture the faked ones.
    vi.useRealTimers();
    const { renderHook, waitFor } = await import("@testing-library/react");
    const { useSwr, resetSwrCache } = await import("./swrCache");
    resetSwrCache();
    await fetchAndCache("env:x", async () => "old");
    // Make the cached entry stale so a refresh runs behind it.
    const raw = JSON.parse(localStorage.getItem("swr:v1:env:x") as string);
    raw.at = Date.now() - 2 * 3_600_000;
    localStorage.setItem("swr:v1:env:x", JSON.stringify(raw));

    const { result } = renderHook(() =>
      useSwr("env:x", async () => "new", { freshMs: 30 * 60_000, maxAgeMs: 6 * 3_600_000 }),
    );

    // The cached reading is there on the first render, with no loading state.
    expect(result.current.loading).toBe(false);
    await waitFor(() => expect(result.current.data).toBe("new"), { timeout: 3000 });
  });
});
