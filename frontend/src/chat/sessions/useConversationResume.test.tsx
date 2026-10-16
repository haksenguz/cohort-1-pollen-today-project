/**
 * Resume-path UI and remount-key tests.
 *
 * The remount key is the part that is easy to get subtly wrong: a wrong key
 * silently serves the previous conversation's messages, which looks like the
 * feature working right up until a user reopens a thread and sees someone
 * else's turn.
 */
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import type { ConversationResumeState } from "./useConversationResume";
import { conversationRuntimeKey } from "./useConversationResume";
import { ConversationResumeNotice } from "./ConversationResumeNotice";

const readyState: ConversationResumeState = {
  status: "ready",
  conversation: { id: 42, title: null, created_at: "", messages: [] },
};

describe("conversationRuntimeKey", () => {
  it("is stable for a new conversation", () => {
    expect(conversationRuntimeKey(null, { status: "new" })).toBe("new");
  });

  it("changes when the conversation changes", () => {
    expect(conversationRuntimeKey(42, readyState)).not.toBe(
      conversationRuntimeKey(43, readyState),
    );
  });

  it("differs between pending and ready so the runtime rebuilds once history lands", () => {
    expect(conversationRuntimeKey(42, { status: "loading" })).not.toBe(
      conversationRuntimeKey(42, readyState),
    );
  });

  it("stays on the pending key while a resume fails, so a retry rebuilds it", () => {
    const failed: ConversationResumeState = {
      status: "error",
      error: { kind: "unreachable", message: "offline" },
    };

    expect(conversationRuntimeKey(42, failed)).toBe(
      conversationRuntimeKey(42, { status: "loading" }),
    );
  });
});

describe("ConversationResumeNotice", () => {
  it("offers a retry for a transport failure", () => {
    const onRetry = vi.fn();
    render(
      <ConversationResumeNotice
        error={{ kind: "unreachable", message: "Failed to fetch" }}
        onRetry={onRetry}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("does not offer a retry for a 404, which retrying cannot fix", () => {
    render(
      <ConversationResumeNotice
        error={{ kind: "not-found", message: "This conversation does not exist." }}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.queryByRole("button", { name: /try again/i })).not.toBeInTheDocument();
    expect(screen.getByText(/does not exist/i)).toBeInTheDocument();
  });
});