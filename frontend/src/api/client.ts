/**
 * Hand-written typed client for docs/API_CONTRACT.md. One function per
 * endpoint, bearer token attached automatically on protected routes.
 */
import { getToken } from "../auth/token";
import type {
  AlertResponse,
  AllergyCreateRequest,
  AllergyResponse,
  ChatResponse,
  ChatErrorEvent,
  ChatStatusEvent,
  ConversationDetail,
  ConversationListResponse,
  ConversationSummary,
  DevLlmSettingsResponse,
  DevLlmSettingsUpdateRequest,
  EnvironmentResponse,
  Health,
  HospitalNearbyParams,
  HospitalNearbyResponse,
  LoginRequest,
  NearbyCareClinic,
  NearbyCareResult,
  PreferenceResponse,
  PreferenceUpdateRequest,
  RegisterRequest,
  TokenResponse,
  ToolCallAudit,
  ToolCallEvent,
  ToolCallStatus,
  TriageRequest,
  TriageResponse,
  UserResponse,
  UserUpdateRequest,
} from "./types";

export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined | null>;
  auth?: boolean;
}

function buildUrl(
  path: string,
  query?: RequestOptions["query"],
): string {
  const url = new URL(path, API_BASE_URL);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null) {
        url.searchParams.set(key, String(value));
      }
    }
  }
  return url.toString();
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, query, auth = false } = options;

  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth) {
    const token = getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(buildUrl(path, query), {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (response.status === 204) {
    return undefined as T;
  }

  const isJson = response.headers.get("content-type")?.includes("application/json");
  const payload = isJson ? await response.json() : undefined;

  if (!response.ok) {
    const detail =
      (payload && typeof payload === "object" && "detail" in payload
        ? String((payload as { detail: unknown }).detail)
        : response.statusText) || "Request failed";
    throw new ApiError(response.status, detail);
  }

  return payload as T;
}

// ---- Health ------------------------------------------------------------

export function getHealth(): Promise<Health> {
  return request<Health>("/health");
}

// ---- Auth ------------------------------------------------------------

export function register(body: RegisterRequest): Promise<TokenResponse> {
  return request<TokenResponse>("/api/auth/register", { method: "POST", body });
}

export function login(body: LoginRequest): Promise<TokenResponse> {
  return request<TokenResponse>("/api/auth/login", { method: "POST", body });
}

// ---- Users -------------------------------------------------------------

export function getCurrentUser(): Promise<UserResponse> {
  return request<UserResponse>("/api/users/me", { auth: true });
}

export function updateCurrentUser(body: UserUpdateRequest): Promise<UserResponse> {
  return request<UserResponse>("/api/users/me", { method: "PUT", body, auth: true });
}

// ---- Allergies -------------------------------------------------------

export function listAllergies(): Promise<AllergyResponse[]> {
  return request<AllergyResponse[]>("/api/allergies", { auth: true });
}

export function createAllergy(body: AllergyCreateRequest): Promise<AllergyResponse> {
  return request<AllergyResponse>("/api/allergies", { method: "POST", body, auth: true });
}

export function deleteAllergy(allergyId: number): Promise<void> {
  return request<void>(`/api/allergies/${allergyId}`, { method: "DELETE", auth: true });
}

// ---- Environment -------------------------------------------------------

export function getCurrentEnvironment(lat: number, lon: number): Promise<EnvironmentResponse> {
  return request<EnvironmentResponse>("/api/environment/current", { query: { lat, lon } });
}

// ---- Triage --------------------------------------------------------------

export function submitTriage(body: TriageRequest): Promise<TriageResponse> {
  return request<TriageResponse>("/api/triage", { method: "POST", body });
}

// ---- Hospitals -------------------------------------------------------

export function getNearbyHospitals(
  params: HospitalNearbyParams,
): Promise<HospitalNearbyResponse> {
  const { lat, lon, specialty, location_query, radius_m } = params;
  return request<HospitalNearbyResponse>("/api/hospitals/nearby", {
    query: { lat, lon, specialty, location_query, radius_m },
  });
}

// ---- Notifications ---------------------------------------------------

export interface ListAlertsParams {
  unreadOnly?: boolean;
}

export function listAlerts(params: ListAlertsParams = {}): Promise<AlertResponse[]> {
  return request<AlertResponse[]>("/api/alerts", {
    query: { unread_only: params.unreadOnly },
    auth: true,
  });
}

export function markAlertRead(alertId: number): Promise<AlertResponse> {
  return request<AlertResponse>(`/api/alerts/${alertId}/read`, {
    method: "PATCH",
    auth: true,
  });
}

export function readPreferences(): Promise<PreferenceResponse> {
  return request<PreferenceResponse>("/api/notifications/preferences", { auth: true });
}

export function updatePreferences(
  body: PreferenceUpdateRequest,
): Promise<PreferenceResponse> {
  return request<PreferenceResponse>("/api/notifications/preferences", {
    method: "PUT",
    body,
    auth: true,
  });
}

// ---- Dev settings (local dev only) ---------------------------------------
//
// Only reachable when the backend sets DEV_SETTINGS_ENABLED=true, which is
// true solely in a gitignored local .env. The route is unauthenticated by
// design; that is only safe because the flag is off in every other build. A
// 404 therefore means "feature absent", not "something went wrong", and both
// callers below treat it that way rather than surfacing an error.

export function readDevLlmSettings(): Promise<DevLlmSettingsResponse> {
  return request<DevLlmSettingsResponse>("/api/dev/llm");
}

export function saveDevLlmSettings(
  body: DevLlmSettingsUpdateRequest,
): Promise<DevLlmSettingsResponse> {
  return request<DevLlmSettingsResponse>("/api/dev/llm", { method: "PUT", body });
}

// ---- Conversations ---------------------------------------------------
//
// Both routes are scoped to the caller: the backend answers 404 for a
// conversation owned by somebody else rather than 403, so a 404 here means
// "gone or never yours", never "ask again later".

export function listConversations(): Promise<ConversationSummary[]> {
  return request<ConversationListResponse>("/api/conversations", { auth: true }).then(
    (response) => response.conversations,
  );
}

export function getConversation(conversationId: number): Promise<ConversationDetail> {
  return request<ConversationDetail>(`/api/conversations/${conversationId}`, { auth: true });
}

// ---- Chat (SSE) ------------------------------------------------------
//
// POST /api/chat is Bearer-protected and streams Server-Sent Events: a
// `status` event per pipeline step, any number of `tool` events as the agent
// acts, one `message` event, then one `done` event, or a single `error`
// event. It is not a token-by-token stream — `message.delta` carries the full
// assistant reply as one string. See docs/API_CONTRACT.md and docs/GOAL.md.
//
// The chat screen itself lives in frontend/src/chat/ (TASKS.md J5) — kept here
// only so every endpoint in the contract has a typed client function.

export interface ChatStreamHandlers {
  onMessage?: (delta: string) => void;
  onDone?: (response: ChatResponse) => void;
  onError?: (error: ChatErrorEvent) => void;
  /** Fired for each `status` event: which part of the turn is running now. */
  onStatus?: (event: ChatStatusEvent) => void;
  /** Fired for each `tool` event: a tool call starting, finishing or failing. */
  onTool?: (event: ToolCallEvent) => void;
}

/** Stands in for a tool name the backend did not send. */
export const UNKNOWN_TOOL_NAME = "Unknown tool";

export async function streamChat(
  message: string,
  conversationId: number | null,
  handlers: ChatStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const token = getToken();
  const response = await fetch(buildUrl("/api/chat"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ message, conversation_id: conversationId }),
    signal,
  });

  if (!response.ok || !response.body) {
    let detail = response.statusText || "chat request failed";
    try {
      const payload = await response.json();
      if (payload && typeof payload === "object" && "detail" in payload) {
        detail = String((payload as { detail: unknown }).detail);
      }
    } catch {
      // body wasn't JSON — keep statusText
    }
    throw new ApiError(response.status, detail);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let separatorIndex: number;
    while ((separatorIndex = buffer.indexOf("\n\n")) !== -1) {
      const rawEvent = buffer.slice(0, separatorIndex);
      buffer = buffer.slice(separatorIndex + 2);
      parseSseEvent(rawEvent, handlers);
    }
  }
}

