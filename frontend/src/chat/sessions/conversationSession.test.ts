/**
 * Resume-mapping tests.
 *
 * The mapping is the whole resume feature: if it is wrong the reopened thread
 * is either empty or missing the safety verdict the rule engine produced.
 */
import { describe, expect, it } from "vitest";

import { TRIAGE_PART_NAME } from "../allergyChatAdapter";
import type { ConversationDetail, ConversationMessage } from "../../api/types";
import {
  UNTITLED_CONVERSATION,
  conversationPreview,
  conversationTitle,
  parseConversationId,
  toThreadMessages,
} from "./conversationSession";

const detail = (messages: ConversationDetail["messages"]): ConversationDetail => ({
  id: 42,
  title: "chest tightness after running",
  created_at: "2026-10-16T08:12:00Z",
  messages,
});

describe("parseConversationId", () => {
  it("accepts a positive integer id", () => {
    expect(parseConversationId("42")).toBe(42);
  });

  it("treats a missing, blank or non-numeric param as no conversation", () => {
    expect(parseConversationId(undefined)).toBeNull();
    expect(parseConversationId("")).toBeNull();
    expect(parseConversationId("abc")).toBeNull();
    expect(parseConversationId("4.2")).toBeNull();
    expect(parseConversationId("0")).toBeNull();
    expect(parseConversationId("-7")).toBeNull();
  });
});

describe("conversationTitle", () => {
  it("prefers the generated title", () => {
    expect(conversationTitle({ title: "chest tightness after running" })).toBe(
      "chest tightness after running",
    );
  });

  it("falls back when the title is null or blank", () => {
    expect(conversationTitle({ title: null })).toBe(UNTITLED_CONVERSATION);
    expect(conversationTitle({ title: "  " })).toBe(UNTITLED_CONVERSATION);
  });
});

describe("conversationPreview", () => {
  it("returns the last message, trimmed", () => {
    expect(conversationPreview({ last_message: "  it started 10 minutes ago  " })).toBe(
      "it started 10 minutes ago",
    );
  });

  it("returns null when there is nothing to preview", () => {
    expect(conversationPreview({ last_message: null })).toBeNull();
    expect(conversationPreview({ last_message: "   " })).toBeNull();
  });
});

describe("toThreadMessages", () => {
  const userMessage: ConversationMessage = {
    id: 9001,
    role: "user",
    content: "my chest feels tight",
    triage_level: null,
    triage_reasons: [],
    created_at: "2026-10-16T08:12:00Z",
  };

  const assistantMessage: ConversationMessage = {
    id: 9002,
    role: "assistant",
    content: "Thanks. How long has it been going on?",
    triage_level: "MODERATE",
    triage_reasons: ["severity 6 >= 5"],
    created_at: "2026-10-16T08:14:31Z",
  };

  it("keeps the backend's message order and roles", () => {
    const messages = toThreadMessages(detail([userMessage, assistantMessage]));

    expect(messages.map((message) => message.role)).toEqual(["user", "assistant"]);
    expect(messages.map((message) => message.id)).toEqual(["9001", "9002"]);
  });

  it("carries the stored triage verdict as the same data part a live turn emits", () => {
    const [, assistant] = toThreadMessages(detail([userMessage, assistantMessage]));

    expect(assistant.content).toEqual([
      { type: "text", text: assistantMessage.content },
      {
        type: `data-${TRIAGE_PART_NAME}`,
        data: { level: "MODERATE", reasons: ["severity 6 >= 5"] },
      },
    ]);
  });

  it("omits the verdict part for a turn that has no triage level", () => {
    const [user, assistant] = toThreadMessages(
      detail([userMessage, { ...assistantMessage, triage_level: null }]),
    );

    expect(assistant.content).toEqual([{ type: "text", text: assistantMessage.content }]);
    expect(user.content).toEqual([{ type: "text", text: userMessage.content }]);
  });

  it("parses the created_at stamp into a Date", () => {
    const [first] = toThreadMessages(detail([userMessage]));

    expect(first.createdAt).toBeInstanceOf(Date);
    expect(first.createdAt?.toISOString()).toBe("2026-10-16T08:12:00.000Z");
  });

  it("returns an empty array for a conversation with no messages", () => {
    expect(toThreadMessages(detail([]))).toEqual([]);
  });
});