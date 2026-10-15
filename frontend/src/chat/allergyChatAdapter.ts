/**
 * The one place that knows our chat wire format.
 *
 * assistant-ui owns the thread state, the composer, auto-scroll, the
 * running/cancel states and error rendering. This adapter is the seam:
 * it hands assistant-ui a promise of a finished assistant message, and
 * does the SSE work behind that promise using the `streamChat` client
 * that already parses the `message` / `done` / `error` events defined in
 * docs/API_CONTRACT.md.
 *
 * Note the backend sends the entire assistant reply in a single `message`
 * event rather than token by token, so there is nothing to yield
 * incrementally. We return one completed result.
 */
import type {
  ChatModelAdapter,
  ChatModelRunOptions,
  ChatModelRunResult,
} from "@assistant-ui/react";
import { ApiError, streamChat } from "../api/client";
import type { ChatResponse } from "../api/types";
import { clearActivity, setActivity } from "./activity";

/**
 * The backend identifies a conversation by id and expects it back on the
 * next turn. assistant-ui owns the thread, so we hold the id here and feed
 * it forward. `resetConversation` drops it when the user starts over.
 */
let conversationId: number | null = null;

export function resetConversation(): void {
  conversationId = null;
}

export function currentConversationId(): number | null {
  return conversationId;
}

interface TextPart {
  type: "text";
  text: string;
}

function isTextPart(part: { type: string }): part is TextPart {
  return part.type === "text";
}

/**
 * The prompt to send is the most recent user turn. assistant-ui hands us
 * the whole thread, and our endpoint takes a single `message` field, not a
 * history, so we do not replay earlier turns to the backend.
 */
function lastUserText(options: ChatModelRunOptions): string {
  const { messages } = options;
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const message = messages[i];
    if (message.role !== "user") continue;
    const text = message.content
      .filter(isTextPart)
      .map((part) => part.text)
      .join("")
      .trim();
    if (text) return text;
  }
  return "";
}

export const allergyChatAdapter: ChatModelAdapter = {
  async run(options: ChatModelRunOptions): Promise<ChatModelRunResult> {
    const prompt = lastUserText(options);
    if (!prompt) return { content: [{ type: "text", text: "" }] };

    // A plain object rather than three closure-captured lets: TypeScript
    // cannot see that the SSE callbacks reassign them, so `!== null` checks
    // below are what narrow these fields.
    const state: {
      reply: string;
      result: ChatResponse | null;
      streamError: string | null;
    } = { reply: "", result: null, streamError: null };

    // Show something immediately rather than waiting for the first `status`
    // event, which cannot arrive until the backend has opened the stream.
    setActivity("starting");

    try {
      await streamChat(
        prompt,
        conversationId,
        {
          // `status` events name which part of the turn is running. They are
          // pipeline stages, NOT tool calls — this agent has no tools.
          onStatus: (event) => setActivity(event.stage),
          onMessage: (delta) => {
            state.reply = delta;
          },
          onDone: (response) => {
            state.result = response;
          },
          onError: (event) => {
            state.streamError = event.detail;
          },
        },
        options.abortSignal,
      );
    } catch (error) {
      // Prefer the server's own wording. A 401 or a dead provider should read
      // as the reason it failed, not as a generic transport error.
      if (error instanceof ApiError) throw new Error(error.detail);
      throw error;
    } finally {
      // Runs on the throw paths too: a failed turn must not leave a spinner
      // spinning forever next to the error message.
      clearActivity();
    }

    if (state.streamError !== null) throw new Error(state.streamError);
    if (state.result !== null) conversationId = state.result.conversation_id;

    return { content: [{ type: "text", text: state.reply }] };
  },
};
