/**
 * The resume path: read the conversation id out of the route, fetch that
 * conversation's messages, and expose the result as a small state machine
 * the chat screen can render.
 *
 * `GET /api/conversations/{id}` answers 404 both for a conversation that does
 * not exist and for one owned by another account, so those two cases cannot be
 * told apart from the client side. They are grouped into one "not-found"
 * outcome with wording that stays true either way. A transport failure is a
 * different outcome with a retry, because retrying can actually help.
 */
import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { ApiError, getConversation } from "../../api/client";
import type { ConversationDetail } from "../../api/types";
import { parseConversationId } from "./conversationSession";

export type ConversationResumeErrorKind = "not-found" | "unauthorized" | "unreachable";

export interface ConversationResumeError {
  kind: ConversationResumeErrorKind;
  message: string;
}

export type ConversationResumeState =
  | { status: "new" }
  | { status: "loading" }
  | { status: "ready"; conversation: ConversationDetail }
  | { status: "error"; error: ConversationResumeError };

/**
 * The `:conversationId` route param, or null on `/chat`. Reading it through
 * `useParams` means the chat screen needs no prop from the router, so the
 * route and the screen stay independently testable.
 */
export function useConversationRouteId(): number | null {
  const { conversationId } = useParams<{ conversationId?: string }>();
  return parseConversationId(conversationId);
}

export function useConversationResume(conversationId: number | null): {
  state: ConversationResumeState;
  retry: () => void;
} {
  const [state, setState] = useState<ConversationResumeState>(() =>
    conversationId === null ? { status: "new" } : { status: "loading" },
  );
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (conversationId === null) {
      // oxlint-disable-next-line react/set-state-in-effect -- mirror of the fetch branch below
      setState({ status: "new" });
      return;
    }

    let cancelled = false;
    // oxlint-disable-next-line react/set-state-in-effect -- reset-before-refetch so a retry never shows stale messages
    setState({ status: "loading" });

    getConversation(conversationId)
      .then((conversation) => {
        if (cancelled) return;
        setState({ status: "ready", conversation });
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setState({ status: "error", error: describeConversationError(error) });
      });

    return () => {
      cancelled = true;
    };
  }, [conversationId, attempt]);

  const retry = useCallback(() => {
    setAttempt((value) => value + 1);
  }, []);

  return { state, retry };
}

/**
 * `useLocalRuntime` reads `initialMessages` once, when it builds the runtime.
 * A chat screen that stays mounted across a route change would therefore keep
 * serving the previous conversation's messages, so the provider has to be
 * given a key that changes with the conversation.
 *
 * The extra `-pending` suffix matters: while a resumed conversation is still
 * loading there is nothing to seed the runtime with, and without the suffix
 * the runtime would be built empty and then never rebuilt once the history
 * arrived. Remounting on the fetch settling is the whole fix.
 */
export function conversationRuntimeKey(
  conversationId: number | null,
  state: ConversationResumeState,
): string {
  if (conversationId === null) return "new";
  if (state.status !== "ready") return `conversation-${conversationId}-pending`;
  return `conversation-${conversationId}`;
}

function describeConversationError(error: unknown): ConversationResumeError {
  if (error instanceof ApiError) {
    if (error.status === 404) {
      return {
        kind: "not-found",
        message: "This conversation does not exist, or it belongs to another account.",
      };
    }
    if (error.status === 401 || error.status === 403) {
      return {
        kind: "unauthorized",
        message: "Your session has expired. Sign in again to continue.",
      };
    }
    return { kind: "unreachable", message: error.detail };
  }
  if (error instanceof Error && error.message) {
    return { kind: "unreachable", message: error.message };
  }
  return { kind: "unreachable", message: "Could not reach the server." };
}