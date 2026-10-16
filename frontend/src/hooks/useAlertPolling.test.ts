/**
 * useAlertPolling tests.
 *
 * `fetch` is stubbed at the network layer rather than mocking `listAlerts`,
 * so the real request helper in client.ts is exercised too — same choice as
 * allergyChatAdapter.test.ts.
 *
 * The hook keeps its seen-set and its timer at module scope on purpose, so
 * every test re-imports it through `loadHook()` after `vi.resetModules()` to
 * get a clean baseline instead of leaking "already seen" ids between cases.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";

import type { AlertResponse } from "../api/types";

vi.mock("sonner", () => {
  const toast = Object.assign(vi.fn(), {
    error: vi.fn(),
    warning: vi.fn(),
    success: vi.fn(),
    info: vi.fn(),
    message: vi.fn(),
    dismiss: vi.fn(),
  });
  return { toast, Toaster: () => null };
});

const INTERVAL = 60_000;

const alertRow = (overrides: Partial<AlertResponse> = {}): AlertResponse => ({
  id: 1,
  risk_level: "MODERATE",
  alert_type: "TREE_POLLEN",
  message: "Tree pollen is moderate in your area.",
  is_read: false,
  created_at: "2026-10-16T12:00:00Z",
  ...overrides,
});

const okJson = (body: unknown) =>
  new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });

/** Fresh module registry: no carried-over seen-set, timer, or spies. */
async function loadHook() {
  const { useAlertPolling } = await import("./useAlertPolling");
  const { toast } = await import("sonner");
  return { useAlertPolling, toast };
}

let visibility: DocumentVisibilityState = "visible";

const setVisibility = (next: DocumentVisibilityState) => {
  visibility = next;
  document.dispatchEvent(new Event("visibilitychange"));
};

/** Let queued promises settle without moving the clock. */
const flush = () => vi.advanceTimersByTimeAsync(0);

