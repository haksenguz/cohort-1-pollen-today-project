/**
 * ChatScreen smoke test.
 *
 * This exists because the screen once rendered a completely blank page and
 * every other check missed it: the module served 200, tsc passed, the
 * backend SSE contract was verified end to end, and 58 unit tests were
 * green. Nothing actually mounted the component. A misplaced
 * ErrorPrimitive.Message threw during render, React unmounted the tree,
 * and /chat, the default route, was white.
 *
 * So: render it and assert something is on screen. Cheap insurance against
 * exactly this class of failure.
 *
 * The triage cases drive a whole turn through the mocked adapter, because the
 * verdict has to survive the whole path (adapter -> data part -> assistant-ui
 * thread -> render) and a component test with a hand-built message would not
 * prove any of it.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return { ...actual, streamChat: vi.fn() };
});

import { streamChat } from "../api/client";
import type { ChatResponse, TriageLevel } from "../api/types";
import { ChatScreen } from "./ChatScreen";
import { resetConversation } from "./allergyChatAdapter";

function doneEvent(
  level: TriageLevel | null,
  reasons: string[] = [],
): ChatResponse {
  return {
    message: "I can help.",
    conversation_id: 7,
    symptoms: [],
    severity: null,
    duration: null,
    possible_trigger: null,
    breathing_difficulty: null,
    airway_swelling: null,
    triage_level: level,
    triage_reasons: reasons,
    triage_rule_version: "1",
  };
}

function mockTurn(response: ChatResponse | null) {
  vi.mocked(streamChat).mockImplementation(async (_msg, _id, handlers) => {
    handlers.onMessage?.("I can help.");
    if (response) handlers.onDone?.(response);
  });
}

async function sendATurn(text = "my eyes are itchy") {
  const user = userEvent.setup();
  await user.type(
    screen.getByPlaceholderText("Describe how you feel, in any language"),
    text,
  );
  await user.click(screen.getByRole("button", { name: "Send message" }));
}

function renderScreen() {
  render(
    <MemoryRouter>
      <ChatScreen />
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
  resetConversation();
});

describe("ChatScreen", () => {
  it("mounts and shows the empty state, the composer and the disclaimer", async () => {
    mockTurn(doneEvent(null));
    renderScreen();

    expect(await screen.findByText("Tell me how you feel")).toBeTruthy();
    expect(
      screen.getByPlaceholderText("Describe how you feel, in any language"),
    ).toBeTruthy();
    expect(screen.getByText(/Not a diagnosis/)).toBeTruthy();
  });

  it("shows an emergency banner with a one-tap call to 119", async () => {
    mockTurn(doneEvent("EMERGENCY", ["airway_swelling"]));
    renderScreen();

    await sendATurn("my throat is closing up");

    const banner = await screen.findByText("Get medical help now");
    expect(banner).toBeTruthy();
    expect(screen.getByRole("link", { name: /Call the emergency number 119/ })).toHaveAttribute(
      "href",
      "tel:119",
    );
  });

  it("lists the triage reasons behind the verdict", async () => {
    mockTurn(doneEvent("MODERATE", ["severity_5", "symptoms_persist"]));
    renderScreen();

    await sendATurn();

    expect(await screen.findByText("severity_5")).toBeTruthy();
    expect(screen.getByText("symptoms_persist")).toBeTruthy();
    expect(screen.getByText("Why this level")).toBeTruthy();
  });

  it("renders a low verdict calmly and never as an emergency banner", async () => {
    mockTurn(doneEvent("LOW"));
    renderScreen();

    await sendATurn();

    expect(await screen.findByText("Safety check: low")).toBeTruthy();
    expect(screen.queryByText("Get medical help now")).toBeNull();
    expect(screen.queryByRole("link", { name: /Call the emergency number/ })).toBeNull();
  });

  it("renders no verdict at all when the backend sent none", async () => {
    // A missing verdict must not read as LOW. The LOW card is an explicit
    // statement, so with no card on screen nothing claims the user is fine.
    mockTurn(doneEvent(null));
    renderScreen();

    await sendATurn();

    await screen.findByText("I can help.");
    await waitFor(() => {
      expect(screen.queryByText("Safety check: low")).toBeNull();
    });
    expect(screen.queryByText("Get medical help now")).toBeNull();
    expect(screen.queryByText("Safety check could not be read")).toBeNull();
  });

  it("shows an unreadable verdict as unchecked rather than as low", async () => {
    mockTurn({
      ...doneEvent("LOW"),
      triage_level: "CRITICAL" as TriageLevel,
    });
    renderScreen();

    await sendATurn();

    expect(await screen.findByText("Safety check could not be read")).toBeTruthy();
    expect(screen.queryByText("Safety check: low")).toBeNull();
    expect(screen.queryByRole("link", { name: /Call the emergency number/ })).toBeNull();
  });

  it("routes an emergency verdict to nearby care and lands on Today", async () => {
    mockTurn(doneEvent("EMERGENCY", ["airway_swelling"]));
    render(
      <MemoryRouter initialEntries={["/chat"]}>
        <Routes>
          <Route path="/chat" element={<ChatScreen />} />
          <Route path="/today" element={<p>Today care screen</p>} />
        </Routes>
      </MemoryRouter>,
    );

    await sendATurn();
    await userEvent.click(
      await screen.findByRole("button", { name: /Find a clinic near you/ }),
    );

    expect(await screen.findByText("Today care screen")).toBeTruthy();
  });

  it("offers nearby care on a moderate verdict but never on a low one", async () => {
    mockTurn(doneEvent("MODERATE", ["severity_5"]));
    renderScreen();

    await sendATurn();

    expect(await screen.findByText("Safety check: moderate")).toBeTruthy();
    expect(screen.getByRole("button", { name: /Find a clinic near you/ })).toBeTruthy();
  });

  it("does not offer nearby care on a low verdict", async () => {
    mockTurn(doneEvent("LOW"));
    renderScreen();

    await sendATurn();

    expect(await screen.findByText("Safety check: low")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Find a clinic near you/ })).toBeNull();
  });
});