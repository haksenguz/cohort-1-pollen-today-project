/**
 * The controls the chat screen gained: copy, regenerate, timestamps, jump to
 * latest and the offline state (bugs.md C3, C4, C5, C7, C10).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { toast } from "sonner";

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return {
    ...actual,
    streamChat: vi.fn(),
    getConversation: vi.fn(),
    listConversations: vi.fn(),
  };
});

import { getConversation, listConversations, streamChat } from "../api/client";
import type { ChatResponse, ConversationDetail } from "../api/types";
import { Toaster } from "../components/ui/sonner";
import { ChatScreen } from "./ChatScreen";
import { resetActivity } from "./activity";
import { resetConversation } from "./allergyChatAdapter";

function doneEvent(): ChatResponse {
  return {
    message: "I can help.",
    conversation_id: 7,
    symptoms: [],
    severity: null,
    duration: null,
    possible_trigger: null,
    breathing_difficulty: null,
    airway_swelling: null,
    triage_level: null,
    triage_reasons: [],
    triage_rule_version: "1",
  };
}

function mockTurn(reply = "I can help.") {
  vi.mocked(streamChat).mockImplementation(async (_msg, _id, handlers) => {
    handlers.onMessage?.(reply);
    handlers.onDone?.(doneEvent());
  });
}

/** A turn that stays open until the returned callback fires. */
function mockHeldTurn(reply = "I can help.") {
  let open = () => {};
  const held = new Promise<void>((resolve) => {
    open = resolve;
  });
  vi.mocked(streamChat).mockImplementation(async (_msg, _id, handlers) => {
    await held;
    handlers.onMessage?.(reply);
    handlers.onDone?.(doneEvent());
  });
  return async () => {
    await act(async () => {
      open();
    });
  };
}

function renderScreen(path = "/chat") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Toaster />
      <Routes>
        <Route path="/chat" element={<ChatScreen />} />
        <Route path="/chat/:conversationId" element={<ChatScreen />} />
      </Routes>
    </MemoryRouter>,
  );
}

async function sendATurn(text = "my eyes are itchy") {
  const user = userEvent.setup();
  await user.type(
    screen.getByPlaceholderText("Describe how you feel, in any language"),
    text,
  );
  await user.click(screen.getByRole("button", { name: "Send message" }));
}

function setClipboard(value: unknown) {
  Object.defineProperty(navigator, "clipboard", { value, configurable: true });
}

function setOnline(online: boolean) {
  Object.defineProperty(navigator, "onLine", { value: online, configurable: true });
}

beforeEach(() => {
  // sonner keeps its toasts in a module level store, so a toast from the
  // previous test would still be on screen.
  toast.dismiss();
  vi.mocked(listConversations).mockResolvedValue([]);
  vi.mocked(getConversation).mockRejectedValue(new Error("not used"));
  setOnline(true);
  setClipboard({ writeText: vi.fn().mockResolvedValue(undefined) });
});

afterEach(() => {
  vi.restoreAllMocks();
  resetActivity();
  resetConversation();
  setOnline(true);
});

describe("copy a reply", () => {
  it("writes the reply text and confirms it", async () => {
    mockTurn("Your eyes look irritated.");
    renderScreen();

    await sendATurn();
    await screen.findByText("Your eyes look irritated.");

    // user-event installs its own clipboard stub, so the mock has to go in
    // after the last setup() call.
    const writeText = vi.fn().mockResolvedValue(undefined);
    setClipboard({ writeText });

    fireEvent.click(screen.getByRole("button", { name: "Copy reply" }));

    expect(writeText).toHaveBeenCalledWith("Your eyes look irritated.");
    expect(await screen.findByText("Reply copied.")).toBeTruthy();
  });

  it("says the copy failed when the browser refuses", async () => {
    mockTurn("Your eyes look irritated.");
    renderScreen();

    await sendATurn();
    await screen.findByText("Your eyes look irritated.");

    setClipboard({ writeText: vi.fn().mockRejectedValue(new Error("denied")) });

    fireEvent.click(screen.getByRole("button", { name: "Copy reply" }));

    expect(await screen.findByText("Copy failed.")).toBeTruthy();
    expect(screen.queryByText("Reply copied.")).toBeNull();
  });

  it("says the copy failed when there is no clipboard API at all", async () => {
    mockTurn("Your eyes look irritated.");
    renderScreen();

    await sendATurn();
    await screen.findByText("Your eyes look irritated.");

    setClipboard(undefined);

    fireEvent.click(screen.getByRole("button", { name: "Copy reply" }));

    expect(await screen.findByText("Copy failed.")).toBeTruthy();
  });
});

describe("regenerate the last reply", () => {
  it("offers the control on the last reply and re-runs the turn", async () => {
    mockTurn("First answer.");
    renderScreen();

    await sendATurn();
    await screen.findByText("First answer.");

    mockTurn("Second answer.");
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Regenerate the last reply" }));

    await waitFor(() => {
      expect(vi.mocked(streamChat).mock.calls.length).toBe(2);
    });
    const options = vi.mocked(streamChat).mock.calls[1][4];
    expect(options).toEqual({ regenerate: true });

    await screen.findByText("Second answer.");
    expect(screen.queryByText("First answer.")).toBeNull();
  });

  it("is disabled while a turn is in flight", async () => {
    mockTurn("First answer.");
    renderScreen();

    await sendATurn();
    await screen.findByText("First answer.");

    const release = mockHeldTurn("Second answer.");
    const user = userEvent.setup();
    await user.type(
      screen.getByPlaceholderText("Describe how you feel, in any language"),
      "and my nose runs",
    );
    await user.click(screen.getByRole("button", { name: "Send message" }));

    const control = await screen.findByRole("button", {
      name: "Regenerate the last reply",
    });
    expect((control as HTMLButtonElement).disabled).toBe(true);

    await release();
  });
});

