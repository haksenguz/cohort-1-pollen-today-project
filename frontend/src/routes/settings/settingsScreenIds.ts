/**
 * The settings subscreens, as ids.
 *
 * They live in their own file because the list and the guard are not
 * components. A module that exports components and something else breaks fast
 * refresh, and the ids are read by the page and by the URL, not by a row.
 */

export type SettingsScreenId =
  | "profile"
  | "health"
  | "location"
  | "notifications"
  | "textsize"
  | "privacy"
  | "stored"
  | "export"
  | "delete"
  | "emergency";

const SCREEN_IDS: readonly SettingsScreenId[] = [
  "profile",
  "health",
  "location",
  "notifications",
  "textsize",
  "privacy",
  "stored",
  "export",
  "delete",
  "emergency",
];

/**
 * Guards the `?screen=` query parameter, so a link from another screen can
 * open a subscreen directly. An unknown value opens the overview rather than
 * a blank page.
 */
export function isSettingsScreenId(value: string): value is SettingsScreenId {
  return SCREEN_IDS.some((id) => id === value);
}
