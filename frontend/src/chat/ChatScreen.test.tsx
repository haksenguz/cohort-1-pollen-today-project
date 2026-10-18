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
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return { ...actual, streamChat: vi.fn() };
});

import { streamChat } from "../api/client";
import type { ChatResponse, TriageLevel, ToolCallEvent } from "../api/types";
import { ChatScreen } from "./ChatScreen";
import { resetActivity } from "./activity";
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

function mockToolTurn(events: ToolCallEvent[]) {
  vi.mocked(streamChat).mockImplementation(async (_msg, _id, handlers) => {
    for (const event of events) handlers.onTool?.(event);
    handlers.onMessage?.("I can help.");
    handlers.onDone?.(doneEvent(null));
  });
}

/**
 * Same turn, but held open until the returned callback fires. A `running` tool
 * row is on screen for as long as the stream is open, so asserting on one needs
 * a stream that has not finished yet. `before` lands immediately, `after` once
 * the gate opens.
 */
function mockHeldTurn(before: ToolCallEvent[], after: ToolCallEvent[] = []) {
  let open = () => {};
  const held = new Promise<void>((resolve) => {
    open = resolve;
  });
  vi.mocked(streamChat).mockImplementation(async (_msg, _id, handlers) => {
    for (const event of before) handlers.onTool?.(event);
    await held;
    for (const event of after) handlers.onTool?.(event);
    handlers.onMessage?.("I can help.");
    handlers.onDone?.(doneEvent(null));
  });
  return async () => {
    await act(async () => {
      open();
    });
  };
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
  resetActivity();
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

  // The four cases below drive tool events through the real adapter, so they
  // only pass once `allergyChatAdapter` forwards `onTool` to `setToolActivity`.
  // Until that line lands the store never hears about a tool and all four fail
  // on a missing row, which is the failure to expect, not a broken store.

  it("says what a running tool call is doing, in plain English", async () => {
    const finish = mockHeldTurn([
      {
        id: "call_1",
        name: "find_nearby_care",
        status: "running",
        args: { radius_m: 3000 },
      },
    ]);
    renderScreen();

    await sendATurn();

    expect(await screen.findByText("Looking for clinics near you…")).toBeTruthy();
    // Neither the identifier nor the argument payload belongs on the screen,
    // in any state.
    expect(document.body.innerHTML).not.toContain("find_nearby_care");
    expect(document.body.innerHTML).not.toContain("radius_m");

    await finish();
  });

  it("replaces the running row with what the finished call found", async () => {
    mockToolTurn([
      { id: "call_1", name: "find_nearby_care", status: "running" },
      {
        id: "call_1",
        name: "find_nearby_care",
        status: "done",
        summary: "3 clinics found",
      },
    ]);
    renderScreen();

    await sendATurn();

    // The summary outlives the turn: the answer is the reason the call ran.
    expect(await screen.findByText("3 clinics found")).toBeTruthy();
    expect(screen.queryByText("Looking for clinics near you…")).toBeNull();
  });

  it("shows a failed tool call as a failure, never as a result and never as silence", async () => {
    mockToolTurn([
      { id: "call_2", name: "find_nearby_care", status: "running" },
      {
        id: "call_2",
        name: "find_nearby_care",
        status: "error",
        summary: "Provider unavailable",
      },
    ]);
    renderScreen();

    await sendATurn();

    expect(await screen.findByText("Could not look up clinics near you.")).toBeTruthy();
    // Stated twice on purpose: the activity strip is the polite live region,
    // the tool card is the assertive one. Same failure, two weights.
    expect(screen.getAllByText(/Provider unavailable/).length).toBeGreaterThan(0);
    expect(document.querySelector('[data-state="error"]')).toBeTruthy();
    // No done row anywhere: a failure that renders like a success is a lie.
    expect(document.querySelector('[data-state="done"]')).toBeNull();
  });

  it("says something honest about a tool it has no sentence for", async () => {
    const finish = mockHeldTurn(
      [
        {
          id: "call_9",
          name: "query_pharmacy_stock_v2",
          status: "running",
          args: { latitude: 37.5 },
        },
      ],
      [
        {
          id: "call_9",
          name: "query_pharmacy_stock_v2",
          status: "done",
          summary: "2 pharmacies found",
        },
      ],
    );
    renderScreen();

    await sendATurn();

    // Unknown tools degrade rather than leaking. An identifier on screen is a
    // worse answer than an honest one line, because it tells the user nothing.
    expect(await screen.findByText("Checking something…")).toBeTruthy();
    expect(document.body.innerHTML).not.toContain("query_pharmacy_stock_v2");

    await finish();

    expect(await screen.findByText("2 pharmacies found")).toBeTruthy();
    expect(document.body.innerHTML).not.toContain("query_pharmacy_stock_v2");
    // No clinic card: it would claim the call was a clinic search that could
    // not be read, directly under a strip that just said it was not one.
    expect(document.querySelector("[data-slot='tool-result']")).toBeNull();
  });

  it("gives a clinic lookup a card the strip's row cannot contradict", async () => {
    mockToolTurn([
      { id: "call_3", name: "find_nearby_hospitals", status: "running" },
      // Done, but the backend sent no result payload at all.
      { id: "call_3", name: "find_nearby_hospitals", status: "done", summary: "Finished." },
    ]);
    renderScreen();

    await sendATurn();

    expect(await screen.findByText("Finished.")).toBeTruthy();
    const card = document.querySelector("[data-slot='tool-result']");
    expect(card).toHaveAttribute("data-state", "unreadable");
    // The card must not say the search found nothing. Nothing was searched.
    expect(card?.textContent).not.toContain("No clinics found");
  });

  /**
   * Wire conformance against payloads CAPTURED FROM THE REAL BACKEND.
   *
   * The rest of this file drives `onTool` with hand-written events, which proves
   * the component works against events I imagined. These are the literal
   * payloads the backend emitted for a live turn against the real provider on
   * 2026-10-18, one account, saved location then location cleared. If the two
   * sides ever drift apart, this is where it shows up.
   */
  describe("captured backend payloads", () => {
    it("renders the clinics from a real find_nearby_care call", async () => {
      mockToolTurn([
        {
          id: "call_1",
          name: "find_nearby_care",
          status: "done",
          summary: "Found 2 results.",
          result: {
            clinics: [
              { name: "Severance Sinchon Severance Hospital", address: "Eoulmukro 59", distance_m: 1240, phone: "02-737-5432", rank: 1 },
              { name: "Dawell Internal Medicine Mapo", address: "Worldcup-ro 242", distance_m: 3410, phone: null, rank: 2 },
            ],
          },
        },
      ]);
      renderScreen();

      await sendATurn("my eyes are itchy and I keep sneezing - which hospital should I go to?");

      expect(await screen.findByText("Severance Sinchon Severance Hospital")).toBeTruthy();
      expect(screen.getByText("Dawell Internal Medicine Mapo")).toBeTruthy();
      expect(screen.getByText("2 found")).toBeTruthy();
      expect(document.querySelector("[data-slot='tool-result']")).toHaveAttribute(
        "data-state",
        "results",
      );
      // The real phone number is a tap target, not a 12px line of text. Only
      // whitespace is stripped for the URI; the hyphens are part of the number.
      expect(screen.getByRole("link", { name: /02-737-5432/ })).toHaveAttribute(
        "href",
        "tel:02-737-5432",
      );
    });

    it("renders no_location as the fixable state, never as no clinics found", async () => {
      mockToolTurn([
        {
          id: "call_1",
          name: "find_nearby_care",
          status: "error",
          code: "no_location",
          summary:
            "We need your location first. Your profile has no location saved, so we could not search. This does not mean there are no clinics around you.",
          result: null,
        },
      ]);
      renderScreen();

      await sendATurn();

      expect(await screen.findByText("We need your location first")).toBeTruthy();
      const card = document.querySelector("[data-slot='tool-result']");
      expect(card).toHaveAttribute("data-state", "no_location");
      expect(card?.textContent).not.toContain("No clinics found");
      expect(card?.textContent).not.toContain("Search failed");
      expect(screen.getByRole("button", { name: "Set your location" })).toBeTruthy();
    });

    it("keeps an empty clinic array as an empty result, not as unknown", async () => {
      mockToolTurn([
        {
          id: "call_1",
          name: "find_nearby_care",
          status: "done",
          summary: "No results found.",
          result: { clinics: [], provider_available: true },
        },
      ]);
      renderScreen();

      await sendATurn();

      expect(await screen.findByText("No clinics found")).toBeTruthy();
      expect(document.querySelector("[data-slot='tool-result']")).toHaveAttribute(
        "data-state",
        "empty",
      );
    });
  });
});