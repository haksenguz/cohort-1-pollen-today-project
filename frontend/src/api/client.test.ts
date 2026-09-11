/**
 * API client tests. Each test stubs `fetch` and asserts:
 *   - the URL and method are right,
 *   - the bearer token is attached on protected routes,
 *   - JSON bodies parse and errors throw `ApiError`.
 *
 * The test base URL falls through to the default `http://localhost:8000`
 * because the client reads `import.meta.env.VITE_API_BASE_URL`, which is
 * not set in tests — that is fine, we mock the network layer.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getToken } from "../auth/token";
import {
  ApiError,
  getNearbyHospitals,
  listAlerts,
  markAlertRead,
  readPreferences,
  updatePreferences,
} from "./client";

vi.mock("../auth/token", () => ({
  getToken: vi.fn(),
}));

const mockFetch = (body: unknown, init: { status?: number; ok?: boolean } = {}) => {
  const status = init.status ?? 200;
  const ok = init.ok ?? (status >= 200 && status < 300);
  return vi.fn().mockResolvedValue({
    ok,
    status,
    statusText: ok ? "OK" : "Error",
    headers: { get: (name: string) => (name === "content-type" ? "application/json" : null) },
    json: async () => body,
  } as unknown as Response);
};

describe("listAlerts", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.mocked(getToken).mockReturnValue("tkn-abc");
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("GETs /api/alerts with the bearer token", async () => {
    fetchSpy = mockFetch([
      {
        id: 1,
        risk_level: "HIGH",
        alert_type: "POLLEN",
        message: "Tree pollen is high",
        is_read: false,
        created_at: "2026-09-11T00:00:00Z",
      },
    ]);
    vi.stubGlobal("fetch", fetchSpy);

    const alerts = await listAlerts();

    expect(alerts).toHaveLength(1);
    expect(alerts[0].id).toBe(1);
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toBe("http://localhost:8000/api/alerts");
    expect(init.method).toBe("GET");
    expect(init.headers.Authorization).toBe("Bearer tkn-abc");
  });

  it("passes unread_only=true when requested", async () => {
    fetchSpy = mockFetch([]);
    vi.stubGlobal("fetch", fetchSpy);

    await listAlerts({ unreadOnly: true });

    const [url] = fetchSpy.mock.calls[0];
    expect(String(url)).toContain("unread_only=true");
  });
});

describe("markAlertRead", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("PATCHes /api/alerts/{id}/read with the bearer token", async () => {
    vi.mocked(getToken).mockReturnValue("tkn-abc");
    const fetchSpy = mockFetch({
      id: 7,
      risk_level: "MODERATE",
      alert_type: "AIR_QUALITY",
      message: "PM2.5 is moderate",
      is_read: true,
      created_at: "2026-09-11T00:00:00Z",
    });
    vi.stubGlobal("fetch", fetchSpy);

    const result = await markAlertRead(7);

    expect(result.is_read).toBe(true);
    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toBe("http://localhost:8000/api/alerts/7/read");
    expect(init.method).toBe("PATCH");
    expect(init.headers.Authorization).toBe("Bearer tkn-abc");
  });

  it("throws ApiError when the server returns 404", async () => {
    vi.mocked(getToken).mockReturnValue(null);
    const fetchSpy = mockFetch({ detail: "Alert not found" }, { status: 404, ok: false });
    vi.stubGlobal("fetch", fetchSpy);

    await expect(markAlertRead(999)).rejects.toMatchObject({
      name: "ApiError",
      status: 404,
      detail: "Alert not found",
    } satisfies Partial<ApiError>);
  });
});

describe("readPreferences", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("GETs /api/notifications/preferences", async () => {
    vi.mocked(getToken).mockReturnValue("tkn-abc");
    const fetchSpy = mockFetch({
      alert_pollen: true,
      alert_air_quality: true,
      alert_weather: false,
      min_risk_level: "HIGH",
      quiet_hours_start: 22,
      quiet_hours_end: 7,
    });
    vi.stubGlobal("fetch", fetchSpy);

    const prefs = await readPreferences();

    expect(prefs.min_risk_level).toBe("HIGH");
    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toBe("http://localhost:8000/api/notifications/preferences");
    expect(init.method).toBe("GET");
  });
});

describe("updatePreferences", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("PUTs the body to /api/notifications/preferences", async () => {
    vi.mocked(getToken).mockReturnValue("tkn-abc");
    const fetchSpy = mockFetch({
      alert_pollen: true,
      alert_air_quality: false,
      alert_weather: false,
      min_risk_level: "MODERATE",
      quiet_hours_start: null,
      quiet_hours_end: null,
    });
    vi.stubGlobal("fetch", fetchSpy);

    const prefs = await updatePreferences({
      alert_air_quality: false,
      min_risk_level: "MODERATE",
    });

    expect(prefs.alert_air_quality).toBe(false);
    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toBe("http://localhost:8000/api/notifications/preferences");
    expect(init.method).toBe("PUT");
    expect(JSON.parse(init.body)).toEqual({
      alert_air_quality: false,
      min_risk_level: "MODERATE",
    });
  });
});

describe("getNearbyHospitals", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("forwards lat/lon and query params as numbers", async () => {
    vi.mocked(getToken).mockReturnValue(null);
    const fetchSpy = mockFetch({
      latitude: 37.5,
      longitude: 127.0,
      specialty: "ENT",
      provider_available: true,
      count: 0,
      results: [],
    });
    vi.stubGlobal("fetch", fetchSpy);

    await getNearbyHospitals({ lat: 37.5, lon: 127.0, specialty: "ENT", radius_m: 3000 });

    const [url] = fetchSpy.mock.calls[0];
    expect(String(url)).toContain("lat=37.5");
    expect(String(url)).toContain("lon=127");
    expect(String(url)).toContain("specialty=ENT");
    expect(String(url)).toContain("radius_m=3000");
  });
});
