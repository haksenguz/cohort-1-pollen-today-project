/**
 * SettingsPage tests. Three fetches, all from the page: getCurrentUser,
 * listAllergies, readPreferences.
 *
 * The overview only shows values, so most assertions open a row first and then
 * drive the screen behind it. The cases worth keeping are the ones that can be
 * wrong without a browser: that a save sends the typed request the API
 * contract expects, that a rejected fetch surfaces the server's message instead
 * of a blank card, that an out-of-range coordinate never reaches the network,
 * and that an area with nothing behind it says so instead of offering a
 * control that does nothing.
 *
 * The Location screen drives the browser Geolocation API, which jsdom does not
 * implement at all. That absence is load-bearing here: with no stub installed
 * navigator.geolocation is undefined, so the screen takes its "this browser
 * cannot find your location" branch for free.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import type {
  AllergyResponse,
  PreferenceResponse,
  UserResponse,
} from "../api/types";

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return {
    ...actual,
    getCurrentUser: vi.fn(),
    updateCurrentUser: vi.fn(),
    listAllergies: vi.fn(),
    createAllergy: vi.fn(),
    deleteAllergy: vi.fn(),
    readPreferences: vi.fn(),
    updatePreferences: vi.fn(),
  };
});

vi.mock("../api/emergencyContact", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/emergencyContact")>();
  return {
    ...actual,
    readEmergencyContact: vi.fn(),
    saveEmergencyContact: vi.fn(),
  };
});

const auth = vi.hoisted(() => ({ logout: vi.fn() }));

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({
    user: null,
    status: "authenticated",
    login: vi.fn(),
    register: vi.fn(),
    logout: auth.logout,
    updateUser: vi.fn(),
  }),
}));

// The consent state lives in its own provider above the app shell. The page
// only reads it, so the test stands one in.
const consent = vi.hoisted(() => ({
  granted: false,
  withdrawnAt: null as string | null,
  setGranted: vi.fn(),
}));

vi.mock("../auth/ConsentContext", () => ({
  useConsent: () => ({
    status: "ready",
    consent: {
      purpose: "health_data_processing",
      granted: consent.granted,
      version: consent.granted ? "2026-10-19-draft1" : null,
      granted_at: consent.granted ? "2026-10-20T00:00:00Z" : null,
      withdrawn_at: consent.withdrawnAt,
      policy_version: "2026-10-19-draft1",
      basis: "개인정보 보호법 제23조제1항제1호, 제15조제2항",
    },
    policy: {
      title: "개인정보 처리방침 (초안)",
      version: "2026-10-19-draft1",
      status: "draft",
      requires_legal_review: true,
      operator: "Pollen Health Co. (사업자등록번호: 123-45-67890)",
      operator_name: "Pollen Health Co.",
      operator_registration_number: "123-45-67890",
      operator_named: true,
      sections: [],
      required_notice_items: [
        "수집·이용 목적",
        "수집하는 민감정보의 항목",
        "보유 및 이용 기간",
        "동의를 거부할 권리와 거부 시 불이익",
      ],
    },
    granted: consent.granted,
    error: null,
    refresh: vi.fn(),
    setGranted: consent.setGranted,
  }),
}));

import {
  createAllergy,
  deleteAllergy,
  getCurrentUser,
  listAllergies,
  readPreferences,
  updateCurrentUser,
  updatePreferences,
} from "../api/client";
import { readEmergencyContact, saveEmergencyContact } from "../api/emergencyContact";
import { TEXT_SIZE_STORAGE_KEY } from "../prefs/textSize";
import { SettingsPage } from "./SettingsPage";

const user = (overrides: Partial<UserResponse> = {}): UserResponse => ({
  id: 1,
  email: "someone@example.com",
  latitude: 37.5665,
  longitude: 126.978,
  created_at: "2026-09-11T00:00:00Z",
  updated_at: "2026-09-11T00:00:00Z",
  ...overrides,
});

const allergy = (overrides: Partial<AllergyResponse> = {}): AllergyResponse => ({
  id: 1,
  allergen: "TREE_POLLEN",
  severity: "MILD",
  created_at: "2026-09-11T00:00:00Z",
  ...overrides,
});

const prefs = (overrides: Partial<PreferenceResponse> = {}): PreferenceResponse => ({
  alert_pollen: true,
  alert_air_quality: true,
  alert_weather: false,
  min_risk_level: "MODERATE",
  quiet_hours_start: null,
  quiet_hours_end: null,
  ...overrides,
});

/** The defaults backend/app/models/__init__.py gives a fresh account. */
const serverDefaults = prefs({ alert_weather: true });

