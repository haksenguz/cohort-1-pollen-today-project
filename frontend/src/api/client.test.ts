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
import type { ToolCallEvent } from "./types";
import {
  API_BASE_URL,
  ApiError,
  getConversation,
  getNearbyHospitals,
  listAlerts,
  listConversations,
  markAlertRead,
  readPreferences,
  streamChat,
  UNKNOWN_TOOL_NAME,
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

  it("sends the search as q and leaves it off when there is none", async () => {
    vi.mocked(getToken).mockReturnValue("tkn-abc");
    const fetchSpy = mockFetch({ conversations: [] });
    vi.stubGlobal("fetch", fetchSpy);

    await listConversations("pollen");
    await listConversations("   ");
    await listConversations();

    const [searched] = fetchSpy.mock.calls[0];
    expect(String(searched)).toBe(`${API_BASE_URL}/api/conversations?q=pollen`);
    const [blank] = fetchSpy.mock.calls[1];
    expect(String(blank)).toBe(`${API_BASE_URL}/api/conversations`);
    const [plain] = fetchSpy.mock.calls[2];
    expect(String(plain)).toBe(`${API_BASE_URL}/api/conversations`);
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

const sse = (event: string, data: unknown): string =>
  `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;

/** One chunk per element, so the reader's buffering is exercised too. */
const mockSseFetch = (chunks: string[]) => {
  const encoder = new TextEncoder();
  let index = 0;
  return vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    statusText: "OK",
    headers: { get: () => null },
    json: async () => ({}),
    body: {
      getReader: () => ({
        read: async () =>
          index < chunks.length
            ? { done: false, value: encoder.encode(chunks[index++]) }
            : { done: true, value: undefined },
      }),
    },
  } as unknown as Response);
};

const DONE_PAYLOAD = {
  message: "Here are three clinics near you.",
  conversation_id: 42,
  symptoms: [],
  severity: null,
  duration: null,
  possible_trigger: null,
  breathing_difficulty: null,
  airway_swelling: null,
  triage_level: null,
  triage_reasons: [],
  triage_rule_version: null,
};

describe("streamChat tool events", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("fires onTool with the id, name, status and args of a running call", async () => {
    vi.mocked(getToken).mockReturnValue("tkn-abc");
    const onTool = vi.fn();
    const onDone = vi.fn();
    vi.stubGlobal(
      "fetch",
      mockSseFetch([
        sse("status", { stage: "acting" }),
        sse("tool", {
          id: "call_1",
          name: "find_nearby_care",
          status: "running",
          args: { radius_m: 3000 },
        }),
        sse("message", { delta: "Looking now." }),
        sse("done", DONE_PAYLOAD),
      ]),
    );

    await streamChat("clinic near me?", null, { onTool, onDone });

    expect(onTool).toHaveBeenCalledTimes(1);
    expect(onTool).toHaveBeenCalledWith({
      id: "call_1",
      name: "find_nearby_care",
      status: "running",
      args: { radius_m: 3000 },
      summary: null,
      result: null,
    });
    expect(onDone).toHaveBeenCalledTimes(1);
  });

  it("still reports status, message and done exactly as before", async () => {
    vi.mocked(getToken).mockReturnValue("tkn-abc");
    const onStatus = vi.fn();
    const onMessage = vi.fn();
    const onError = vi.fn();
    const onDone = vi.fn();
    vi.stubGlobal(
      "fetch",
      mockSseFetch([
        sse("status", { stage: "extracting" }),
        sse("message", { delta: "How long has it been going on?" }),
        sse("done", DONE_PAYLOAD),
      ]),
    );

    await streamChat("my chest feels tight", null, { onStatus, onMessage, onError, onDone });

    expect(onStatus).toHaveBeenCalledWith({ stage: "extracting" });
    expect(onMessage).toHaveBeenCalledWith("How long has it been going on?");
    expect(onError).not.toHaveBeenCalled();
    // Unchanged on purpose. This test is the additive-contract guard: if a
    // feature starts mutating the `done` payload, this line is where it shows.
    expect(onDone).toHaveBeenCalledWith(DONE_PAYLOAD);
    expect(Object.keys((onDone.mock.calls[0][0] as object))).not.toContain("tool_calls");
  });

  it("carries the clinic list on a done tool event", async () => {
    vi.mocked(getToken).mockReturnValue("tkn-abc");
    const onTool = vi.fn();
    vi.stubGlobal(
      "fetch",
      mockSseFetch([
        sse("tool", {
          id: "call_1",
          name: "find_nearby_care",
          status: "done",
          summary: "3 clinics found",
          result: {
            clinics: [
              { name: "Seoul ENT Clinic", address: "Mapo-gu", distance_m: 1240, phone: "02-000", rank: 1 },
              { name: "Hongdae Allergy Centre", address: null, distance_m: 3100, phone: null, rank: 2 },
            ],
          },
        }),
      ]),
    );

    await streamChat("clinic near me?", null, { onTool });

    const [event] = onTool.mock.calls[0] as [{ result: { clinics: unknown[] } | null }];
    expect(event.result?.clinics).toHaveLength(2);
    expect(event.result?.clinics[0]).toEqual({
      name: "Seoul ENT Clinic",
      address: "Mapo-gu",
      distance_m: 1240,
      phone: "02-000",
      rank: 1,
    });
  });

  it("fills the audit array from tool_calls on the done event", async () => {
    vi.mocked(getToken).mockReturnValue("tkn-abc");
    const onDone = vi.fn();
    vi.stubGlobal(
      "fetch",
      mockSseFetch([
        sse("done", {
          ...DONE_PAYLOAD,
          tool_calls: [
            { name: "find_nearby_care", status: "done", summary: "3 clinics found" },
            { name: "check_availability", status: "error", summary: "No hours source" },
          ],
        }),
      ]),
    );

    await streamChat("clinic near me?", null, { onDone });

    expect(onDone.mock.calls[0][0].tool_calls).toEqual([
      { name: "find_nearby_care", status: "done", summary: "3 clinics found" },
      { name: "check_availability", status: "error", summary: "No hours source" },
    ]);
  });

  it("omits tool_calls entirely when the backend sent no tool audit", async () => {
    vi.mocked(getToken).mockReturnValue("tkn-abc");
    const onDone = vi.fn();
    vi.stubGlobal("fetch", mockSseFetch([sse("done", DONE_PAYLOAD)]));

    await streamChat("hello", null, { onDone });

    // Absent, not []. A key that only appears when the backend sends it is
    // additive; a key injected into every response is a contract change, and
    // it would break every consumer that snapshots the done payload.
    expect(Object.keys(onDone.mock.calls[0][0] as object)).not.toContain("tool_calls");
  });

  it("still fires onTool when the summary is missing", async () => {
    vi.mocked(getToken).mockReturnValue("tkn-abc");
    const onTool = vi.fn();
    vi.stubGlobal(
      "fetch",
      mockSseFetch([
        sse("tool", { id: "call_1", name: "find_nearby_care", status: "done" }),
      ]),
    );

    await streamChat("clinic near me?", null, { onTool });

    expect(onTool).toHaveBeenCalledTimes(1);
    const [event] = onTool.mock.calls[0] as [ToolCallEvent];
    // A summary-less row is not a summary of the tool's name. The chat layer
    // owns the wording; the client must not hand it a raw identifier.
    expect(event.summary).toBeNull();
  });

  it("renders a missing tool name and an unreadable status instead of crashing", async () => {
    vi.mocked(getToken).mockReturnValue("tkn-abc");
    const onTool = vi.fn();
    vi.stubGlobal(
      "fetch",
      mockSseFetch([
        sse("tool", { id: "call_1", status: "finished" }),
        sse("tool", "not an object"),
      ]),
    );

    await expect(
      streamChat("clinic near me?", null, { onTool }),
    ).resolves.toBeUndefined();

    expect(onTool).toHaveBeenCalledTimes(1);
    const [event] = onTool.mock.calls[0] as [{ name: string; status: string }];
    expect(event.name).toBe(UNKNOWN_TOOL_NAME);
    expect(event.status).toBe("error");
  });

  it("keeps a malformed result null instead of an empty clinic list", async () => {
    vi.mocked(getToken).mockReturnValue("tkn-abc");
    const onTool = vi.fn();
    vi.stubGlobal(
      "fetch",
      mockSseFetch([
        // Every one of these is a result we could not read. Coercing any of
        // them to `[]` is what makes the card claim "no clinics found".
        sse("tool", { id: "c1", name: "find_nearby_care", status: "done", result: {} }),
        sse("tool", { id: "c2", name: "find_nearby_care", status: "done", result: { clinics: "three" } }),
        sse("tool", { id: "c3", name: "find_nearby_care", status: "done", result: "ok" }),
      ]),
    );

    await streamChat("clinic near me?", null, { onTool });

    for (const [event] of onTool.mock.calls as [ToolCallEvent][]) {
      expect(event.result).toBeNull();
    }
  });

  it("carries provider_available so an offline provider is not an empty result", async () => {
    vi.mocked(getToken).mockReturnValue("tkn-abc");
    const onTool = vi.fn();
    vi.stubGlobal(
      "fetch",
      mockSseFetch([
        sse("tool", {
          id: "c1",
          name: "find_nearby_care",
          status: "done",
          result: { provider_available: false, count: 0, clinics: [] },
        }),
        sse("tool", {
          id: "c2",
          name: "find_nearby_care",
          status: "done",
          result: { provider_available: true, clinics: [{ name: "A Clinic", distance_m: 900 }] },
        }),
      ]),
    );

    await streamChat("clinic near me?", null, { onTool });

    const [offline, online] = onTool.mock.calls.map(
      ([event]) => event as ToolCallEvent,
    );
    expect(offline.result?.provider_available).toBe(false);
    expect(offline.result?.clinics).toEqual([]);
    expect(online.result?.provider_available).toBe(true);
    expect(online.result?.clinics).toHaveLength(1);
  });

  it("keeps the stream alive when a tool payload is unparseable JSON", async () => {
    vi.mocked(getToken).mockReturnValue("tkn-abc");
    const onTool = vi.fn();
    const onMessage = vi.fn();
    const onDone = vi.fn();
    vi.stubGlobal(
      "fetch",
      mockSseFetch([
        "event: tool\ndata: {not json\n\n",
        sse("tool", { id: "call_1", name: "find_nearby_care", status: "error", summary: "Provider unavailable" }),
        sse("message", { delta: "I could not reach the clinic list." }),
        sse("done", { ...DONE_PAYLOAD, tool_calls: [{ name: "find_nearby_care", status: "error", summary: "Provider unavailable" }] }),
      ]),
    );

    await expect(
      streamChat("clinic near me?", null, { onTool, onMessage, onDone }),
    ).resolves.toBeUndefined();

    expect(onTool).toHaveBeenCalledTimes(1);
    expect(onTool.mock.calls[0][0].summary).toBe("Provider unavailable");
    expect(onMessage).toHaveBeenCalledTimes(1);
    expect(onDone).toHaveBeenCalledTimes(1);
    expect(onDone.mock.calls[0][0].tool_calls).toHaveLength(1);
  });

  it("never puts a triage field on a tool event", async () => {
    vi.mocked(getToken).mockReturnValue("tkn-abc");
    const onTool = vi.fn();
    vi.stubGlobal(
      "fetch",
      mockSseFetch([
        sse("tool", {
          id: "call_1",
          name: "find_nearby_care",
          status: "error",
          summary: "Provider unavailable",
          triage_level: "EMERGENCY",
          triage_verdict: "emergency",
        }),
      ]),
    );

    await streamChat("clinic near me?", null, { onTool });

    const [event] = onTool.mock.calls[0] as [Record<string, unknown>];
    expect(Object.keys(event)).not.toContain("triage_level");
    expect(Object.keys(event)).not.toContain("triage_verdict");
  });
});

describe("streamChat regenerate", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  const bodyOf = (fetchSpy: ReturnType<typeof mockSseFetch>) =>
    JSON.parse((fetchSpy.mock.calls[0][1] as RequestInit).body as string);

  it("marks the turn as a regeneration when asked", async () => {
    vi.mocked(getToken).mockReturnValue("tkn-abc");
    const fetchSpy = mockSseFetch([sse("message", { delta: "Another answer." })]);
    vi.stubGlobal("fetch", fetchSpy);

    await streamChat("my eyes are itchy", 42, {}, undefined, { regenerate: true });

    expect(bodyOf(fetchSpy)).toEqual({
      message: "my eyes are itchy",
      conversation_id: 42,
      regenerate: true,
    });
  });

  it("leaves a normal turn without the field", async () => {
    vi.mocked(getToken).mockReturnValue("tkn-abc");
    const fetchSpy = mockSseFetch([sse("message", { delta: "An answer." })]);
    vi.stubGlobal("fetch", fetchSpy);

    await streamChat("my eyes are itchy", 42, {});

    expect(bodyOf(fetchSpy)).toEqual({
      message: "my eyes are itchy",
      conversation_id: 42,
    });
  });
});
