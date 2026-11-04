/**
 * The 민감정보 consent endpoints (제23조).
 *
 * This sits beside api/client.ts rather than inside it, because the consent
 * state is read before the app shell knows anything about the user, and the
 * policy is public while the consent is per user.
 */
import { getToken } from "../auth/token";
import { API_BASE_URL } from "./client";

/** The code the server sends when 민감정보 processing is refused. */
export const SENSITIVE_CONSENT_REQUIRED = "sensitive_consent_required";

export interface ConsentState {
  purpose: string;
  granted: boolean;
  version: string | null;
  granted_at: string | null;
  withdrawn_at: string | null;
  policy_version: string;
  basis: string;
}

export interface PolicySection {
  heading: string;
  body: string[];
}

export interface PolicyDocument {
  title: string;
  version: string;
  status: string;
  requires_legal_review: boolean;
  operator: string;
  operator_name: string | null;
  operator_registration_number: string | null;
  operator_named: boolean;
  sections: PolicySection[];
  /** The four items 제15조② requires before consent is asked for. */
  required_notice_items: string[];
}

export class ConsentApiError extends Error {
  status: number;
  code: string | null;

  constructor(status: number, code: string | null, message: string) {
    super(message);
    this.name = "ConsentApiError";
    this.status = status;
    this.code = code;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

async function request<T>(
  path: string,
  options: { method?: string; body?: unknown; auth?: boolean } = {},
): Promise<T> {
  const headers: Record<string, string> = {};
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (options.auth) {
    const token = getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(new URL(path, API_BASE_URL).toString(), {
    method: options.method ?? "GET",
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  const isJson = response.headers.get("content-type")?.includes("application/json");
  const payload = isJson ? await response.json() : undefined;

  if (!response.ok) {
    const detail = isRecord(payload) ? payload.detail : undefined;
    const source = isRecord(detail) ? detail : isRecord(payload) ? payload : {};
    const code = typeof source.code === "string" ? source.code : null;
    const message =
      typeof source.message === "string" && source.message
        ? source.message
        : `Request failed (${response.status})`;
    throw new ConsentApiError(response.status, code, message);
  }

  return payload as T;
}

/** What the signed-in user has agreed to, if anything. */
export function readConsent(): Promise<ConsentState> {
  return request<ConsentState>("/api/privacy/consent", { auth: true });
}

/** Grant or withdraw 민감정보 consent. */
export function writeConsent(granted: boolean): Promise<ConsentState> {
  return request<ConsentState>("/api/privacy/consent", {
    method: "POST",
    body: { granted },
    auth: true,
  });
}

/**
 * The privacy policy. Public, because a policy only a signed-in user can read
 * was not disclosed before consent was asked for.
 */
export function readPolicy(): Promise<PolicyDocument> {
  return request<PolicyDocument>("/api/privacy/policy");
}