const renderPage = () =>
  render(
    <MemoryRouter>
      <SettingsPage />
    </MemoryRouter>,
  );

const renderPageAt = (entry: string) =>
  render(
    <MemoryRouter initialEntries={[entry]}>
      <SettingsPage />
    </MemoryRouter>,
  );

const openRow = async (name: RegExp) => {
  fireEvent.click(await screen.findByRole("button", { name }));
};

const openHealth = () => openRow(/^Allergies/);
const openLocation = () => openRow(/^Location/);
const openNotifications = () => openRow(/^Categories/);

// GeolocationPosition / GeolocationPositionError carry toJSON() and the
// PERMISSION_DENIED constants, which a hand-built fixture does not need.
// The screen only reads coords.latitude, coords.longitude and code.
function position(lat: number, lon: number): GeolocationPosition {
  return {
    coords: {
      latitude: lat,
      longitude: lon,
      accuracy: 10,
      altitude: null,
      altitudeAccuracy: null,
      heading: null,
      speed: null,
    },
    timestamp: 1_700_000_000_000,
  } as unknown as GeolocationPosition;
}

function positionError(code: number): GeolocationPositionError {
  return { code, message: "geolocation failed" } as unknown as GeolocationPositionError;
}

/**
 * Installs a navigator.geolocation whose callbacks the test fires by hand.
 * Resolving them synchronously from getCurrentPosition would flush the
 * in-flight button state inside the click, so there would be nothing left
 * to assert about the request being pending.
 */
function stubGeolocation() {
  let succeed: PositionCallback | undefined;
  let fail: PositionErrorCallback | undefined;
  const getCurrentPosition = vi.fn(
    (ok?: PositionCallback | null, err?: PositionErrorCallback | null) => {
      succeed = ok ?? undefined;
      fail = err ?? undefined;
    },
  );
  Object.defineProperty(navigator, "geolocation", {
    value: { getCurrentPosition },
    configurable: true,
  });
  return {
    getCurrentPosition,
    resolve: (lat: number, lon: number) => act(async () => succeed?.(position(lat, lon))),
    reject: (code: number) => act(async () => fail?.(positionError(code))),
  };
}

beforeEach(() => {
  vi.mocked(getCurrentUser).mockResolvedValue(user());
  vi.mocked(listAllergies).mockResolvedValue([allergy()]);
  vi.mocked(readPreferences).mockResolvedValue(prefs());
  vi.mocked(updateCurrentUser).mockResolvedValue(user());
  vi.mocked(createAllergy).mockResolvedValue(allergy({ id: 2, allergen: "BIRCH" }));
  vi.mocked(deleteAllergy).mockResolvedValue(undefined);
  vi.mocked(updatePreferences).mockResolvedValue(prefs());
  vi.mocked(readEmergencyContact).mockResolvedValue({
    name: null,
    phone: null,
    note: null,
  });
  vi.mocked(saveEmergencyContact).mockResolvedValue({
    name: "Park Minjun",
    phone: "010-1234-5678",
    note: null,
  });
  consent.granted = false;
  consent.withdrawnAt = null;
  consent.setGranted.mockReset();
  consent.setGranted.mockResolvedValue(undefined);
});

afterEach(() => {
  vi.restoreAllMocks();
  auth.logout.mockClear();
  Reflect.deleteProperty(navigator, "geolocation");
  // The page now reads a text size out of storage, so a choice made by one
  // test would otherwise still be showing on the next one.
  localStorage.removeItem(TEXT_SIZE_STORAGE_KEY);
});

