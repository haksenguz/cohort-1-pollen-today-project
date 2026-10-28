/**
 * The emergency contact endpoints.
 *
 * One contact, on the account row. The app cannot call it: it is a number the
 * person chooses to dial, and this module exists to store it and read it back.
 */
import { getToken } from "../auth/token";
import { API_BASE_URL } from "./client";

export interface EmergencyContact {
  name: string | null;
  phone: string | null;
  note: string | null;
}

export class EmergencyContactError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "EmergencyContactError";
    this.status = status;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * The server's own words about what is wrong with the value.
 *
 * A rejected phone number comes back as a validation list, so the message has
 * to be dug out of it. The text is what tells the user how to fix the value,
 * so it is never replaced with a generic sentence.
 */
function serverMessage(payload: unknown, status: number): string {
  const detail = isRecord(payload) ? payload.detail : undefined;

  if (typeof detail === "string" && detail) return detail;
  if (isRecord(detail) && typeof detail.message === "string") return detail.message;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((entry) => (isRecord(entry) && typeof entry.msg === "string" ? entry.msg : null))
      .filter((entry): entry is string => entry !== null);
    if (messages.length > 0) return messages.join(" ");
  }
  return `Request failed (${status})`;
}

async function request<T>(path: string, method: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetch(new URL(path, API_BASE_URL).toString(), {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  const isJson = response.headers.get("content-type")?.includes("application/json");
  const payload = isJson ? await response.json() : undefined;

  if (!response.ok) {
    throw new EmergencyContactError(response.status, serverMessage(payload, response.status));
  }

  return payload as T;
}

export function readEmergencyContact(): Promise<EmergencyContact> {
  return request<EmergencyContact>("/api/users/me/emergency-contact", "GET");
}

/** Save or clear the contact. An empty field clears it. */
export function saveEmergencyContact(contact: {
  name: string | null;
  phone: string | null;
  note: string | null;
}): Promise<EmergencyContact> {
  return request<EmergencyContact>("/api/users/me/emergency-contact", "PUT", contact);
}
