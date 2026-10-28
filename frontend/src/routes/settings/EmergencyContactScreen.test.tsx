/**
 * The emergency contact screen.
 *
 * The screen has four states that have to be told apart: the saved contact,
 * a save that worked, a save that failed, and a cleared contact. It also has
 * to say the one thing that keeps it honest, which is that the app cannot
 * call the number.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import type { EmergencyContact } from "../../api/emergencyContact";
import { EmergencyContactScreen } from "./Screens";

const contact = (overrides: Partial<EmergencyContact> = {}): EmergencyContact => ({
  name: null,
  phone: null,
  note: null,
  ...overrides,
});

const renderScreen = (props: {
  contact?: EmergencyContact | null;
  loadError?: string | null;
  onSave?: (next: {
    name: string | null;
    phone: string | null;
    note: string | null;
  }) => Promise<void>;
  onRetry?: () => void;
}) => {
  const onSave = props.onSave ?? vi.fn().mockResolvedValue(undefined);
  return render(
    <EmergencyContactScreen
      contact={props.contact === undefined ? contact() : props.contact}
      loadError={props.loadError ?? null}
      onRetry={props.onRetry ?? vi.fn()}
      onSave={onSave}
    />,
  );
};

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("EmergencyContactScreen", () => {
  it("says the app cannot call the contact", () => {
    renderScreen({});

    expect(screen.getByText(/cannot call them for you/)).toBeTruthy();
  });

  it("fills the form from the saved contact", () => {
    renderScreen({
      contact: contact({
        name: "Park Minjun",
        phone: "010-1234-5678",
        note: "Carries an EpiPen",
      }),
    });

    expect(screen.getByLabelText("Name")).toHaveValue("Park Minjun");
    expect(screen.getByLabelText("Phone number")).toHaveValue("010-1234-5678");
    expect(screen.getByLabelText("Note")).toHaveValue("Carries an EpiPen");
  });

  it("sends the typed contact", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    renderScreen({ onSave });

    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Park Minjun" } });
    fireEvent.change(screen.getByLabelText("Phone number"), {
      target: { value: "010-1234-5678" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(onSave).toHaveBeenCalledWith({
        name: "Park Minjun",
        phone: "010-1234-5678",
        note: null,
      }),
    );
  });

  it("clears the contact through the same write", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    renderScreen({
      contact: contact({ name: "Park Minjun", phone: "010-1234-5678" }),
      onSave,
    });

    fireEvent.click(screen.getByRole("button", { name: "Clear" }));

    await waitFor(() =>
      expect(onSave).toHaveBeenCalledWith({ name: null, phone: null, note: null }),
    );
  });

  it("says the contact was saved", async () => {
    renderScreen({});

    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Saved.")).toBeTruthy();
  });

  it("shows the server's message when a save is refused", async () => {
    const onSave = vi.fn().mockRejectedValue(new Error("digits, spaces, dashes and a +"));
    renderScreen({ onSave });

    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("digits, spaces, dashes and a +")).toBeTruthy();
  });

  it("offers a retry when the contact cannot be loaded", () => {
    const onRetry = vi.fn();
    renderScreen({ loadError: "Could not reach server", onRetry });

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