describe("SettingsPage overview", () => {
  it("lists every area in order, most important first", async () => {
    renderPage();

    await screen.findByText("someone@example.com");
    const headings = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);

    expect(headings).toEqual([
      "Health",
      "Emergency",
      "Notifications",
      "Chat and language",
      "Accessibility",
      "Privacy and data",
      "Advanced",
      "Danger zone",
    ]);
  });

  it("shows the live value on each row, not a static hint", async () => {
    renderPage();

    expect(await screen.findByRole("button", { name: /^Profile/ })).toHaveTextContent(
      "someone@example.com",
    );
    expect(screen.getByRole("button", { name: /^Allergies/ })).toHaveTextContent("1 saved");
    expect(screen.getByRole("button", { name: /^Location/ })).toHaveTextContent(
      "37.5665, 126.9780",
    );
    expect(screen.getByRole("button", { name: /^Categories/ })).toHaveTextContent("2 of 3 on");
    expect(screen.getByRole("button", { name: /^Minimum risk/ })).toHaveTextContent("Moderate");
  });

  it("says a row has nothing saved when the list is empty", async () => {
    vi.mocked(listAllergies).mockResolvedValue([]);
    renderPage();

    expect(await screen.findByRole("button", { name: /^Allergies/ })).toHaveTextContent(
      "Nothing saved yet",
    );
  });

  it("signs out through the auth context", async () => {
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Sign out" }));

    expect(auth.logout).toHaveBeenCalledTimes(1);
  });

  it("wires the destructive control to the delete endpoint that exists", async () => {
    renderPage();

    const deleteButton = await screen.findByRole("button", { name: "Delete account" });
    // The server has had DELETE /api/privacy/account for a long time. A
    // disabled button next to "the server has no delete endpoint" told the
    // user their data could not be removed.
    expect(deleteButton).toBeEnabled();
    expect(deleteButton.closest("section")).not.toHaveTextContent("no delete endpoint");

    fireEvent.click(deleteButton);
    expect((await screen.findAllByText("Delete my data")).length).toBeGreaterThan(0);
    expect(deleteAllergy).not.toHaveBeenCalled();
    expect(createAllergy).not.toHaveBeenCalled();
  });

  it("keeps Advanced closed until it is opened", async () => {
    renderPage();

    const toggle = await screen.findByRole("button", { name: /Developer tools/ });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("Diagnostics")).toBeNull();

    fireEvent.click(toggle);

    expect(await screen.findByText("Diagnostics")).toBeTruthy();
    expect(toggle).toHaveAttribute("aria-expanded", "true");
  });
});

