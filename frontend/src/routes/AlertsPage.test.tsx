/**
 * AlertsPage tests. The page lists the user's stored alerts, lets them
 * mark an alert read by clicking, and supports an "unread only" filter
 * that maps to the backend's `unread_only` query parameter.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import type { AlertResponse } from "../api/types";

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return {
    ...actual,
    listAlerts: vi.fn(),
    markAlertRead: vi.fn(),
  };
});

import { ApiError, listAlerts, markAlertRead } from "../api/client";
import { AlertsPage } from "./AlertsPage";

const renderPage = () =>
  render(
    <MemoryRouter>
      <AlertsPage />
    </MemoryRouter>,
  );

const alert = (overrides: Partial<AlertResponse> = {}): AlertResponse => ({
  id: 1,
  risk_level: "HIGH",
  alert_type: "POLLEN",
  message: "Tree pollen is high in your area.",
  is_read: false,
  created_at: "2026-09-11T11:30:00Z",
  ...overrides,
});

beforeEach(() => {
  vi.mocked(listAlerts).mockResolvedValue([]);
  vi.mocked(markAlertRead).mockResolvedValue(alert({ is_read: true }));
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("AlertsPage", () => {
  it("shows a loading state while alerts are in flight", () => {
    vi.mocked(listAlerts).mockReturnValue(new Promise(() => {}));

    renderPage();
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("renders one row per alert with risk, type, and message", async () => {
    vi.mocked(listAlerts).mockResolvedValue([
      alert({ id: 1, risk_level: "HIGH", alert_type: "POLLEN", message: "Tree pollen high" }),
      alert({
        id: 2,
        risk_level: "MODERATE",
        alert_type: "AIR_QUALITY",
        message: "PM2.5 is moderate",
      }),
    ]);

    renderPage();
    await waitFor(() => expect(screen.getByText("Tree pollen high")).toBeInTheDocument());
    expect(screen.getByText("PM2.5 is moderate")).toBeInTheDocument();
  });

  it("renders an empty-state note when there are no alerts", async () => {
    vi.mocked(listAlerts).mockResolvedValue([]);

    renderPage();
    await waitFor(() => expect(screen.getByText(/no alerts/i)).toBeInTheDocument());
  });

  it("renders an error state when the alerts endpoint fails", async () => {
    vi.mocked(listAlerts).mockRejectedValue(new ApiError(503, "Alerts offline"));

    renderPage();
    await waitFor(() => expect(screen.getByText(/alerts offline/i)).toBeInTheDocument());
  });

  it("marks an alert as read when the row is clicked", async () => {
    const a = alert({ id: 7, is_read: false });
    vi.mocked(listAlerts).mockResolvedValue([a]);

    renderPage();
    const row = await waitFor(() => screen.getByText(a.message));
    fireEvent.click(row);

    await waitFor(() => expect(markAlertRead).toHaveBeenCalledWith(7));
  });

  it("marks an alert as read on Enter for keyboard users", async () => {
    const a = alert({ id: 9, is_read: false });
    vi.mocked(listAlerts).mockResolvedValue([a]);

    renderPage();
    const row = (await waitFor(() =>
      screen.getByText(a.message).closest('[role="button"]'),
    )) as HTMLElement;
    row.focus();
    fireEvent.keyDown(row, { key: "Enter" });

    await waitFor(() => expect(markAlertRead).toHaveBeenCalledWith(9));
  });

  it("does not send a second PATCH while the first is in flight", async () => {
    const a = alert({ id: 11, is_read: false });
    vi.mocked(listAlerts).mockResolvedValue([a]);
    let resolvePatch!: (v: AlertResponse) => void;
    vi.mocked(markAlertRead).mockReturnValue(
      new Promise<AlertResponse>((resolve) => {
        resolvePatch = resolve;
      }),
    );

    renderPage();
    const row = await waitFor(() => screen.getByText(a.message));
    fireEvent.click(row);
    fireEvent.click(row); // second click while first is still pending

    expect(markAlertRead).toHaveBeenCalledTimes(1);
    resolvePatch(alert({ id: 11, is_read: true }));
    await waitFor(() => expect(markAlertRead).toHaveBeenCalledTimes(1));
  });

  it("re-fetches with unread_only=true when the filter is on", async () => {
    vi.mocked(listAlerts).mockResolvedValue([alert()]);

    renderPage();
    const toggle = await waitFor(() => screen.getByLabelText(/unread only/i));
    fireEvent.click(toggle);

    await waitFor(() =>
      expect(listAlerts).toHaveBeenCalledWith({ unreadOnly: true }),
    );
  });

  it("draws the alerts as one list", async () => {
    vi.mocked(listAlerts).mockResolvedValue([
      alert({ id: 1, risk_level: "HIGH", alert_type: "POLLEN", message: "Tree pollen high" }),
      alert({
        id: 2,
        risk_level: "MODERATE",
        alert_type: "AIR_QUALITY",
        message: "PM2.5 is moderate",
      }),
    ]);

    renderPage();
    await screen.findByText("Tree pollen high");

    // One list, not a stack of cards: every alert is a row in the same list.
    const lists = screen.getAllByRole("list");
    expect(lists).toHaveLength(1);
    const items = Array.from(lists[0].querySelectorAll("li"));
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent("Tree pollen high");
    expect(items[1]).toHaveTextContent("PM2.5 is moderate");
  });

  it("gives every alert a leading icon and one meta line", async () => {
    vi.mocked(listAlerts).mockResolvedValue([
      alert({ id: 1, risk_level: "HIGH", alert_type: "POLLEN", message: "Tree pollen high" }),
    ]);

    renderPage();
    const message = await screen.findByText("Tree pollen high");
    const row = message.closest("li") as HTMLElement;

    // The icon comes before the text.
    expect(row.querySelector("svg")).toBeTruthy();
    expect(row.firstElementChild?.className).toContain("alert-icon");

    // The time and the level share one line.
    const meta = row.querySelector(".alert-meta") as HTMLElement;
    expect(meta).toBeTruthy();
    expect(meta.textContent).toContain("High");
    expect(meta.textContent).toMatch(/just now|\d+ (min|h|d) ago/);
  });

  it("keeps the alert text exactly as the server sends it", async () => {
    const message = "Oak pollen is high. Close your windows before 6 pm.";
    vi.mocked(listAlerts).mockResolvedValue([alert({ id: 3, message })]);

    renderPage();
    await screen.findByText(message);

    expect(screen.getByText(message).textContent).toBe(message);
  });
});
