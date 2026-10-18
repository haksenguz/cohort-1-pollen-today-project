/**
 * Clinic-list rendering for a chat tool result.
 *
 * The assertions worth having are the state ones. A renderer that shows a list
 * for results and one grey line for everything else looks fine in a happy-path
 * screenshot and is dishonest in production, so each no-list state is pinned
 * to its own text, its own `data-state` and its own ARIA role here.
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ToolResult } from "./ToolResult";
import type { ToolResultClinic } from "./ToolResult";

function clinic(over: Partial<ToolResultClinic> = {}): ToolResultClinic {
  return {
    name: "Seoul Allergy Clinic",
    address: "12 Sejong-daero, Jung-gu, Seoul",
    distance_m: 1240,
    phone: null,
    ...over,
  };
}

const twoClinics = [
  clinic({ name: "Seoul Allergy Clinic", distance_m: 1240, phone: "02-1234-5678" }),
  clinic({
    name: "Han River Hospital",
    address: null,
    distance_m: 3400,
    phone: null,
  }),
];

describe("ToolResult", () => {
  it("renders each clinic with its formatted distance and address", () => {
    render(
      <ToolResult
        status="done"
        summary="2 clinics found"
        result={{ provider_available: true, count: 2, clinics: twoClinics }}
      />,
    );

    const list = screen.getByRole("list");
    const rows = within(list).getAllByRole("listitem");
    expect(rows).toHaveLength(2);

    expect(rows[0]).toHaveTextContent("Seoul Allergy Clinic");
    expect(rows[0]).toHaveTextContent("1.2 km");
    expect(rows[0]).toHaveTextContent("12 Sejong-daero, Jung-gu, Seoul");

    expect(rows[1]).toHaveTextContent("Han River Hospital");
    expect(rows[1]).toHaveTextContent("3.4 km");
  });

  it("formats a sub-kilometre distance in metres", () => {
    render(
      <ToolResult
        status="done"
        result={{ provider_available: true, clinics: [clinic({ distance_m: 480 })] }}
      />,
    );

    expect(screen.getByText("480 m")).toBeInTheDocument();
  });

  it("links a clinic phone number as a tel: link", () => {
    render(
      <ToolResult
        status="done"
        result={{ provider_available: true, clinics: [clinic({ phone: "02-1234-5678" })] }}
      />,
    );

    expect(screen.getByRole("link", { name: "02-1234-5678" })).toHaveAttribute(
      "href",
      "tel:02-1234-5678",
    );
  });

  it("drops spaces from the tel: href but not from the visible number", () => {
    render(
      <ToolResult
        status="done"
        result={{ provider_available: true, clinics: [clinic({ phone: "02 1234 5678" })] }}
      />,
    );

    const link = screen.getByRole("link", { name: "02 1234 5678" });
    expect(link).toHaveAttribute("href", "tel:0212345678");
  });

  it("renders no phone link when the tool returned no phone", () => {
    render(
      <ToolResult
        status="done"
        result={{ provider_available: true, clinics: [clinic({ phone: null })] }}
      />,
    );

    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("says no clinics found when the search ran and returned none", () => {
    render(
      <ToolResult
        status="done"
        summary="0 clinics found"
        result={{ provider_available: true, count: 0, clinics: [] }}
      />,
    );

    const card = screen.getByRole("status");
    expect(card).toHaveAttribute("data-state", "empty");
    expect(screen.getByText("No clinics found")).toBeInTheDocument();
    expect(screen.queryByRole("list")).not.toBeInTheDocument();
  });

  it("renders a failed search differently from a search that found nothing", () => {
    const { container: empty } = render(
      <ToolResult
        status="done"
        summary="0 clinics found"
        result={{ provider_available: true, count: 0, clinics: [] }}
      />,
    );
    const { container: failed } = render(
      <ToolResult status="error" summary="Provider unavailable" result={null} />,
    );

    const emptyCard = empty.querySelector("[data-state]");
    const failedCard = failed.querySelector("[data-state]");

    expect(emptyCard).toHaveAttribute("data-state", "empty");
    expect(failedCard).toHaveAttribute("data-state", "error");
    expect(emptyCard?.getAttribute("class")).not.toBe(failedCard?.getAttribute("class"));
    expect(emptyCard).toHaveAttribute("role", "status");
    expect(failedCard).toHaveAttribute("role", "alert");

    expect(within(emptyCard as HTMLElement).queryByText(/Clinic search failed/)).toBeNull();
    expect(within(failedCard as HTMLElement).getByText("Clinic search failed")).toBeInTheDocument();
    expect(within(failedCard as HTMLElement).getByText("Provider unavailable")).toBeInTheDocument();
  });

  it("never claims a failed or unfinished search found nothing", () => {
    render(<ToolResult status="error" summary="Lookup timed out" result={null} />);

    expect(screen.queryByText("No clinics found")).not.toBeInTheDocument();
    expect(screen.getByText("Clinic search failed")).toBeInTheDocument();
  });

  it("separates an offline provider from both zero results and a failure", () => {
    const { container } = render(
      <ToolResult status="done" result={{ provider_available: false, count: 0, clinics: [] }} />,
    );

    const card = container.querySelector("[data-state]");
    expect(card).toHaveAttribute("data-state", "unavailable");
    expect(screen.getByText("Clinic search is offline")).toBeInTheDocument();
    expect(screen.queryByText("No clinics found")).not.toBeInTheDocument();
    expect(screen.queryByText("Clinic search failed")).not.toBeInTheDocument();
  });

  it("reports an unreadable result as unknown rather than as zero clinics", () => {
    render(<ToolResult status="done" result={null} />);

    expect(screen.getByText("Clinic search result could not be read")).toBeInTheDocument();
    expect(screen.queryByText("No clinics found")).not.toBeInTheDocument();
  });

  it("does not claim zero clinics when the result carries no clinic list", () => {
    // The shape a malformed payload coerces into. It reached the card as `[]`
    // once, and "no clinics found" is a claim nothing here supports.
    const { container } = render(<ToolResult status="done" result={{ count: 0 }} />);

    expect(container.querySelector("[data-state]")).toHaveAttribute("data-state", "unreadable");
    expect(screen.queryByText("No clinics found")).not.toBeInTheDocument();
    expect(screen.getByText("Clinic search result could not be read")).toBeInTheDocument();
  });

  it("does not claim zero clinics when every row it was sent is unreadable", () => {
    const { container } = render(
      <ToolResult
        status="done"
        result={{
          provider_available: true,
          clinics: [
            { name: null } as unknown as ToolResultClinic,
            { name: 42 } as unknown as ToolResultClinic,
          ],
        }}
      />,
    );

    // Counting the raw rows would have taken the results branch and then drawn
    // a header reading "0 found".
    expect(container.querySelector("[data-state]")).toHaveAttribute("data-state", "unreadable");
    expect(screen.queryByText("Nearby clinics")).not.toBeInTheDocument();
    expect(screen.queryByText("No clinics found")).not.toBeInTheDocument();
    expect(screen.queryByText("0 found")).not.toBeInTheDocument();
  });

  it("shows the searching state while the tool is still running", () => {
    const { container } = render(<ToolResult status="running" />);

    expect(container.querySelector("[data-state]")).toHaveAttribute("data-state", "running");
    expect(screen.getByText("Looking for nearby clinics")).toBeInTheDocument();
  });

  it("omits absent optional fields instead of printing undefined", () => {
    const { container } = render(
      <ToolResult
        status="done"
        result={{
          provider_available: true,
          clinics: [{ name: "Namyanju Internal Medicine", address: null, phone: null }],
        }}
      />,
    );

    expect(container.textContent).not.toMatch(/undefined|null|NaN/);
    expect(container.textContent).not.toMatch(/[,·]\s*$/);
    expect(screen.getByText("Namyanju Internal Medicine")).toBeInTheDocument();
  });

  it("survives a malformed row rather than breaking the list", () => {
    const { container } = render(
      <ToolResult
        status="done"
        result={{
          provider_available: true,
          clinics: [
            { name: "   ", address: "nowhere", phone: "02-0000-0000" } as ToolResultClinic,
            clinic({ name: "Real Clinic", distance_m: Number.NaN }),
          ],
        }}
      />,
    );

    const rows = within(screen.getByRole("list")).getAllByRole("listitem");
    expect(rows).toHaveLength(1);
    expect(rows[0]).toHaveTextContent("Real Clinic");
    expect(rows[0]).toHaveTextContent("—");
    expect(container.textContent).not.toMatch(/undefined|NaN/);
  });

  // The backend ships `no_location` as status `error`, so status alone cannot be
  // trusted to mean the search failed. These pin the one case where a failure is
  // actually something the user can fix in five seconds.
  describe("no_location", () => {
    it("never claims there are no clinics nearby", () => {
      render(<ToolResult status="error" result={null} code="no_location" />);

      expect(screen.getByText("We need your location first")).toBeTruthy();
      expect(screen.queryByText("No clinics found")).toBeNull();
      expect(screen.queryByText("Clinic search failed")).toBeNull();
      expect(screen.getByText(/does not mean there are no clinics/)).toBeTruthy();
    });

    it("is its own state, not the generic error state", () => {
      render(<ToolResult status="error" result={null} code="no_location" />);

      expect(document.querySelector('[data-state="no_location"]')).toBeTruthy();
      expect(document.querySelector('[data-state="error"]')).toBeNull();
      // Nothing failed, so it must not be announced as an alert or tinted red.
      expect(screen.queryByRole("alert")).toBeNull();
    });

    it("offers the fix, and the fix is the user's to take", async () => {
      const onAction = vi.fn();
      render(<ToolResult status="error" result={null} code="no_location" onAction={onAction} />);

      await userEvent.click(screen.getByRole("button", { name: "Set your location" }));
      expect(onAction).toHaveBeenCalledTimes(1);
    });

    it("renders without an action rather than inventing one", () => {
      render(<ToolResult status="error" result={null} code="no_location" />);

      expect(screen.queryByRole("button")).toBeNull();
    });

    it("does not override a running call", () => {
      render(<ToolResult status="running" result={null} code="no_location" />);

      expect(document.querySelector('[data-state="running"]')).toBeTruthy();
    });

    it("leaves an unrecognised code as a plain failure", () => {
      render(<ToolResult status="error" result={null} code="something_new" />);

      expect(document.querySelector('[data-state="error"]')).toBeTruthy();
      expect(screen.queryByText("We need your location first")).toBeNull();
    });
  });
});