describe("SettingsPage areas with nothing behind them yet", () => {
  it("labels each row not built yet and offers no control", async () => {
    renderPage();

    await screen.findByText("someone@example.com");

    // Accessibility is not in this list: bugs.md F4 gave it a working text
    // size control, and the invariant it is really protecting is that a row
    // with nothing behind it says so rather than offering a dead control.
    // Emergency and Privacy are not in it either: both have a working row now,
    // and the rows around them are still inert.
    for (const name of ["Chat and language"]) {
      const group = screen.getByRole("region", { name });
      expect(within(group).getAllByText("Not built yet").length).toBeGreaterThan(0);
      expect(within(group).queryAllByRole("button")).toHaveLength(0);
      expect(within(group).queryAllByRole("switch")).toHaveLength(0);
      expect(within(group).queryAllByRole("checkbox")).toHaveLength(0);
    }
  });

  it("gives Emergency and Privacy a real row and leaves the rest inert", async () => {
    renderPage();

    await screen.findByText("someone@example.com");

    const emergency = screen.getByRole("region", { name: "Emergency" });
    expect(within(emergency).getByRole("button", { name: /^Emergency contact/ })).toHaveTextContent(
      "Not set",
    );
    expect(within(emergency).getByText("Medical card")).toBeTruthy();
    expect(within(emergency).getAllByText("Not built yet")).toHaveLength(1);

    const privacy = screen.getByRole("region", { name: "Privacy and data" });
    expect(
      within(privacy).getByRole("button", { name: /^Health information consent/ }),
    ).toHaveTextContent("Not agreed yet");
    // Export and delete are real rows now. The server has had both endpoints
    // for a long time, and the rows used to say "Not built yet", which told
    // the user their data could not be taken out.
    expect(within(privacy).getByRole("button", { name: /^What is stored/ })).toBeTruthy();
    expect(within(privacy).getByRole("button", { name: /^Export my data/ })).toBeTruthy();
    expect(within(privacy).getByRole("button", { name: /^Delete my data/ })).toBeTruthy();
    expect(within(privacy).queryAllByText("Not built yet")).toHaveLength(0);
  });

  it("gives Accessibility a real text size row and leaves the rest inert", async () => {
    renderPage();

    const group = await screen.findByRole("region", { name: "Accessibility" });

    expect(within(group).getByRole("button", { name: /^Text size/ })).toHaveTextContent(
      "Normal",
    );
    expect(within(group).getAllByText("Not built yet")).toHaveLength(2);
    expect(within(group).getByText("Reduce motion")).toBeTruthy();
    expect(within(group).getByText("High contrast")).toBeTruthy();
    expect(within(group).queryAllByRole("switch")).toHaveLength(0);
  });

  it("shows the stored text size on the row behind", async () => {
    localStorage.setItem(TEXT_SIZE_STORAGE_KEY, "largest");
    renderPage();

    expect(await screen.findByRole("button", { name: /^Text size/ })).toHaveTextContent(
      "Largest",
    );
  });

  it("keeps Quiet hours and the permission link inert inside Notifications", async () => {
    renderPage();

    const group = await screen.findByRole("region", { name: "Notifications" });
    expect(within(group).getByText("Quiet hours")).toBeTruthy();
    expect(within(group).getByText("Notification permission")).toBeTruthy();
    expect(within(group).getAllByText("Not built yet")).toHaveLength(2);
  });
});

describe("SettingsPage profile and health screens", () => {
  it("shows the account email and says name is not built yet", async () => {
    renderPage();

    await openRow(/^Profile/);

    expect(await screen.findByLabelText("Email")).toHaveValue("someone@example.com");
    expect(screen.getByText("Name").nextElementSibling).toHaveTextContent("Not built yet");
  });

  it("shows a saved allergy with its human label and severity", async () => {
    renderPage();
    await openHealth();

    // Anchor on the Remove button, which only exists in a saved-allergy
    // row. The allergen label on its own also appears in the add picker,
    // so matching on it alone would pass without the list ever rendering.
    const remove = await screen.findByRole("button", { name: "Remove Tree pollen" });
    const row = remove.closest("li");

    expect(row?.textContent).toContain("Tree pollen");
    expect(row?.textContent).toContain("Mild");
  });

  it("says so when there are no allergies instead of rendering a blank card", async () => {
    vi.mocked(listAllergies).mockResolvedValue([]);
    renderPage();
    await openHealth();

    expect(
      await screen.findByText("Nothing saved yet. Add what you react to below."),
    ).toBeTruthy();
  });

  it("adds an allergy and shows it on the row behind", async () => {
    renderPage();
    await openHealth();
    await screen.findByText("Birch");

    fireEvent.click(screen.getByRole("button", { name: "Add" }));

    await waitFor(() => {
      expect(createAllergy).toHaveBeenCalledWith({ allergen: "BIRCH", severity: "MILD" });
    });
    expect(await screen.findByRole("button", { name: "Remove Birch" })).toBeTruthy();
  });

  it("removes an allergy through deleteAllergy", async () => {
    renderPage();
    await openHealth();

    fireEvent.click(await screen.findByRole("button", { name: "Remove Tree pollen" }));

    await waitFor(() => expect(deleteAllergy).toHaveBeenCalledWith(1));
  });

  it("offers a retry when the allergy list cannot load", async () => {
    vi.mocked(listAllergies).mockRejectedValueOnce(new Error("Could not reach server"));
    renderPage();
    await openHealth();

    expect(await screen.findByText("Could not reach server")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("button", { name: "Remove Tree pollen" })).toBeTruthy();
  });

  it("shows an error card when the profile itself cannot load", async () => {
    vi.mocked(getCurrentUser).mockRejectedValue(new Error("Token expired"));
    renderPage();

    expect(await screen.findByText("Token expired")).toBeTruthy();
    expect(screen.getByText("Back to today")).toBeTruthy();
  });
});

