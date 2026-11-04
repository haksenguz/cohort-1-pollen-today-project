/**
 * AppShell tests (B-031).
 *
 * The shell is the app frame: the header, the scrolling stage, and the tab
 * nav. The nav has to be a sibling of the scrolling stage, not inside it, or
 * it scrolls away with the content. The height rules are asserted against
 * theme.css, because a DOM cannot say whether a box is capped.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { AppShell } from "./AppShell";

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

vi.mock("../hooks/useAlertPolling", () => ({
  useAlertPolling: vi.fn(),
}));

// The consent gate is a screen of its own and it reads a context that is
// mounted above the shell in the real app. The shell's own layout is what
// this file is about, so the gate is stubbed out.
vi.mock("./ConsentGate", () => ({
  ConsentGate: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return { ...actual, getCurrentEnvironment: vi.fn().mockResolvedValue(null) };
});

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({
    user: null,
    status: "authenticated",
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    updateUser: vi.fn(),
    retry: vi.fn(),
  }),
}));

const renderShell = (path = "/today") =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/today" element={<p>the today screen</p>} />
          <Route path="/chat" element={<p>the chat screen</p>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );

afterEach(() => {
  vi.restoreAllMocks();
});

describe("AppShell — the nav is not inside the scrolling stage", () => {
  it("keeps the nav a sibling of the stage, after it", () => {
    const { container } = renderShell();

    const shell = container.querySelector(".app-shell");
    expect(shell).not.toBeNull();

    const stage = shell?.querySelector(".stage");
    const nav = shell?.querySelector("nav");
    // The guard is the null check. The assertions below cannot run without
    // both elements.
    if (!stage || !nav) throw new Error("the shell has no stage or no nav");

    // Same parent, so the nav is a row of the shell and not a child of the
    // thing that scrolls.
    expect(nav.parentElement).toBe(stage.parentElement);
    // After the stage in the markup, so it sits at the bottom of the frame.
    expect(
      stage.compareDocumentPosition(nav) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("renders the stage content inside the stage, not in the nav", () => {
    renderShell();

    expect(screen.getByText("the today screen")).toBeInTheDocument();
    expect(screen.getByRole("navigation")).toBeInTheDocument();
  });
});

describe("AppShell — the shell has a definite height", () => {
  it("caps the shell instead of letting it grow with its content", () => {
    // A min-height lets the shell grow, so the stage never gets a height to
    // scroll inside and the document scrolls instead, taking the nav with it.
    const shell = rule(".app-shell");
    expect(shell).toContain("height: 100vh");
    expect(shell).not.toMatch(/^\s*min-height:/m);
  });

  it("lets the stage shrink so it can scroll inside the shell", () => {
    const stage = rule(".stage");
    expect(stage).toContain("flex: 1");
    expect(stage).toContain("min-height: 0");
    expect(stage).toContain("overflow-y: auto");
  });

  it("keeps the desktop phone frame with its rounded corners and border", () => {
    const frame = themeCss.slice(
      themeCss.indexOf("@media (min-width: 461px)"),
      themeCss.indexOf("}", themeCss.indexOf("@media (min-width: 461px)")),
    );
    expect(frame).toContain("border-radius: 34px");
    expect(frame).toContain("border: 1px solid var(--line)");
    expect(frame).toContain("height:");
  });

  it("keeps the iOS safe-area padding on the shell", () => {
    const shell = rule(".app-shell");
    expect(shell).toContain("padding-top: env(safe-area-inset-top)");
    expect(shell).toContain("padding-bottom: env(safe-area-inset-bottom)");
  });

  it("never pins the nav with position: fixed", () => {
    // The nav is a flex row of the shell. Fixed positioning would take it out
    // of the frame and break the desktop phone frame.
    const nav = rule(".nav");
    expect(nav).not.toContain("position: fixed");
  });
});

describe("AppShell — the chat keeps its own scroll region", () => {
  it("gives the chat stage its own layout so the composer stays above the nav", () => {
    renderShell("/chat");

    const stage = document.querySelector(".stage");
    expect(stage?.classList.contains("stage-chat")).toBe(true);
  });
});
