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
import { clearToken } from "../auth/token";
import { clearActivity, setActivity, setToolActivity } from "./activity";

/**
 * The backend identifies a conversation by id and expects it back on the
 * next turn. assistant-ui owns the thread, so we hold the id here and feed
 * it forward. `resetConversation` drops it when the user starts over.
 */
let conversationId: number | null = null;

/**
 * Name of the data part the verdict travels on. The renderer keys off this,
 * so both sides import it from here rather than repeating the string.
 */
export const TRIAGE_PART_NAME = "triage";

export function resetConversation(): void {
  conversationId = null;
}

/**
 * Hand the active conversation id to the adapter from outside.
 *
 * `conversationId` is module state, so a conversation reopened from
 * `/chat/:id` has to hand its id over before the first turn; otherwise the
 * next message posts `conversation_id: null`, the backend opens a fresh
 * conversation and the reopened thread is orphaned.
 */
export function adoptConversation(id: number | null): void {
  conversationId = id;
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

type AssistantPart = NonNullable<ChatModelRunResult["content"]>[number];

/**
 * The verdict rides on the assistant message as a data part rather than
 * loose component state, so it stays attached to the turn it belongs to and
 * survives scrolling, re-render and thread switches.
 *
 * `triage_level` is null when the backend did not run triage for a turn. That
 * is an absent verdict, not a LOW one, so no part is emitted and the renderer
 * has nothing to show.
 */
function assistantParts(reply: string, result: ChatResponse | null): AssistantPart[] {
  const parts: AssistantPart[] = [{ type: "text", text: reply }];
  const level = result?.triage_level;
  if (result && level) {
    const reasons = Array.isArray(result.triage_reasons) ? result.triage_reasons : [];
    parts.push({
      type: "data",
      name: TRIAGE_PART_NAME,
      data: {
        level,
        reasons: reasons.filter((r): r is string => typeof r === "string"),
      },
    });
  }
  return parts;
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
          // pipeline stages, NOT tool calls — a `tool` event is the only thing
          // that reports a tool, and it arrives separately.
          onStatus: (event) => setActivity(event.stage),
          onTool: (event) => setToolActivity(event),
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
      // A rejected token used to surface as an inline "Could not validate
      // credentials" that stayed on screen while every retry failed the same
      // way - a chat screen that could never recover. Drop the dead token and
      // go to the only place a new one can be issued.
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
        clearToken();
        window.location.replace("/login");
        return { content: [{ type: "text", text: "" }] };
      }
      // Otherwise prefer the server's own wording, so a dead provider reads as
      // the reason it failed rather than as a generic transport error.
      if (error instanceof ApiError) throw new Error(error.detail);
      throw error;
    } finally {
      // Runs on the throw paths too: a failed turn must not leave a spinner
      // spinning forever next to the error message.
      clearActivity();
    }

    if (state.streamError !== null) throw new Error(state.streamError);
    if (state.result !== null) conversationId = state.result.conversation_id;

    return { content: assistantParts(state.reply, state.result) };
  },
};
