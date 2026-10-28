/**
 * Conversation history drawer tests.
 *
 * Covers the four things a history list gets wrong: it hides a real title, it
 * shows a raw timestamp, it shows no preview, and it shows "failed to load"
 * in the same empty panel as "you have none". All four are asserted here
 * because all four are the reason the feature was missing.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";

import type { ConversationSummary } from "../api/types";

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return { ...actual, listConversations: vi.fn() };
});

import { ApiError, listConversations } from "../api/client";
import { ChatHistorySheet } from "./ChatHistorySheet";

const NOW = new Date("2026-10-16T08:14:31Z");

const conversation = (overrides: Partial<ConversationSummary> = {}): ConversationSummary => ({
  id: 42,
  title: "chest tightness after running",
  created_at: "2026-10-16T06:12:00Z",
  updated_at: "2026-10-16T06:14:31Z",
  last_message: "it started about 10 minutes ago",
  message_count: 6,
  ...overrides,
});

function LocationProbe() {
  const location = useLocation();
  return <span data-testid="location">{`${location.pathname}`}</span>;
}

const renderSheet = (initialEntry = "/chat") =>
  render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <LocationProbe />
      <Routes>
        <Route path="/chat" element={<ChatHistorySheet activeId={42} />} />
        <Route path="/chat/:conversationId" element={<ChatHistorySheet />} />
      </Routes>
    </MemoryRouter>,
  );

const openHistory = async () => {
  fireEvent.click(screen.getByRole("button", { name: /history/i }));
  return waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());
};

beforeEach(() => {
  // Only Date, so waitFor keeps working on real timers.
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(NOW);
  vi.mocked(listConversations).mockResolvedValue([]);
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("ChatHistorySheet", () => {
  it("does not call the list endpoint until the sheet is opened", async () => {
    renderSheet();
    expect(listConversations).not.toHaveBeenCalled();
  });

  it("shows a loading state before the list arrives", async () => {
    vi.mocked(listConversations).mockReturnValue(new Promise(() => {}));
    renderSheet();
    fireEvent.click(screen.getByRole("button", { name: /history/i }));

    expect(await screen.findByText(/loading conversations/i)).toBeInTheDocument();
  });

  it("renders the title, the relative timestamp and the last-message preview", async () => {
    vi.mocked(listConversations).mockResolvedValue([conversation()]);
    renderSheet();
    await openHistory();

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("chest tightness after running")).toBeInTheDocument();
    expect(within(dialog).getByText("2 h ago")).toBeInTheDocument();
    expect(within(dialog).getByText("it started about 10 minutes ago")).toBeInTheDocument();
  });

  it("falls back to a readable label when the title has not been generated yet", async () => {
    vi.mocked(listConversations).mockResolvedValue([conversation({ title: null })]);
    renderSheet();
    await openHistory();

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Untitled conversation")).toBeInTheDocument();
    expect(within(dialog).queryByText("chest tightness after running")).not.toBeInTheDocument();
  });

  it("treats a blank title as no title", async () => {
    vi.mocked(listConversations).mockResolvedValue([conversation({ title: "   " })]);
    renderSheet();
    await openHistory();

    expect(await screen.findByText("Untitled conversation")).toBeInTheDocument();
  });

  it("omits the preview line when the conversation has no messages yet", async () => {
    vi.mocked(listConversations).mockResolvedValue([
      conversation({ title: "first session", last_message: null, message_count: 0 }),
    ]);
    renderSheet();
    await openHistory();

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("first session")).toBeInTheDocument();
    expect(within(dialog).queryByText("it started about 10 minutes ago")).not.toBeInTheDocument();
  });

  it("distinguishes an empty history from a failed load", async () => {
    vi.mocked(listConversations).mockResolvedValue([]);
    renderSheet();
    await openHistory();

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/no conversations yet/i)).toBeInTheDocument();
    expect(within(dialog).queryByText(/could not load/i)).not.toBeInTheDocument();
  });

  it("shows a retryable error instead of an empty list when the endpoint fails", async () => {
    vi.mocked(listConversations).mockRejectedValue(new ApiError(500, "Conversations offline"));
    renderSheet();
    await openHistory();

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/could not load your conversations/i)).toBeInTheDocument();
    expect(within(dialog).getByText("Conversations offline")).toBeInTheDocument();
    // The failure must never read as "you have no conversations".
    expect(within(dialog).queryByText(/no conversations yet/i)).not.toBeInTheDocument();
  });

  it("refetches when the retry button is pressed", async () => {
    vi.mocked(listConversations).mockRejectedValueOnce(new ApiError(500, "Conversations offline"));
    renderSheet();
    await openHistory();

    fireEvent.click(await screen.findByRole("button", { name: /try again/i }));

    await waitFor(() => expect(listConversations).toHaveBeenCalledTimes(2));
    expect(await screen.findByText(/no conversations yet/i)).toBeInTheDocument();
  });

  it("navigates to /chat when a conversation row is chosen", async () => {
    vi.mocked(listConversations).mockResolvedValue([conversation()]);
    renderSheet();
    await openHistory();

    fireEvent.click(await screen.findByRole("link", { name: /chest tightness after running/i }));

    expect(screen.getByTestId("location")).toHaveTextContent("/chat/42");
  });

  it("leaves the open conversation and lands on /chat from the sheet's New chat control", async () => {
    vi.mocked(listConversations).mockResolvedValue([conversation()]);
    renderSheet("/chat/42");
    await openHistory();

    // Scoped to the dialog: Radix marks everything outside it aria-hidden while
    // it is open, so the trigger bar's own New chat button is not exposed.
    const dialog = screen.getByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: /new chat/i }));

    expect(screen.getByTestId("location")).toHaveTextContent("/chat");
  });

  it("dismisses the sheet on Escape", async () => {
    vi.mocked(listConversations).mockResolvedValue([conversation()]);
    renderSheet();
    await openHistory();

    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });
});

describe("searching conversations", () => {
  const typeSearch = async (text: string) => {
    fireEvent.change(screen.getByLabelText("Search conversations"), {
      target: { value: text },
    });
  };

  it("searches titles and message content through the list endpoint", async () => {
    vi.mocked(listConversations).mockResolvedValue([conversation()]);
    renderSheet();
    await openHistory();
    await screen.findByText("chest tightness after running");

    await typeSearch("pollen");

    await waitFor(() => {
      expect(listConversations).toHaveBeenLastCalledWith("pollen");
    });
  });

  it("asks for no filter when the search is empty", async () => {
    vi.mocked(listConversations).mockResolvedValue([conversation()]);
    renderSheet();
    await openHistory();
    await screen.findByText("chest tightness after running");

    await typeSearch("pollen");
    await waitFor(() => {
      expect(listConversations).toHaveBeenLastCalledWith("pollen");
    });

    await typeSearch("");
    await waitFor(() => {
      expect(listConversations).toHaveBeenLastCalledWith(undefined);
    });
  });

  it("shows the matches that came back", async () => {
    vi.mocked(listConversations).mockResolvedValue([conversation()]);
    renderSheet();
    await openHistory();
    await screen.findByText("chest tightness after running");

    vi.mocked(listConversations).mockResolvedValue([
      conversation({ id: 7, title: "pollen season" }),
    ]);
    await typeSearch("pollen");

    expect(await screen.findByText("pollen season")).toBeInTheDocument();
    expect(screen.queryByText("chest tightness after running")).not.toBeInTheDocument();
  });

  it("says a search matched nothing without saying the history is empty", async () => {
    vi.mocked(listConversations).mockResolvedValue([conversation()]);
    renderSheet();
    await openHistory();
    await screen.findByText("chest tightness after running");

    vi.mocked(listConversations).mockResolvedValue([]);
    await typeSearch("zzz");

    const dialog = screen.getByRole("dialog");
    expect(await within(dialog).findByText(/no conversations match/i)).toBeInTheDocument();
    expect(within(dialog).queryByText(/no conversations yet/i)).not.toBeInTheDocument();
  });

  it("keeps a failed search apart from a search that matched nothing", async () => {
    vi.mocked(listConversations).mockResolvedValue([conversation()]);
    renderSheet();
    await openHistory();
    await screen.findByText("chest tightness after running");

    vi.mocked(listConversations).mockRejectedValue(new ApiError(500, "Search offline"));
    await typeSearch("pollen");

    const dialog = screen.getByRole("dialog");
    expect(
      await within(dialog).findByText(/could not load your conversations/i),
    ).toBeInTheDocument();
    expect(within(dialog).queryByText(/no conversations match/i)).not.toBeInTheDocument();
    expect(within(dialog).queryByText(/no conversations yet/i)).not.toBeInTheDocument();
  });
});