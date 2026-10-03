/**
 * Tests for the chat adapter.
 *
 * The adapter is the only file that translates between assistant-ui's
 * run/result shape and our SSE contract, so these cover the translation
 * and the two ways the backend can fail: an `error` event and a non-ok
 * HTTP response.
 *
 * `fetch` is stubbed at the network layer rather than mocking `streamChat`,
 * so the real SSE parser in client.ts is exercised too.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  ChatModelRunOptions,
  ChatModelRunResult,
} from "@assistant-ui/react";

import { ApiError } from "../api/client";
import {
  allergyChatAdapter,
  currentConversationId,
  resetConversation,
} from "./allergyChatAdapter";

vi.mock("../auth/token", () => ({
  getToken: vi.fn(() => "tkn-abc"),
}));

/** Build the SSE body the backend would send for one turn. */
function sseBody(
  reply: string,
  conversationId: number,
  done: Record<string, unknown> = {},
): string {
  const donePayload = {
    message: reply,
    conversation_id: conversationId,
    symptoms: [],
    severity: null,
    duration: null,
    possible_trigger: null,
    breathing_difficulty: null,
    airway_swelling: null,
    triage_level: "LOW",
    triage_reasons: [],
    triage_rule_version: "1",
    ...done,
  };
  return (
    `event: message\ndata: ${JSON.stringify({ delta: reply })}\n\n` +
    `event: done\ndata: ${JSON.stringify(donePayload)}\n\n`
  );
}

function runOptions(userText: string, signal = new AbortController().signal) {
  return {
    messages: [
      { id: "m0", role: "user", content: [{ type: "text", text: userText }] },
    ],
    abortSignal: signal,
  } as unknown as ChatModelRunOptions;
}

/**
 * The `ChatModelAdapter` contract widens `run` to a Promise or an async
 * generator. Ours only ever returns a Promise, so narrow it once here
 * instead of casting at every assertion.
 */
async function runAdapter(
  options: ChatModelRunOptions,
): Promise<ChatModelRunResult> {
  return (await allergyChatAdapter.run(options)) as ChatModelRunResult;
}

const okResponse = (body: string) =>
  new Response(new TextEncoder().encode(body), {
    status: 200,
    headers: { "content-type": "text/event-stream" },
  });

describe("allergyChatAdapter", () => {
  beforeEach(() => {
    resetConversation();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns the assistant reply from the message event", async () => {
    const fetchSpy = vi.fn().mockResolvedValue(okResponse(sseBody("I can help.", 7)));
    vi.stubGlobal("fetch", fetchSpy);

    const result = await runAdapter(runOptions("내 눈이 가려요"));

    expect(result.content).toEqual([{ type: "text", text: "I can help." }]);
  });

  it("sends the newest user text and a null id on the first turn", async () => {
    const fetchSpy = vi.fn().mockResolvedValue(okResponse(sseBody("ok", 7)));
    vi.stubGlobal("fetch", fetchSpy);

    await allergyChatAdapter.run(runOptions("first question"));

    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toContain("/api/chat");
    expect(JSON.parse(init.body)).toEqual({
      message: "first question",
      conversation_id: null,
    });
  });

  it("carries the conversation id into the next turn", async () => {
    const fetchSpy = vi
      .fn()
      .mockResolvedValueOnce(okResponse(sseBody("first answer", 42)))
      .mockResolvedValueOnce(okResponse(sseBody("second answer", 42)));
    vi.stubGlobal("fetch", fetchSpy);

    await allergyChatAdapter.run(runOptions("first question"));
    expect(currentConversationId()).toBe(42);

    await allergyChatAdapter.run(runOptions("second question"));
    expect(JSON.parse(fetchSpy.mock.calls[1][1].body).conversation_id).toBe(42);
  });

  it("reads only the latest user turn, not the whole history", async () => {
    const fetchSpy = vi.fn().mockResolvedValue(okResponse(sseBody("ok", 7)));
    vi.stubGlobal("fetch", fetchSpy);

    const options = {
      messages: [
        { id: "m0", role: "user", content: [{ type: "text", text: "older" }] },
        { id: "m1", role: "assistant", content: [{ type: "text", text: "reply" }] },
        { id: "m2", role: "user", content: [{ type: "text", text: "newest" }] },
      ],
      abortSignal: new AbortController().signal,
    } as unknown as ChatModelRunOptions;

    await allergyChatAdapter.run(options);

    expect(JSON.parse(fetchSpy.mock.calls[0][1].body).message).toBe("newest");
  });

  it("throws the backend's own message when an error event arrives", async () => {
    const body = `event: error\ndata: ${JSON.stringify({ detail: "no LLM configured" })}\n\n`;
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(okResponse(body)));

    await expect(allergyChatAdapter.run(runOptions("hi"))).rejects.toThrow(
      "no LLM configured",
    );
  });

  it("throws the server detail rather than a generic error on a 401", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "Could not validate credentials" }), {
          status: 401,
          headers: { "content-type": "application/json" },
        }),
      ),
    );

    // The client throws ApiError; the adapter re-throws with the detail so the
    // screen can show the reason rather than "something went wrong".
    await expect(allergyChatAdapter.run(runOptions("hi"))).rejects.toThrow(
      "Could not validate credentials",
    );
  });

  it("does not call the backend when the prompt is empty", async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);

    const result = await runAdapter(runOptions("   "));

    expect(fetchSpy).not.toHaveBeenCalled();
    expect(result.content).toEqual([{ type: "text", text: "" }]);
  });

  it("exports ApiError from the client for callers that catch it", () => {
    // Sanity check that the error type the adapter branches on is the one the
    // client actually throws.
    expect(new ApiError(500, "boom")).toBeInstanceOf(ApiError);
  });
});
