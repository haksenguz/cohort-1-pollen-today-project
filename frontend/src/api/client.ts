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
  EnvironmentResponse,
  Health,
  HospitalNearbyParams,
  HospitalNearbyResponse,
  LoginRequest,
  PreferenceResponse,
  PreferenceUpdateRequest,
  RegisterRequest,
  TokenResponse,
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

// ---- Chat (SSE) ------------------------------------------------------
//
// POST /api/chat is Bearer-protected and streams Server-Sent Events: one
// `message` event followed by one `done` event, or a single `error` event.
// It is not a token-by-token stream — `message.delta` carries the full
// assistant reply as one string. See docs/API_CONTRACT.md.
//
// This belongs to the chat vertical (Jack, frontend/src/chat/) — kept here
// only so every endpoint in the contract has a typed client function.

export interface ChatStreamHandlers {
  onMessage?: (delta: string) => void;
  onDone?: (response: ChatResponse) => void;
  onError?: (error: ChatErrorEvent) => void;
}

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
  const data = JSON.parse(dataLines.join("\n"));

  if (eventName === "message") {
    handlers.onMessage?.(data.delta as string);
  } else if (eventName === "done") {
    handlers.onDone?.(data as ChatResponse);
  } else if (eventName === "error") {
    handlers.onError?.(data as ChatErrorEvent);
  }
}