function parseSseEvent(rawEvent: string, handlers: ChatStreamHandlers): void {
  let eventName = "message";
  const dataLines: string[] = [];

  for (const line of rawEvent.split("\n")) {
    if (line.startsWith("event:")) {
      eventName = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trim());
    }
  }

  if (dataLines.length === 0) return;

  let data: unknown;
  try {
    data = JSON.parse(dataLines.join("\n"));
  } catch {
    // One unreadable payload is not worth losing the rest of the turn over.
    return;
  }

  if (eventName === "message") {
    if (isRecord(data)) handlers.onMessage?.(data.delta as string);
  } else if (eventName === "status") {
    handlers.onStatus?.(data as ChatStatusEvent);
  } else if (eventName === "tool") {
    const toolEvent = toToolCallEvent(data);
    if (toolEvent) handlers.onTool?.(toolEvent);
  } else if (eventName === "done") {
    handlers.onDone?.(withToolCalls(data));
  } else if (eventName === "error") {
    handlers.onError?.(data as ChatErrorEvent);
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function toToolCallStatus(value: unknown): ToolCallStatus {
  if (value === "running" || value === "done" || value === "error") return value;
  return "error";
}

function toDisplayName(value: unknown, fallback: string): string {
  return typeof value === "string" && value.length > 0 ? value : fallback;
}

function toOptionalString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function toOptionalNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function toOptionalBoolean(value: unknown): boolean | null {
  return typeof value === "boolean" ? value : null;
}

/**
 * Turns a raw `tool` payload into the shape the chat layer renders. Returns
 * null only when the payload is not an object at all, because there is
 * nothing to render. A payload that is an object but incomplete still fires:
 * the name falls back to `UNKNOWN_TOOL_NAME`, an absent summary stays null for
 * the chat layer to fill, and an unreadable status becomes `error` rather than
 * a call that looks fine.
 */
function toToolCallEvent(data: unknown): ToolCallEvent | null {
  if (!isRecord(data)) return null;
  return {
    id: toOptionalString(data.id) ?? "",
    name: toDisplayName(data.name, UNKNOWN_TOOL_NAME),
    status: toToolCallStatus(data.status),
    args: isRecord(data.args) ? data.args : null,
    summary: toOptionalString(data.summary),
    result: toNearbyCareResult(data.result),
    // Same additive rule: carry the key only when the backend sent one.
    ...(toOptionalString(data.code) === null ? {} : { code: toOptionalString(data.code) as string }),
  };
}

/**
 * A payload that is not an object, or one that carries no clinic list, is
 * null. It is deliberately NOT an empty list: coercing a malformed result to
 * `[]` is what makes a lookup we never got render as "no clinics found", which
 * is the same lie as an unreadable triage level rendering as LOW.
 *
 * `provider_available: false` is the one shape that survives without a clinic
 * list, because it is the server saying outright that it did not search. That
 * is a real value, not a stand-in for a missing one.
 */
function toNearbyCareResult(value: unknown): NearbyCareResult | null {
  if (!isRecord(value)) return null;

  const providerAvailable = toOptionalBoolean(value.provider_available);
  if (providerAvailable === false) return { clinics: [], provider_available: false };

  if (!Array.isArray(value.clinics)) return null;
  return {
    clinics: value.clinics.filter(isRecord).map(toNearbyCareClinic),
    ...(providerAvailable === null ? {} : { provider_available: providerAvailable }),
  };
}

function toNearbyCareClinic(clinic: Record<string, unknown>, index: number): NearbyCareClinic {
  return {
    name: toDisplayName(clinic.name, "Unknown clinic"),
    address: toOptionalString(clinic.address),
    distance_m: toOptionalNumber(clinic.distance_m),
    phone: toOptionalString(clinic.phone),
    // The list is already distance-ordered, so position is the rank the
    // backend would have sent.
    rank: toOptionalNumber(clinic.rank) ?? index + 1,
  };
}

function toToolCallAudit(value: unknown): ToolCallAudit[] {
  if (!Array.isArray(value)) return [];
  return value.filter(isRecord).map((entry) => {
    const id = toOptionalString(entry.id);
    return {
      // Same additive rule as `tool_calls` itself: carry the id only when the
      // backend sent one, rather than stamping `id: null` onto every row.
      ...(id === null ? {} : { id }),
      name: toDisplayName(entry.name, UNKNOWN_TOOL_NAME),
      status: toToolCallStatus(entry.status),
      summary: toOptionalString(entry.summary),
    };
  });
}

/**
 * Attach the audit array ONLY when the backend actually sent one. Injecting
 * `tool_calls: []` into every response would change the `done` payload for
 * every consumer, and the test "still reports status, message and done exactly
 * as before" exists precisely to prove this feature is additive. A new
 * optional key is additive; a new always-present key is not.
 */
function withToolCalls(data: unknown): ChatResponse {
  const response = data as ChatResponse;
  if (isRecord(data) && Array.isArray(data.tool_calls)) {
    response.tool_calls = toToolCallAudit(data.tool_calls);
  }
  return response;
}
