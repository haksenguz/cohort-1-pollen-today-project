/**
 * Arrow-key recall for the composer.
 *
 * The thread already holds every message this conversation sent, so the recall
 * list is derived from the transcript rather than kept in a parallel store that
 * could drift from it. A resumed conversation therefore comes back with its
 * recall history intact instead of starting from an empty list.
 *
 * Shell semantics: ArrowUp walks backwards from the draft, ArrowDown walks
 * forwards, and walking past the newest entry restores whatever the user had
 * typed before they started recalling.
 *
 * Nothing here reads or writes the assistant runtime directly. The history is a
 * plain value and the stepping is a pure function, so both are testable without
 * mounting a thread.
 */
import { useCallback, useMemo, useRef } from "react";

import { useAuiState } from "@assistant-ui/react";

/** Sentinel for "the composer holds the user's own text, not a sent message". */
export const DRAFT = -1;

/** A message we may not be able to read at all. */
type Unreadable = { role?: unknown; parts?: unknown };

/**
 * The text of one message, or null when the message cannot be read.
 *
 * A part we do not recognise is skipped rather than rendered as an empty
 * string, and a message whose parts we cannot enumerate returns null so the
 * caller can leave it out of the recall list entirely. Skipping beats emitting
 * a blank entry the user would arrow onto and find nothing in.
 */
export function partText(parts: unknown): string | null {
  if (!Array.isArray(parts)) return null;

  const chunks: string[] = [];
  for (const part of parts) {
    if (!part || typeof part !== "object") continue;
    const candidate = part as { type?: unknown; text?: unknown };
    if (candidate.type !== "text" || typeof candidate.text !== "string") continue;
    chunks.push(candidate.text);
  }
  return chunks.join("");
}

/**
 * Every message the user sent, oldest first.
 *
 * Anything unreadable is dropped instead of coerced to "" so that a malformed
 * message cannot become a blank arrow target. Blank sends are dropped for the
 * same reason: recalling an empty draft is never what the user wanted.
 */
export function sentMessageTexts(messages: unknown): string[] {
  if (!Array.isArray(messages)) return [];

  const sent: string[] = [];
  for (const message of messages) {
    if (!message || typeof message !== "object") continue;
    const candidate = message as Unreadable;
    if (candidate.role !== "user") continue;

    const text = partText(candidate.parts);
    if (text === null) continue;

    const trimmed = text.trim();
    if (trimmed.length > 0) sent.push(trimmed);
  }
  return sent;
}

/**
 * The index one arrow press away from `index`. `direction` is -1 for up and 1
 * for down. Walks clamp at the ends rather than wrapping, which is what a shell
 * does and what stops one stray press from teleporting to the oldest message.
 */
export function stepHistory(
  history: readonly string[],
  index: number,
  direction: -1 | 1,
): number {
  if (history.length === 0) return DRAFT;

  if (direction === -1) {
    return index === DRAFT ? history.length - 1 : Math.max(0, index - 1);
  }
  if (index === DRAFT) return DRAFT;
  if (index >= history.length - 1) return DRAFT;
  return index + 1;
}

/**
 * The composer text for a recall index.
 *
 * An index we cannot read resolves to the draft rather than to undefined or an
 * empty string, so a stale index can never blank the composer.
 */
export function historyValue(
  history: readonly string[],
  index: number,
  draft: string,
): string {
  if (index === DRAFT) return draft;
  return history[index] ?? draft;
}

/**
 * Wires ArrowUp/ArrowDown recall to the composer.
 *
 * The draft is captured on the first ArrowUp only, so holding the key down and
 * walking backwards keeps returning to the text the user actually had.
 */
export function useComposerHistory() {
  const messages = useAuiState((s) => s.thread.messages);

  const history = useMemo(() => sentMessageTexts(messages), [messages]);
  const indexRef = useRef<number>(DRAFT);
  const draftRef = useRef<string>("");

  const recall = useCallback(
    (direction: -1 | 1, current: string) => {
      if (direction === -1 && indexRef.current === DRAFT) {
        draftRef.current = current;
      }
      const next = stepHistory(history, indexRef.current, direction);
      indexRef.current = next;
      return historyValue(history, next, draftRef.current);
    },
    [history],
  );

  /* Typing means the user has abandoned the walk, so the next ArrowUp starts
     again from the newest send. The composer input is a controlled textarea,
     so this only fires for real typing and not for setText below. */
  const forget = useCallback(() => {
    indexRef.current = DRAFT;
    draftRef.current = "";
  }, []);

  return {
    recall,
    forget,
    canRecall: history.length > 0,
    /* Read inside the key handler, so a ref is enough and this does not force
       a re-render on every arrow press. */
    isWalking: () => indexRef.current !== DRAFT,
  };
}