describe("timestamps", () => {
  it("shows no time on a message that was just sent", async () => {
    mockTurn("Fresh answer.");
    renderScreen();

    await sendATurn();
    await screen.findByText("Fresh answer.");

    expect(document.querySelector("time")).toBeNull();
  });

  it("shows the time a stored message was sent", async () => {
    const conversation: ConversationDetail = {
      id: 5,
      title: "Pollen",
      created_at: "2026-10-20T09:30:00Z",
      messages: [
        {
          id: 1,
          role: "user",
          content: "my eyes are itchy",
          triage_level: null,
          triage_reasons: [],
          created_at: "2026-10-20T09:30:00Z",
        },
        {
          id: 2,
          role: "assistant",
          content: "Your eyes look irritated.",
          triage_level: null,
          triage_reasons: [],
          created_at: "2026-10-20T09:30:00Z",
        },
      ],
    };
    vi.mocked(getConversation).mockResolvedValue(conversation);
    renderScreen("/chat/5");

    await screen.findByText("Your eyes look irritated.");
    const times = document.querySelectorAll("time");
    // Both the question and the answer carry the time the server recorded.
    expect(times).toHaveLength(2);
    expect(times[0].getAttribute("datetime")).toBe("2026-10-20T09:30:00Z");
    expect(times[0].textContent?.trim()).not.toBe("");
  });
});

describe("jump to latest", () => {
  /** Makes the viewport look scrolled up, then fires the scroll event. */
  function scrollUp(viewport: HTMLElement) {
    Object.defineProperty(viewport, "scrollHeight", {
      value: 1000,
      configurable: true,
    });
    Object.defineProperty(viewport, "clientHeight", {
      value: 400,
      configurable: true,
    });
    Object.defineProperty(viewport, "scrollTop", {
      value: 0,
      writable: true,
      configurable: true,
    });
    // The user was at the bottom and scrolled up. Both positions are fired,
    // because the library reads the direction from the previous position.
    viewport.scrollTop = 600;
    fireEvent.scroll(viewport);
    viewport.scrollTop = 0;
    fireEvent.scroll(viewport);
  }

  it("is offered once the user scrolls up and takes them back to the bottom", async () => {
    mockTurn();
    const { container } = renderScreen();

    await sendATurn();
    await screen.findByText("I can help.");

    const viewport = container.querySelector(".aui-viewport") as HTMLElement;
    expect(viewport).toBeTruthy();

    // At the bottom there is nowhere to jump to, so the control is off.
    const control = screen.getByRole("button", { name: "Jump to latest message" });
    expect((control as HTMLButtonElement).disabled).toBe(true);

    scrollUp(viewport);

    await waitFor(() => {
      expect(
        (screen.getByRole("button", { name: "Jump to latest message" }) as HTMLButtonElement)
          .disabled,
      ).toBe(false);
    });

    const scrollTo = vi.fn((options: { top: number }) => {
      Object.defineProperty(viewport, "scrollTop", {
        value: options.top - 400,
        writable: true,
        configurable: true,
      });
      fireEvent.scroll(viewport);
    });
    Object.defineProperty(viewport, "scrollTo", { value: scrollTo, configurable: true });

    fireEvent.click(screen.getByRole("button", { name: "Jump to latest message" }));

    expect(scrollTo).toHaveBeenCalled();
    // Back at the bottom, so the control goes away again.
    await waitFor(() => {
      expect(
        (screen.getByRole("button", { name: "Jump to latest message" }) as HTMLButtonElement)
          .disabled,
      ).toBe(true);
    });
  });
});

describe("offline", () => {
  it("says so and refuses to send", async () => {
    setOnline(false);
    mockTurn();
    renderScreen();

    expect(await screen.findByText(/You are offline/)).toBeTruthy();

    const user = userEvent.setup();
    await user.type(
      screen.getByPlaceholderText("Describe how you feel, in any language"),
      "my eyes are itchy",
    );
    await user.click(screen.getByRole("button", { name: "Send message" }));

    // Nothing was sent, so nothing was added to the thread either.
    expect(vi.mocked(streamChat)).not.toHaveBeenCalled();
    expect(document.querySelector(".aui-msg")).toBeNull();
  });

  it("disables the send button while offline", async () => {
    setOnline(false);
    mockTurn();
    renderScreen();

    const send = await screen.findByRole("button", { name: "Send message" });
    expect((send as HTMLButtonElement).disabled).toBe(true);
  });

  it("comes back when the device reconnects", async () => {
    setOnline(false);
    mockTurn();
    renderScreen();

    expect(await screen.findByText(/You are offline/)).toBeTruthy();

    await act(async () => {
      setOnline(true);
      window.dispatchEvent(new Event("online"));
    });

    await waitFor(() => {
      expect(screen.queryByText(/You are offline/)).toBeNull();
    });
  });
});

describe("markdown in the chat", () => {
  it("renders the model's markdown as HTML", async () => {
    mockTurn("Take **antihistamine** now.");
    const { container } = renderScreen();

    await sendATurn();

    await waitFor(() => {
      expect(container.querySelector("strong")?.textContent).toBe("antihistamine");
    });
  });
});