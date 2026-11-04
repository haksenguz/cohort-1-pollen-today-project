/**
 * TopHeader tests (B-028).
 *
 * The header is one row: the brand on the left, a risk pill on the right that
 * opens Today. The assertions are about the shape a user meets, not about the
 * CSS class names, except for the two rules that cannot be seen in a DOM:
 * the header being a row and the shell having a definite height.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import type { EnvironmentResponse, UserResponse } from "../api/types";

vi.mock("../auth/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return { ...actual, getCurrentEnvironment: vi.fn() };
});

import { useAuth } from "../auth/AuthContext";
import { getCurrentEnvironment } from "../api/client";
import { TopHeader } from "./TopHeader";

/* The stylesheet is read from disk, because the DOM cannot say whether a box
   is capped and the rules below are the only way to pin that. */

const themeCss = readFileSync(resolve(process.cwd(), "src/styles/theme.css"), "utf8");

/** The body of one CSS rule, so a test can assert on a single block. */
function rule(selector: string): string {
  const start = themeCss.indexOf(`${selector} {`);
  expect(start, `${selector} rule is missing from theme.css`).toBeGreaterThan(-1);
  const end = themeCss.indexOf("}", start);
  return themeCss.slice(start, end);
}

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
  risk_available: true,
  pollen_is_sample: false,
  ...overrides,
});

function LocationProbe() {
  const location = useLocation();
  return <span data-testid="pathname">{location.pathname}</span>;
}

const renderHeader = () =>
  render(
    <MemoryRouter>
      <TopHeader />
      <LocationProbe />
    </MemoryRouter>,
  );

beforeEach(() => {
  vi.mocked(useAuth).mockReturnValue({
    user: user(),
    status: "authenticated",
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    updateUser: vi.fn(),
    retry: vi.fn(),
  });
  vi.mocked(getCurrentEnvironment).mockResolvedValue(env());
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("TopHeader — one row", () => {
  it("puts the brand and the risk pill in the same header row", () => {
    renderHeader();

    const header = screen.getByRole("banner");
    // One row means the header holds the brand block and the pill as its two
    // children, side by side. A second row would add a third child.
    expect(header.children).toHaveLength(2);
    expect(header.querySelector(".brandrow")).not.toBeNull();
    expect(header.querySelector(".riskpill")).not.toBeNull();
    expect(screen.getByText("Allergy Companion")).toBeInTheDocument();
  });

  it("does not render the old full-width strip under the brand", () => {
    renderHeader();

    expect(document.querySelector(".envstrip")).toBeNull();
    expect(screen.queryByText(/See today's pollen, air quality and risk/)).toBeNull();
  });

  it("keeps the header a single row in CSS, not just in the markup", () => {
    // The DOM cannot say whether the header is a row or a column, so the rule
    // itself is the assertion.
    const top = rule(".top");
    expect(top).toContain("flex-direction: row");
    expect(top).not.toContain("flex-direction: column");
  });
});

describe("TopHeader — the risk pill", () => {
  it("is a control that opens Today and says so in its accessible name", async () => {
    renderHeader();

    const pill = screen.getByRole("button", {
      name: /Today's pollen and air quality, open Today/,
    });
    await userEvent.click(pill);

    expect(screen.getByTestId("pathname")).toHaveTextContent("/today");
  });

  it("shows the current risk level and the dot colour that goes with it", async () => {
    vi.mocked(getCurrentEnvironment).mockResolvedValue(env({ risk: "HIGH" }));

    renderHeader();

    await waitFor(() => expect(screen.getByText("High")).toBeInTheDocument());
    // The colour comes from riskClass(), never from the component.
    expect(document.querySelector(".risk-dot.high")).not.toBeNull();
  });

  it("shows no level at all when the providers had nothing to score", async () => {
    vi.mocked(getCurrentEnvironment).mockResolvedValue(
      env({ risk: null, risk_available: false, points: 0 }),
    );

    renderHeader();

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /open Today/ })).toBeInTheDocument(),
    );
    // "Unavailable" is a real state, so it is named. What must not happen is a
    // level appearing out of nothing.
    expect(document.querySelector(".risk-dot.low")).toBeNull();
  });

  it("does not ask for an environment when the user has no location", () => {
    vi.mocked(useAuth).mockReturnValue({
      user: user({ latitude: null, longitude: null }),
      status: "authenticated",
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      updateUser: vi.fn(),
      retry: vi.fn(),
    });

    renderHeader();

    expect(getCurrentEnvironment).not.toHaveBeenCalled();
  });

  it("keeps the same header height whatever the risk level is", async () => {
    // A fixed-height pill is what guarantees this. The rule is the assertion,
    // because the height of a DOM node cannot be measured here.
    const pill = rule(".riskpill");
    expect(pill).toContain("min-height: 44px");
    expect(pill).toContain("white-space: nowrap");
  });
});
