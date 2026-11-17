import type { SettingsScreenId } from "./settingsScreenIds";

/** The heading of each settings subscreen. The header and the page both read it. */
export const SCREEN_TITLE: Record<SettingsScreenId, string> = {
  profile: "Profile",
  health: "Health",
  location: "Location",
  notifications: "Notifications",
  textsize: "Text size",
  privacy: "Privacy and data",
  stored: "What is stored",
  export: "Export my data",
  delete: "Delete my data",
  emergency: "Emergency contact",
};
