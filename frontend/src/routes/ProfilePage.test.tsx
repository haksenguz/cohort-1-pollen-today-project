/**
 * ProfilePage tests. Three sections, three independent fetches:
 * getCurrentUser, listAllergies, readPreferences.
 *
 * These cover the parts that can be wrong without a browser: that each
 * section renders from its own endpoint, that a save sends the typed
 * request the API contract expects, that a rejected fetch surfaces the
 * server's message instead of a blank card, and that an out-of-range
 * coordinate is rejected before it reaches the network.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
import { ProfilePage } from "./ProfilePage";

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
      <ProfilePage />
    </MemoryRouter>,
  );

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
});

describe("ProfilePage", () => {
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

  it("adds an allergy with the chosen allergen and severity", async () => {
    renderPage();

    await screen.findByText("Tree pollen");
    fireEvent.click(screen.getByRole("button", { name: "Add" }));

    await waitFor(() => {
      expect(createAllergy).toHaveBeenCalledWith({
        allergen: "TREE_POLLEN",
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