beforeEach(() => {
  vi.useFakeTimers();
  vi.resetModules();
  visibility = "visible";
  Object.defineProperty(document, "visibilityState", {
    configurable: true,
    get: () => visibility,
  });
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("useAlertPolling", () => {
  it("polls GET /api/alerts once per interval", async () => {
    const { useAlertPolling } = await loadHook();
    const fetchSpy = vi.fn().mockResolvedValue(okJson([]));
    vi.stubGlobal("fetch", fetchSpy);

    renderHook(() => useAlertPolling({ pollOnMount: true }));
    await flush();

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const url = String(fetchSpy.mock.calls[0][0]);
    expect(url).toContain("/api/alerts");
    // The full list, not unread_only: the page's own filter should not narrow
    // what the app can notify the user about.
    expect(url).not.toContain("unread_only");

    await vi.advanceTimersByTimeAsync(INTERVAL);
    expect(fetchSpy).toHaveBeenCalledTimes(2);

    await vi.advanceTimersByTimeAsync(INTERVAL * 2);
    expect(fetchSpy).toHaveBeenCalledTimes(4);
  });

  it("does not poll while the document is hidden", async () => {
    const { useAlertPolling } = await loadHook();
    const fetchSpy = vi.fn().mockResolvedValue(okJson([]));
    vi.stubGlobal("fetch", fetchSpy);

    renderHook(() => useAlertPolling({ pollOnMount: true }));
    await flush();
    expect(fetchSpy).toHaveBeenCalledTimes(1);

    act(() => {
      setVisibility("hidden");
    });
    await vi.advanceTimersByTimeAsync(INTERVAL * 5);

    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });

  it("polls once immediately when the document becomes visible again", async () => {
    const { useAlertPolling } = await loadHook();
    const fetchSpy = vi.fn().mockResolvedValue(okJson([]));
    vi.stubGlobal("fetch", fetchSpy);

    renderHook(() => useAlertPolling({ pollOnMount: true }));
    await flush();

    act(() => {
      setVisibility("hidden");
    });
    await vi.advanceTimersByTimeAsync(INTERVAL * 4);
    expect(fetchSpy).toHaveBeenCalledTimes(1);

    // The app may have been backgrounded across a whole alert window, so
    // resuming must not wait a full interval to notice.
    act(() => {
      setVisibility("visible");
    });
    await flush();
    expect(fetchSpy).toHaveBeenCalledTimes(2);

    await vi.advanceTimersByTimeAsync(INTERVAL);
    expect(fetchSpy).toHaveBeenCalledTimes(3);
  });

  it("does not toast alerts that were already there on the first load", async () => {
    const { useAlertPolling, toast } = await loadHook();
    const fetchSpy = vi.fn().mockResolvedValue(
      okJson([
        alertRow({ id: 11 }),
        alertRow({ id: 12, risk_level: "HIGH" }),
        alertRow({ id: 13, risk_level: "EMERGENCY" }),
      ]),
    );
    vi.stubGlobal("fetch", fetchSpy);

    renderHook(() => useAlertPolling({ pollOnMount: true }));
    await flush();

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(toast).not.toHaveBeenCalled();
    expect(toast.warning).not.toHaveBeenCalled();
    expect(toast.error).not.toHaveBeenCalled();
  });

  it("toasts an alert that appears after the first load, and only once", async () => {
    const { useAlertPolling, toast } = await loadHook();
    const fresh = alertRow({ id: 2, message: "Grass pollen is moderate in your area." });
    const fetchSpy = vi
      .fn()
      // Baseline: only the alert that already existed when polling started.
      .mockResolvedValueOnce(okJson([alertRow({ id: 1 })]))
      .mockResolvedValue(okJson([alertRow({ id: 1 }), fresh]));
    vi.stubGlobal("fetch", fetchSpy);

    renderHook(() => useAlertPolling({ pollOnMount: true }));
    await flush();
    expect(toast).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(INTERVAL);
    expect(toast).toHaveBeenCalledTimes(1);
    expect(toast).toHaveBeenCalledWith(
      fresh.message,
      expect.objectContaining({ id: "alert-2" }),
    );

    // Same alert on every later tick: the seen-set must swallow it, or the
    // stack fills with copies of one pollen spike.
    await vi.advanceTimersByTimeAsync(INTERVAL * 3);
    expect(toast).toHaveBeenCalledTimes(1);
  });

  it("escalates HIGH and EMERGENCY onto sonner's warning and error surfaces", async () => {
    const { useAlertPolling, toast } = await loadHook();
    const fetchSpy = vi
      .fn()
      .mockResolvedValueOnce(okJson([alertRow({ id: 1 })]))
      .mockResolvedValue(
        okJson([
          alertRow({ id: 1 }),
          alertRow({ id: 2, risk_level: "HIGH", message: "Tree pollen is high." }),
          alertRow({ id: 3, risk_level: "EMERGENCY", message: "Air quality is dangerous." }),
        ]),
      );
    vi.stubGlobal("fetch", fetchSpy);

    renderHook(() => useAlertPolling({ pollOnMount: true }));
    await vi.advanceTimersByTimeAsync(INTERVAL);

    expect(toast.warning).toHaveBeenCalledWith(
      "Tree pollen is high.",
      expect.objectContaining({ id: "alert-2" }),
    );
    expect(toast.error).toHaveBeenCalledWith(
      "Air quality is dangerous.",
      expect.objectContaining({ id: "alert-3", duration: Infinity }),
    );
    expect(toast).not.toHaveBeenCalled();
  });

  it("keeps polling and stays silent after a failed request", async () => {
    const { useAlertPolling, toast } = await loadHook();
    const fetchSpy = vi
      .fn()
      .mockResolvedValueOnce(okJson([alertRow({ id: 1 })]))
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValue(
        okJson([alertRow({ id: 1 }), alertRow({ id: 2, message: "Grass pollen is moderate." })]),
      );
    vi.stubGlobal("fetch", fetchSpy);

    renderHook(() => useAlertPolling({ pollOnMount: true }));
    await flush();

    await vi.advanceTimersByTimeAsync(INTERVAL); // the failing tick
    expect(toast).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(INTERVAL); // the tick after it
    expect(toast).toHaveBeenCalledTimes(1);
    expect(toast).toHaveBeenCalledWith(
      "Grass pollen is moderate.",
      expect.objectContaining({ id: "alert-2" }),
    );
  });

  it("stops polling once unmounted", async () => {
    const { useAlertPolling } = await loadHook();
    const fetchSpy = vi.fn().mockResolvedValue(okJson([]));
    vi.stubGlobal("fetch", fetchSpy);

    const { unmount } = renderHook(() => useAlertPolling({ pollOnMount: true }));
    await flush();
    expect(fetchSpy).toHaveBeenCalledTimes(1);

    unmount();
    await vi.advanceTimersByTimeAsync(INTERVAL * 4);

    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });

  it("does not poll at all when disabled", async () => {
    const { useAlertPolling } = await loadHook();
    const fetchSpy = vi.fn().mockResolvedValue(okJson([]));
    vi.stubGlobal("fetch", fetchSpy);

    renderHook(() => useAlertPolling({ enabled: false, pollOnMount: true }));
    await vi.advanceTimersByTimeAsync(INTERVAL * 3);

    expect(fetchSpy).not.toHaveBeenCalled();
  });
});