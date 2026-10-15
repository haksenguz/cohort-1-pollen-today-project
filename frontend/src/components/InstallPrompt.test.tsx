/**
 * InstallPrompt toast-conversion test.
 *
 * The old InstallPrompt rendered a fixed-position .pwa-toast that sat on
 * top of page content (it covered the "Save key" button on /login) with no
 * auto-dismiss. This pins the new contract: the component renders nothing
 * of its own and everything lands in the shared Toaster.
 *
 * The "renders nothing of its own" assertion is deliberately made *after* the
 * event fires. Asserting it on an idle render passes against either
 * implementation — the component returns null before it has anything to show,
 * so a revert to the old markup slipped through a suite that looked green.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { toast } from "sonner";

import { InstallPrompt } from "./InstallPrompt";
import { Toaster } from "./ui/sonner";

const STORAGE_KEY = "allergy_pwa_install_dismissed_at";

function fireBeforeInstallPrompt() {
  const event = new Event("beforeinstallprompt", { cancelable: true });
  Object.defineProperty(event, "prompt", { value: vi.fn().mockResolvedValue(undefined) });
  Object.defineProperty(event, "userChoice", {
    value: vi.fn().mockResolvedValue({ outcome: "dismissed" }),
  });
  window.dispatchEvent(event);
  return event;
}

function renderWithToaster() {
  return render(
    <>
      <InstallPrompt />
      <Toaster />
    </>,
  );
}

beforeEach(() => {
  localStorage.clear();
  // jsdom has no matchMedia in some paths; InstallPrompt only calls it from
  // isStandalone(), so a minimal stub is enough.
  if (!window.matchMedia) {
    window.matchMedia = ((query: string) => ({
      matches: false,
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {},
    })) as unknown as typeof window.matchMedia;
  }
});

afterEach(() => {
  // Sonner's store outlives the unmounted <Toaster>, so a toast fired by
  // one test would otherwise be on screen for the next one.
  toast.dismiss();
  cleanup();
  localStorage.clear();
});

describe("InstallPrompt", () => {
  it("renders no inline markup of its own", () => {
    const { container } = renderWithToaster();
    expect(container.querySelector(".pwa-toast")).toBeNull();
  });

  it("fires a toast with a keyboard-reachable Install action on beforeinstallprompt", async () => {
    const { container } = renderWithToaster();
    fireBeforeInstallPrompt();

    await waitFor(() => {
      expect(screen.getByText("Install for one-tap access.")).toBeTruthy();
    });
    // Sonner renders actions as real <button>s, so this stays tab-reachable.
    expect(screen.getByRole("button", { name: "Install" })).toBeTruthy();

    // The load-bearing assertion. Once the component actually has something to
    // show, it still must not put it in the page flow: no fixed panel of its
    // own, and the message lives inside the shared toaster rather than in the
    // component's own markup. Both fail against the pre-sonner version.
    expect(container.querySelector(".pwa-toast")).toBeNull();
    const toaster = document.querySelector("[data-sonner-toaster]");
    expect(toaster).not.toBeNull();
    expect(toaster?.textContent).toContain("Install for one-tap access.");
  });

  it("stays quiet inside the 7-day cooldown after an explicit dismissal", async () => {
    localStorage.setItem(STORAGE_KEY, String(Date.now()));
    renderWithToaster();
    fireBeforeInstallPrompt();

    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(screen.queryByText("Install for one-tap access.")).toBeNull();
  });

  it("offers the toast again once the cooldown has expired", async () => {
    const sevenDays = 7 * 24 * 60 * 60 * 1000;
    localStorage.setItem(STORAGE_KEY, String(Date.now() - sevenDays - 1000));
    renderWithToaster();
    fireBeforeInstallPrompt();

    await waitFor(() => {
      expect(screen.getByText("Install for one-tap access.")).toBeTruthy();
    });
  });
});