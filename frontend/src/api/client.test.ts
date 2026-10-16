/**
 * API client tests. Each test stubs `fetch` and asserts:
 *   - the URL and method are right,
 *   - the bearer token is attached on protected routes,
 *   - JSON bodies parse and errors throw `ApiError`.
 *
 * URL assertions are written against the exported `API_BASE_URL`, not a
 * hard-coded `http://localhost:8000`. A developer's `frontend/.env` sets
 * `VITE_API_BASE_URL` (it often points at a LAN or Tailscale address so a
 * phone can reach the laptop), and Vite loads it in test mode too. Asserting
 * the literal localhost default made these tests fail for anyone with a
 * local .env while still passing in CI. We mock the network layer, so what
 * matters is that the path is composed onto whatever base is configured.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getToken } from "../auth/token";
import {
  API_BASE_URL,
  ApiError,
  getConversation,
  getNearbyHospitals,
  listAlerts,
  listConversations,
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
    expect(url).toBe(`${API_BASE_URL}/api/alerts`);
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
    expect(url).toBe(`${API_BASE_URL}/api/alerts/7/read`);
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
    expect(url).toBe(`${API_BASE_URL}/api/notifications/preferences`);
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
    expect(url).toBe(`${API_BASE_URL}/api/notifications/preferences`);
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

describe("listConversations", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("GETs /api/conversations with the bearer token and unwraps the list", async () => {
    vi.mocked(getToken).mockReturnValue("tkn-abc");
    const fetchSpy = mockFetch({
      conversations: [
        {
          id: 42,
          title: "chest tightness after running",
          created_at: "2026-10-16T08:12:00Z",
          updated_at: "2026-10-16T08:14:31Z",
          last_message: "it started about 10 minutes ago",
          message_count: 6,
        },
      ],
    });
    vi.stubGlobal("fetch", fetchSpy);

    const conversations = await listConversations();

    expect(conversations).toHaveLength(1);
    expect(conversations[0].id).toBe(42);
    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toBe(`${API_BASE_URL}/api/conversations`);
    expect(init.method).toBe("GET");
    expect(init.headers.Authorization).toBe("Bearer tkn-abc");
  });

  it("keeps a null title and a null last_message as null rather than coercing them", async () => {
    vi.mocked(getToken).mockReturnValue("tkn-abc");
    const fetchSpy = mockFetch({
      conversations: [
        {
          id: 7,
          title: null,
          created_at: "2026-10-16T08:12:00Z",
          updated_at: "2026-10-16T08:12:00Z",
          last_message: null,
          message_count: 0,
        },
      ],
    });
    vi.stubGlobal("fetch", fetchSpy);

    const [conversation] = await listConversations();

    expect(conversation.title).toBeNull();
    expect(conversation.last_message).toBeNull();
  });
});

describe("getConversation", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("GETs /api/conversations/{id} with the bearer token", async () => {
    vi.mocked(getToken).mockReturnValue("tkn-abc");
    const fetchSpy = mockFetch({
      id: 42,
      title: "chest tightness after running",
      created_at: "2026-10-16T08:12:00Z",
      messages: [
        {
          id: 9001,
          role: "user",
          content: "my chest feels tight",
          triage_level: null,
          triage_reasons: [],
          created_at: "2026-10-16T08:12:00Z",
        },
        {
          id: 9002,
          role: "assistant",
          content: "Thanks. How long has it been going on?",
          triage_level: "MODERATE",
          triage_reasons: ["severity 6 >= 5"],
          created_at: "2026-10-16T08:14:31Z",
        },
      ],
    });
    vi.stubGlobal("fetch", fetchSpy);

    const conversation = await getConversation(42);

    expect(conversation.messages).toHaveLength(2);
    expect(conversation.messages[1].triage_reasons).toEqual(["severity 6 >= 5"]);
    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toBe(`${API_BASE_URL}/api/conversations/42`);
    expect(init.method).toBe("GET");
    expect(init.headers.Authorization).toBe("Bearer tkn-abc");
  });

  // The backend answers 404 for a conversation owned by somebody else, so a
  // 404 has to stay distinguishable from a transport failure: the first is
  // permanent and retrying it is pointless, the second is worth retrying.
  it("surfaces a foreign or missing conversation as ApiError 404", async () => {
    vi.mocked(getToken).mockReturnValue("tkn-abc");
    const fetchSpy = mockFetch({ detail: "Conversation not found" }, { status: 404, ok: false });
    vi.stubGlobal("fetch", fetchSpy);

    await expect(getConversation(999)).rejects.toMatchObject({
      name: "ApiError",
      status: 404,
      detail: "Conversation not found",
    } satisfies Partial<ApiError>);
  });

  it("rejects a network failure as a plain TypeError, not an ApiError", async () => {
    vi.mocked(getToken).mockReturnValue("tkn-abc");
    const fetchSpy = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    vi.stubGlobal("fetch", fetchSpy);

    const error = await getConversation(42).catch((err: unknown) => err);

    expect(error).toBeInstanceOf(TypeError);
    expect(error).not.toBeInstanceOf(ApiError);
  });

  it("surfaces an expired token as ApiError 401", async () => {
    vi.mocked(getToken).mockReturnValue("tkn-stale");
    const fetchSpy = mockFetch({ detail: "Not authenticated" }, { status: 401, ok: false });
    vi.stubGlobal("fetch", fetchSpy);

    await expect(getConversation(42)).rejects.toMatchObject({
      status: 401,
    } satisfies Partial<ApiError>);
  });
});
