/**
 * AlertsPage tests. The page lists the user's alerts, groups them by day,
 * collapses identical runs, filters by unread and type, and marks alerts read
 * one at a time or all at once. Filtering runs on the client, so the list is
 * fetched once.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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

/** An ISO timestamp at a local hour, `daysAgo` local days back. */
const at = (daysAgo: number, hour = 12): string => {
  const d = new Date();
  d.setDate(d.getDate() - daysAgo);
  d.setHours(hour, 0, 0, 0);
  return d.toISOString();
};

beforeEach(() => {
  vi.mocked(listAlerts).mockResolvedValue([]);
  vi.mocked(markAlertRead).mockImplementation(async (id: number) =>
    alert({ id, is_read: true }),
  );
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
    expect(screen.getByText("High", { selector: ".al-chip-level" })).toBeInTheDocument();
    expect(screen.getByText("Moderate", { selector: ".al-chip-level" })).toBeInTheDocument();
  });

  it("shows a calm empty state with a link to notification settings", async () => {
    vi.mocked(listAlerts).mockResolvedValue([]);

    renderPage();
    await waitFor(() => expect(screen.getByText(/all caught up/i)).toBeInTheDocument());
    const links = screen.getAllByRole("link", { name: /notification settings/i });
    expect(links.some((l) => l.getAttribute("href") === "/settings?screen=notifications")).toBe(
      true,
    );
  });

  it("renders an error state with Retry that reloads the list", async () => {
    vi.mocked(listAlerts)
      .mockRejectedValueOnce(new ApiError(503, "Alerts offline"))
      .mockResolvedValueOnce([alert({ message: "Back online alert" })]);

    renderPage();
    await waitFor(() => expect(screen.getByText(/alerts offline/i)).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    await waitFor(() => expect(screen.getByText("Back online alert")).toBeInTheDocument());
    expect(listAlerts).toHaveBeenCalledTimes(2);
  });

  it("re-fetches when Refresh is pressed", async () => {
    vi.mocked(listAlerts).mockResolvedValue([alert()]);

    renderPage();
    await screen.findByText("Tree pollen is high in your area.");
    fireEvent.click(screen.getByRole("button", { name: /refresh alerts/i }));

    await waitFor(() => expect(listAlerts).toHaveBeenCalledTimes(2));
  });

  it("marks an alert as read when the row is clicked", async () => {
    const a = alert({ id: 7, is_read: false });
    vi.mocked(listAlerts).mockResolvedValue([a]);

    renderPage();
    const row = await waitFor(() => screen.getByText(a.message));
    fireEvent.click(row);

    await waitFor(() => expect(markAlertRead).toHaveBeenCalledWith(7));
  });

  it("uses a native button for the row, so Enter and Space activate it", async () => {
    const a = alert({ id: 9, is_read: false });
    vi.mocked(listAlerts).mockResolvedValue([a]);

    renderPage();
    const button = (await waitFor(() =>
      screen.getByText(a.message).closest("button"),
    )) as HTMLButtonElement;
    expect(button.tagName).toBe("BUTTON");
    expect(button).toHaveAttribute("aria-expanded", "false");

    fireEvent.click(button);
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

  it("reverts the row and explains when marking read fails", async () => {
    const a = alert({ id: 12, is_read: false, message: "Oak pollen rising" });
    vi.mocked(listAlerts).mockResolvedValue([a]);
    vi.mocked(markAlertRead).mockRejectedValue(new ApiError(500, "Server busy"));

    renderPage();
    fireEvent.click(await screen.findByText("Oak pollen rising"));

    expect(await screen.findByRole("alert")).toHaveTextContent(/could not be marked read/i);
    expect(screen.getByText("1 unread")).toBeInTheDocument();
  });

  it("filters to unread on the client without a second fetch", async () => {
    vi.mocked(listAlerts).mockResolvedValue([
      alert({ id: 1, message: "Still unread alert", is_read: false }),
      alert({ id: 2, message: "Already read alert", is_read: true }),
    ]);

    renderPage();
    await screen.findByText("Still unread alert");
    fireEvent.click(screen.getByRole("button", { name: /^unread/i }));

    expect(screen.getByRole("button", { name: /^unread/i })).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByText("Already read alert")).not.toBeInTheDocument();
    expect(screen.getByText("Still unread alert")).toBeInTheDocument();
    expect(listAlerts).toHaveBeenCalledTimes(1);
  });

  it("shows only one alert type when its chip is chosen", async () => {
    vi.mocked(listAlerts).mockResolvedValue([
      alert({ id: 1, alert_type: "POLLEN", message: "Birch count climbing" }),
      alert({ id: 2, alert_type: "WEATHER", message: "Storm later today" }),
    ]);

    renderPage();
    await screen.findByText("Storm later today");
    fireEvent.click(screen.getByRole("button", { name: /^weather/i }));

    expect(screen.queryByText("Birch count climbing")).not.toBeInTheDocument();
    expect(screen.getByText("Storm later today")).toBeInTheDocument();
  });

  it("explains an empty filter and offers to show all", async () => {
    vi.mocked(listAlerts).mockResolvedValue([
      alert({ id: 1, message: "Old read alert", is_read: true }),
    ]);

    renderPage();
    await screen.findByText("Old read alert");
    fireEvent.click(screen.getByRole("button", { name: /^unread/i }));

    expect(screen.getByText("No unread alerts")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /show all alerts/i }));
    expect(screen.getByText("Old read alert")).toBeInTheDocument();
  });

  it("groups alerts under Today, Yesterday and Earlier", async () => {
    vi.mocked(listAlerts).mockResolvedValue([
      alert({ id: 1, message: "Fresh one", created_at: at(0) }),
      alert({ id: 2, message: "Yesterday one", created_at: at(1) }),
      alert({ id: 3, message: "Old one", created_at: at(9) }),
    ]);

    renderPage();
    await screen.findByText("Fresh one");

    const today = screen.getByRole("heading", { name: "Today" }).closest("section") as HTMLElement;
    expect(within(today).getByText("Fresh one")).toBeInTheDocument();
    const yesterday = screen.getByRole("heading", { name: "Yesterday" }).closest("section") as HTMLElement;
    expect(within(yesterday).getByText("Yesterday one")).toBeInTheDocument();
    const earlier = screen.getByRole("heading", { name: "Earlier" }).closest("section") as HTMLElement;
    expect(within(earlier).getByText("Old one")).toBeInTheDocument();
  });

  it("collapses a run of identical consecutive alerts into one row with a count", async () => {
    const birch = "Birch pollen is high.";
    vi.mocked(listAlerts).mockResolvedValue([
      alert({ id: 5, message: birch, created_at: at(0, 11) }),
      alert({ id: 4, message: birch, created_at: at(0, 10) }),
      alert({ id: 3, message: birch, created_at: at(0, 9) }),
      alert({ id: 2, message: "Storm later today" }),
    ]);

    renderPage();
    await screen.findByText(birch);

    expect(screen.getAllByText(birch)).toHaveLength(1);
    expect(screen.getByText("x3")).toBeInTheDocument();
    expect(screen.getByText("Storm later today")).toBeInTheDocument();

    // Expanding the run lists each alert in it.
    const toggle = screen.getByText(birch).closest("button") as HTMLButtonElement;
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    const sub = screen.getByRole("list", { name: /3 alerts with this message/i });
    expect(within(sub).getAllByRole("listitem")).toHaveLength(3);
  });

  it("marks every unread alert read with Mark all read", async () => {
    vi.mocked(listAlerts).mockResolvedValue([
      alert({ id: 1, message: "First unread" }),
      alert({ id: 2, message: "Second unread" }),
      alert({ id: 3, message: "Already read", is_read: true }),
    ]);

    renderPage();
    await screen.findByText("First unread");
    expect(screen.getByText("2 unread")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /mark all read/i }));

    await waitFor(() => expect(screen.getByText("All read")).toBeInTheDocument());
    expect(markAlertRead).toHaveBeenCalledTimes(2);
    expect(markAlertRead).toHaveBeenCalledWith(1);
    expect(markAlertRead).toHaveBeenCalledWith(2);
    expect(screen.getByRole("button", { name: /mark all read/i })).toBeDisabled();
  });

  it("offers Open Today only on environment alerts", async () => {
    vi.mocked(listAlerts).mockResolvedValue([
      alert({ id: 1, alert_type: "POLLEN", message: "Pollen row" }),
      alert({ id: 2, alert_type: "GENERAL", message: "General row" }),
    ]);

    renderPage();
    await screen.findByText("Pollen row");

    const links = screen.getAllByRole("link", { name: "Open Today" });
    expect(links).toHaveLength(1);
    expect(links[0]).toHaveAttribute("href", "/today");
  });

  it("gives every alert a leading icon and one meta line", async () => {
    vi.mocked(listAlerts).mockResolvedValue([
      alert({
        id: 1,
        risk_level: "HIGH",
        alert_type: "POLLEN",
        message: "Tree pollen high",
        created_at: at(0, 0),
      }),
    ]);

    renderPage();
    const message = await screen.findByText("Tree pollen high");
    const row = message.closest("li") as HTMLElement;

    // The icon tile comes before the text.
    expect(row.querySelector("svg")).toBeTruthy();
    expect(row.firstElementChild?.className).toContain("al-tile");

    // The level, the time and the kind share one line.
    const meta = row.querySelector(".al-meta") as HTMLElement;
    expect(meta).toBeTruthy();
    expect(meta.textContent).toContain("High");
    expect(meta.textContent).toMatch(/just now|\d+ (min|h) ago/);
  });

  it("keeps the alert text exactly as the server sends it", async () => {
    const message = "Oak pollen is high. Close your windows before 6 pm.";
    vi.mocked(listAlerts).mockResolvedValue([alert({ id: 3, message })]);

    renderPage();
    await screen.findByText(message);

    expect(screen.getByText(message).textContent).toBe(message);
  });

  it("links to notification settings from the top right", async () => {
    vi.mocked(listAlerts).mockResolvedValue([alert()]);

    renderPage();
    await screen.findByText("Tree pollen is high in your area.");
    expect(screen.getByRole("link", { name: /notification settings/i })).toHaveAttribute(
      "href",
      "/settings?screen=notifications",
    );
  });
});
