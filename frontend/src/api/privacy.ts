/**
 * The privacy rights: export and delete.
 *
 * The server has had both endpoints for a long time. The Settings screen said
 * it had neither, and showed a disabled delete button next to the sentence
 * "the server has no delete endpoint". A user reading that is told the
 * company cannot remove their data, which was never true.
 */
import { getToken } from "../auth/token";
import { API_BASE_URL } from "./client";

export interface DeleteReceipt {
  deleted: Record<string, number>;
  note: string;
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/** The file name the server asked for, when it named one. */
function filenameFrom(disposition: string | null): string {
  if (!disposition) return "allergy-ai-data.json";
  const match = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(disposition);
  return match?.[1] ?? "allergy-ai-data.json";
}

/**
 * Downloads everything the server holds about this account.
 *
 * The export is a file, not a screen, so this hands the browser a blob and
 * lets it save the file. The server sets `Content-Disposition` and
 * `Cache-Control: no-store`; the second one matters because a cached export
 * of health data sitting in a shared machine's cache is a copy the user did
 * not ask for.
 */
export async function exportMyData(): Promise<string> {
  const response = await fetch(new URL("/api/privacy/export", API_BASE_URL).toString(), {
    headers: authHeaders(),
  });
  if (!response.ok) {
    throw new Error("Could not prepare your export. Try again in a moment.");
  }
  const blob = await response.blob();
  const name = filenameFrom(response.headers.get("content-disposition"));
  const url = URL.createObjectURL(blob);
  try {
    const link = document.createElement("a");
    link.href = url;
    link.download = name;
    link.rel = "noopener";
    document.body.appendChild(link);
    link.click();
    link.remove();
  } finally {
    // The object URL holds the file in memory until it is revoked.
    URL.revokeObjectURL(url);
  }
  return name;
}

/** Deletes the account and everything attached to it. There is no undo. */
export async function deleteMyAccount(): Promise<DeleteReceipt> {
  const response = await fetch(new URL("/api/privacy/account", API_BASE_URL).toString(), {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!response.ok) {
    throw new Error("Could not delete your account. Nothing was removed.");
  }
  return (await response.json()) as DeleteReceipt;
}
