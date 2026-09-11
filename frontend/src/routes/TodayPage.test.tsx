/**
 * TodayPage tests. The page composes two async sources (environment,
 * nearby hospitals) and a sync one (the current user from auth). We
 * mock the API client and useAuth, then assert what the user sees.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import type { EnvironmentResponse, HospitalNearbyResponse, UserResponse } from "../api/types";

vi.mock("../auth/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return {
    ...actual,
    getCurrentEnvironment: vi.fn(),
    getNearbyHospitals: vi.fn(),
  };
});

import { useAuth } from "../auth/AuthContext";
import { ApiError, getCurrentEnvironment, getNearbyHospitals } from "../api/client";
import { TodayPage } from "./TodayPage";

const renderPage = () =>
  render(
    <MemoryRouter>
      <TodayPage />
    </MemoryRouter>,
  );

const user = (overrides: Partial<UserResponse> = {}): UserResponse => ({
  id: 1,
  email: "a@example.com",
  latitude: 37.5665,
  longitude: 126.978,
  created_at: "2026-09-01T00:00:00Z",
  updated_at: "2026-09-01T00:00:00Z",
  ...overrides,
});

const env = (overrides: Partial<EnvironmentResponse> = {}): EnvironmentResponse => ({
  latitude: 37.5665,
  longitude: 126.978,
  pollen: { tree: "HIGH", grass: "MODERATE", weed: null },
  air_quality: { pm25: 35, pm10: 60 },
  weather: { temperature: 18, humidity: 60, wind: 2.4 },
  points: 42,
  risk: "HIGH",
  pollen_is_sample: false,
  ...overrides,
});

const hospitals = (overrides: Partial<HospitalNearbyResponse> = {}): HospitalNearbyResponse => ({
  latitude: 37.5665,
  longitude: 126.978,
  specialty: null,
  provider_available: true,
  count: 0,
  results: [],
  ...overrides,
});

beforeEach(() => {
  vi.mocked(useAuth).mockReturnValue({
    user: user(),
    status: "authenticated",
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    updateUser: vi.fn(),
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("TodayPage — happy path", () => {
  it("shows a loading state while data is in flight", () => {
    vi.mocked(getCurrentEnvironment).mockReturnValue(new Promise(() => {}));
    vi.mocked(getNearbyHospitals).mockReturnValue(new Promise(() => {}));

    renderPage();
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("renders the risk chip, points, pollen, and air quality on success", async () => {
    vi.mocked(getCurrentEnvironment).mockResolvedValue(env());
    vi.mocked(getNearbyHospitals).mockResolvedValue(hospitals());

    renderPage();
    // The risk chip and the pollen row both say "High"; use the heading role.
    await waitFor(() => expect(screen.getByRole("heading", { name: "Today" })).toBeInTheDocument());

    expect(screen.getByText(/42/)).toBeInTheDocument();
    expect(screen.getByText(/35/)).toBeInTheDocument();
    expect(screen.getAllByText("High").length).toBeGreaterThan(0);
  });

  it("renders a hospital row with name and distance", async () => {
    vi.mocked(getCurrentEnvironment).mockResolvedValue(env());
    vi.mocked(getNearbyHospitals).mockResolvedValue(
      hospitals({
        count: 1,
        results: [
          {
            name: "Seoul ENT Clinic",
            address: "12 Sejong-daero",
            distance_m: 420,
            specialty: "ENT",
            category: "hospital",
            phone: "02-1234-5678",
            rank: 1,
          },
        ],
      }),
    );

    renderPage();
    await waitFor(() => expect(screen.getByText("Seoul ENT Clinic")).toBeInTheDocument());
    expect(screen.getByText("420 m")).toBeInTheDocument();
    // Phone text is split across nodes, so assert the whole row contains it.
    expect(screen.getByText(/02-1234-5678/)).toBeInTheDocument();
  });

  it("calls both endpoints with the user's coordinates", async () => {
    vi.mocked(useAuth).mockReturnValue({
      user: user({ latitude: 35.6762, longitude: 139.6503 }),
      status: "authenticated",
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      updateUser: vi.fn(),
    });
    vi.mocked(getCurrentEnvironment).mockResolvedValue(env());
    vi.mocked(getNearbyHospitals).mockResolvedValue(hospitals());

    renderPage();
    await waitFor(() => expect(getCurrentEnvironment).toHaveBeenCalled());

    expect(getCurrentEnvironment).toHaveBeenCalledWith(35.6762, 139.6503);
    expect(getNearbyHospitals).toHaveBeenCalledWith(
      expect.objectContaining({ lat: 35.6762, lon: 139.6503 }),
    );
  });
});

describe("TodayPage — degraded paths", () => {
  it("renders a sample-data warning when pollen is the flagged sample", async () => {
    vi.mocked(getCurrentEnvironment).mockResolvedValue(env({ pollen_is_sample: true }));
    vi.mocked(getNearbyHospitals).mockResolvedValue(hospitals());

    renderPage();
    await waitFor(() => expect(screen.getByText(/sample/i)).toBeInTheDocument());
  });

  it("tells the user to add a location when none is set", () => {
    vi.mocked(useAuth).mockReturnValue({
      user: user({ latitude: null, longitude: null }),
      status: "authenticated",
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      updateUser: vi.fn(),
    });

    renderPage();
    expect(screen.getByText(/add a location/i)).toBeInTheDocument();
    expect(getCurrentEnvironment).not.toHaveBeenCalled();
  });

  it("renders an error state when the environment endpoint fails", async () => {
    vi.mocked(getCurrentEnvironment).mockRejectedValue(
      new ApiError(500, "Environment unavailable"),
    );
    vi.mocked(getNearbyHospitals).mockResolvedValue(hospitals());

    renderPage();
    await waitFor(() =>
      expect(screen.getByText(/environment unavailable/i)).toBeInTheDocument(),
    );
  });

  it("renders a Naver-unavailable note when the provider has no key", async () => {
    vi.mocked(getCurrentEnvironment).mockResolvedValue(env());
    vi.mocked(getNearbyHospitals).mockResolvedValue(
      hospitals({ provider_available: false, count: 0, results: [] }),
    );

    renderPage();
    await waitFor(() => expect(screen.getByText(/naver/i)).toBeInTheDocument());
  });
});