describe("SettingsPage notifications screen", () => {
  it("toggling a preference sends only that field", async () => {
    renderPage();
    await openNotifications();

    const pollenSwitch = await screen.findByLabelText("Pollen alerts");
    expect(pollenSwitch.getAttribute("data-state")).toBe("checked");

    fireEvent.click(pollenSwitch);

    await waitFor(() => {
      expect(updatePreferences).toHaveBeenCalledWith({ alert_pollen: false });
    });
  });

  it("restores the documented defaults", async () => {
    vi.mocked(updatePreferences).mockResolvedValue(serverDefaults);
    renderPage();
    await openNotifications();

    fireEvent.click(await screen.findByRole("button", { name: "Restore defaults" }));

    await waitFor(() => {
      expect(updatePreferences).toHaveBeenCalledWith({
        alert_pollen: true,
        alert_air_quality: true,
        alert_weather: true,
        min_risk_level: "MODERATE",
        quiet_hours_start: null,
        quiet_hours_end: null,
      });
    });
    expect(await screen.findByLabelText("Weather alerts")).toHaveAttribute("data-state", "checked");
  });

  it("offers a retry when the preferences cannot load", async () => {
    vi.mocked(readPreferences).mockRejectedValueOnce(new Error("Preferences unavailable"));
    renderPage();
    await openNotifications();

    expect(await screen.findByText("Preferences unavailable")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(await screen.findByLabelText("Pollen alerts")).toBeTruthy();
  });
});

describe("SettingsPage location screen", () => {
  it("saves typed coordinates through updateCurrentUser", async () => {
    renderPage();
    await openLocation();

    const lat = await screen.findByLabelText("Latitude");
    fireEvent.change(lat, { target: { value: "35.1796" } });
    fireEvent.click(screen.getByRole("button", { name: "Save location" }));

    await waitFor(() => {
      expect(updateCurrentUser).toHaveBeenCalledWith({
        latitude: 35.1796,
        longitude: 126.978,
      });
    });
  });

  it("rejects an out-of-range latitude without calling the API", async () => {
    renderPage();
    await openLocation();

    const lat = await screen.findByLabelText("Latitude");
    fireEvent.change(lat, { target: { value: "999" } });
    fireEvent.click(screen.getByRole("button", { name: "Save location" }));

    expect(await screen.findByText(/Latitude must be -90 to 90/)).toBeTruthy();
    expect(updateCurrentUser).not.toHaveBeenCalled();
  });

  it("surfaces the server message when a save fails", async () => {
    vi.mocked(updateCurrentUser).mockRejectedValue(new Error("Could not reach server"));
    renderPage();
    await openLocation();

    const lat = await screen.findByLabelText("Latitude");
    fireEvent.change(lat, { target: { value: "35.1796" } });
    fireEvent.click(screen.getByRole("button", { name: "Save location" }));

    expect(await screen.findByText("Could not reach server")).toBeTruthy();
  });

  it("clears the location when both fields are emptied", async () => {
    renderPage();
    await openLocation();

    const lat = await screen.findByLabelText("Latitude");
    fireEvent.change(lat, { target: { value: "" } });
    fireEvent.change(screen.getByLabelText("Longitude"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Save location" }));

    await waitFor(() => {
      expect(updateCurrentUser).toHaveBeenCalledWith({ latitude: null, longitude: null });
    });
    expect(await screen.findByText("Saved.")).toBeTruthy();
  });

  it("surfaces a failed clear instead of rejecting unhandled", async () => {
    // Regression: the clear branch used to call updateCurrentUser outside any
    // try/catch and never raised `saving`, so a rejected clear produced an
    // unhandled rejection, no message on screen, and a live Save button.
    vi.mocked(updateCurrentUser).mockRejectedValue(new Error("Could not clear location"));
    renderPage();
    await openLocation();

    const lat = await screen.findByLabelText("Latitude");
    fireEvent.change(lat, { target: { value: "" } });
    fireEvent.change(screen.getByLabelText("Longitude"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Save location" }));

    expect(await screen.findByText("Could not clear location")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Save location" })).not.toBeDisabled();
  });

  it("goes back to the overview from a screen", async () => {
    renderPage();
    await openLocation();

    fireEvent.click(await screen.findByRole("button", { name: "Back" }));

    expect(await screen.findByRole("button", { name: /^Location/ })).toBeTruthy();
  });
});

describe("SettingsPage deep links", () => {
  it("opens the screen the link names", async () => {
    // The Today page tells the user to add a location. That button opens
    // /settings?screen=location, so the user lands on the screen that takes
    // one instead of the overview.
    renderPageAt("/settings?screen=location");

    expect(await screen.findByRole("heading", { name: "Location" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /^Emergency contact/ })).toBeNull();
  });

  it("opens the overview for an unknown screen name", async () => {
    renderPageAt("/settings?screen=nonsense");

    expect(await screen.findByRole("button", { name: /^Location/ })).toBeTruthy();
  });
});

describe("SettingsPage location from geolocation", () => {
  const useLocation = () => screen.findByRole("button", { name: "Use my current location" });

  it("keeps manual coordinate entry behind a closed disclosure", async () => {
    renderPage();
    await openLocation();

    const summary = await screen.findByText("Enter coordinates manually");
    expect(summary.closest("details")?.open).toBe(false);
  });

  it("saves a GPS fix through updateCurrentUser and fills the manual fields", async () => {
    const geo = stubGeolocation();
    renderPage();
    await openLocation();

    fireEvent.click(await useLocation());
    await geo.resolve(35.1796, 129.0756);

    // Same payload a manual save sends, not a second write path.
    await waitFor(() => {
      expect(updateCurrentUser).toHaveBeenCalledWith({
        latitude: 35.1796,
        longitude: 129.0756,
      });
    });
    expect((await screen.findByLabelText("Latitude")) as HTMLInputElement).toHaveValue("35.1796");
    expect(await screen.findByText("Saved.")).toBeTruthy();
  });

  it("disables the button and shows progress while the fix is pending", async () => {
    stubGeolocation();
    renderPage();
    await openLocation();

    fireEvent.click(await useLocation());

    const pending = await screen.findByRole("button", { name: "Locating…" });
    expect(pending).toBeDisabled();
    expect(pending).toHaveAttribute("aria-busy", "true");
  });

  it("names a denied permission, saves nothing and opens the manual entry", async () => {
    const geo = stubGeolocation();
    renderPage();
    await openLocation();

    fireEvent.click(await useLocation());
    await geo.reject(1);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Location permission denied");
    expect(updateCurrentUser).not.toHaveBeenCalled();
    // The message tells the reader to type coordinates, so that fallback
    // has to be on screen rather than still collapsed.
    expect(screen.getByText("Enter coordinates manually").closest("details")?.open).toBe(true);
  });

  it("names an unavailable position instead of failing silently", async () => {
    const geo = stubGeolocation();
    renderPage();
    await openLocation();

    fireEvent.click(await useLocation());
    await geo.reject(2);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Your device could not work out a position",
    );
    expect(updateCurrentUser).not.toHaveBeenCalled();
  });

  it("names a timeout instead of failing silently", async () => {
    const geo = stubGeolocation();
    renderPage();
    await openLocation();

    fireEvent.click(await useLocation());
    await geo.reject(3);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Finding your location took too long",
    );
    expect(updateCurrentUser).not.toHaveBeenCalled();
  });

  it("says so when the browser exposes no geolocation at all", async () => {
    // Deliberately unstubbed: jsdom has no navigator.geolocation, which is
    // the same shape as a non-secure context or an older browser.
    renderPage();
    await openLocation();

    fireEvent.click(await useLocation());

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This browser cannot find your location",
    );
    expect(updateCurrentUser).not.toHaveBeenCalled();
  });
});