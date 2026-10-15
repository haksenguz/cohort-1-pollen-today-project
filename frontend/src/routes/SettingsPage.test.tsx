/**
 * SettingsPage tests. Three sections, three independent fetches:
 * getCurrentUser, listAllergies, readPreferences.
 *
 * These cover the parts that can be wrong without a browser: that each
 * section renders from its own endpoint, that a save sends the typed
 * request the API contract expects, that a rejected fetch surfaces the
 * server's message instead of a blank card, and that an out-of-range
 * coordinate is rejected before it reaches the network.
 *
 * The Location section also drives the browser Geolocation API, which jsdom
 * does not implement at all. That absence is load-bearing here: with no
 * stub installed navigator.geolocation is undefined, so the section takes
 * its "this browser cannot find your location" branch for free.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
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

import {
  createAllergy,
  getCurrentUser,
  listAllergies,
  readPreferences,
  updateCurrentUser,
  updatePreferences,
} from "../api/client";
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

const renderPage = () =>
  render(
    <MemoryRouter>
      <SettingsPage />
    </MemoryRouter>,
  );

// GeolocationPosition / GeolocationPositionError carry toJSON() and the
// PERMISSION_DENIED constants, which a hand-built fixture does not need.
// The section only reads coords.latitude, coords.longitude and code.
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
  vi.mocked(createAllergy).mockResolvedValue(allergy({ id: 2 }));
  vi.mocked(updatePreferences).mockResolvedValue(prefs());
  vi.mocked(createAllergy).mockResolvedValue(allergy({ id: 2 }));
});

afterEach(() => {
  vi.restoreAllMocks();
  Reflect.deleteProperty(navigator, "geolocation");
});

describe("SettingsPage", () => {
  it("renders the account email and all three section titles", async () => {
    renderPage();

    expect(await screen.findByText("someone@example.com")).toBeTruthy();
    expect(await screen.findByText("Location")).toBeTruthy();
    expect(await screen.findByText("Allergies")).toBeTruthy();
    expect(await screen.findByText("Notifications")).toBeTruthy();
  });

  it("shows a saved allergy with its human label and severity", async () => {
    renderPage();

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

    expect(
      await screen.findByText("Nothing saved yet. Add what you react to below."),
    ).toBeTruthy();
  });

  it("saves typed coordinates through updateCurrentUser", async () => {
    renderPage();

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

    const lat = await screen.findByLabelText("Latitude");
    fireEvent.change(lat, { target: { value: "999" } });
    fireEvent.click(screen.getByRole("button", { name: "Save location" }));

    expect(
      await screen.findByText(/Latitude must be -90 to 90/),
    ).toBeTruthy();
    expect(updateCurrentUser).not.toHaveBeenCalled();
  });

  it("surfaces the server message when a save fails", async () => {
    vi.mocked(updateCurrentUser).mockRejectedValue(new Error("Could not reach server"));
    renderPage();

    const lat = await screen.findByLabelText("Latitude");
    fireEvent.change(lat, { target: { value: "35.1796" } });
    fireEvent.click(screen.getByRole("button", { name: "Save location" }));

    expect(await screen.findByText("Could not reach server")).toBeTruthy();
  });

  it("clears the location when both fields are emptied", async () => {
    vi.mocked(getCurrentUser).mockResolvedValue(user({ latitude: 37.5665, longitude: 126.978 }));
    renderPage();

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
    vi.mocked(getCurrentUser).mockResolvedValue(user({ latitude: 37.5665, longitude: 126.978 }));
    vi.mocked(updateCurrentUser).mockRejectedValue(new Error("Could not clear location"));
    renderPage();

    const lat = await screen.findByLabelText("Latitude");
    fireEvent.change(lat, { target: { value: "" } });
    fireEvent.change(screen.getByLabelText("Longitude"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Save location" }));

    expect(await screen.findByText("Could not clear location")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Save location" })).not.toBeDisabled();
  });

  it("adds an allergy with the chosen allergen and severity", async () => {
    renderPage();

    // Named allergens, not the old "Tree pollen" bucket — see bugs.md B-005.
    // BIRCH is the picker's default, so Add submits it untouched.
    await screen.findByText("Birch");
    fireEvent.click(screen.getByRole("button", { name: "Add" }));

    await waitFor(() => {
      expect(createAllergy).toHaveBeenCalledWith({
        allergen: "BIRCH",
        severity: "MILD",
      });
    });
  });

  it("toggling a preference sends only that field", async () => {
    renderPage();

    const pollenSwitch = await screen.findByLabelText("Pollen alerts");
    expect(pollenSwitch.getAttribute("data-state")).toBe("checked");

    fireEvent.click(pollenSwitch);

    await waitFor(() => {
      expect(updatePreferences).toHaveBeenCalledWith({ alert_pollen: false });
    });
  });

  it("shows an error card when the profile itself cannot load", async () => {
    vi.mocked(getCurrentUser).mockRejectedValue(new Error("Token expired"));
    renderPage();

    expect(await screen.findByText("Token expired")).toBeTruthy();
    expect(screen.getByText("Back to today")).toBeTruthy();
  });
});

describe("SettingsPage location from geolocation", () => {
  const useLocation = () => screen.findByRole("button", { name: "Use my current location" });

  it("keeps manual coordinate entry behind a closed disclosure", async () => {
    renderPage();

    const summary = await screen.findByText("Enter coordinates manually");
    expect(summary.closest("details")?.open).toBe(false);
  });

  it("saves a GPS fix through updateCurrentUser and fills the manual fields", async () => {
    const geo = stubGeolocation();
    renderPage();

    fireEvent.click(await useLocation());
    await geo.resolve(35.1796, 129.0756);

    // Same payload a manual save sends, not a second write path.
    await waitFor(() => {
      expect(updateCurrentUser).toHaveBeenCalledWith({
        latitude: 35.1796,
        longitude: 129.0756,
      });
    });
    expect((await screen.findByLabelText("Latitude")) as HTMLInputElement).toHaveValue(
      "35.1796",
    );
    expect(await screen.findByText("Saved.")).toBeTruthy();
  });

  it("disables the button and shows progress while the fix is pending", async () => {
    stubGeolocation();
    renderPage();

    fireEvent.click(await useLocation());

    const pending = await screen.findByRole("button", { name: "Locating…" });
    expect(pending).toBeDisabled();
    expect(pending).toHaveAttribute("aria-busy", "true");
  });

  it("names a denied permission, saves nothing and opens the manual entry", async () => {
    const geo = stubGeolocation();
    renderPage();

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

    fireEvent.click(await useLocation());

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This browser cannot find your location",
    );
    expect(updateCurrentUser).not.toHaveBeenCalled();
  });
});
