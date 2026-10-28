/**
 * Conversation-list and resume helpers (TASKS.md B-014).
 *
 * Pure functions only: route parsing, the title fallback, and the mapping
 * from the backend's stored messages onto assistant-ui's `initialMessages`.
 * Everything that touches the network or React lives in
 * `useConversationResume.ts`.
 *
 * The backend already persists every conversation and message; what was
 * missing was a way back in. `/chat/:conversationId` is that way in, and
 * `/chat` with no id is a brand new conversation.
 */
import type { ThreadMessageLike } from "@assistant-ui/react";

import type {
  ConversationDetail,
  ConversationMessage,
  ConversationSummary,
} from "../../api/types";
import { TRIAGE_PART_NAME } from "../allergyChatAdapter";

export const UNTITLED_CONVERSATION = "Untitled conversation";

/**
 * `/chat/abc` is not a conversation. Returning null routes it to the new
 * conversation rather than firing a request that can only 404.
 */
export function parseConversationId(raw: string | undefined): number | null {
  if (raw === undefined || raw === "") return null;
  const parsed = Number(raw);
  if (!Number.isInteger(parsed) || parsed <= 0) return null;
  return parsed;
}

export function conversationTitle(conversation: Pick<ConversationSummary, "title">): string {
  const title = conversation.title?.trim();
  return title ? title : UNTITLED_CONVERSATION;
}

export function conversationPreview(
  conversation: Pick<ConversationSummary, "last_message">,
): string | null {
  const preview = conversation.last_message?.trim();
  return preview ? preview : null;
}

type ThreadMessagePart = Exclude<ThreadMessageLike["content"], string>[number];

/**
 * A stored assistant turn carries the verdict the rule engine produced, and a
 * live turn carries it as a data part. Reopening a conversation has to rebuild
 * the same part or the safety banner silently disappears on resume, which is
 * exactly the turn a returning user most needs to re-read.
 */
function messageParts(message: ConversationMessage): readonly ThreadMessagePart[] {
  const parts: ThreadMessagePart[] = [{ type: "text", text: message.content }];

  if (message.triage_level !== null && message.triage_level !== undefined) {
    parts.push({
      type: `data-${TRIAGE_PART_NAME}`,
      data: { level: message.triage_level, reasons: message.triage_reasons },
    });
  }

  return parts;
}

/**
 * Seed the assistant-ui thread with a conversation's stored history.
 *
 * Order matters: assistant-ui renders messages in array order and the backend
 * returns them oldest first.
 *
 * The server timestamp travels in the message metadata rather than in
 * `createdAt`. assistant-ui fills `createdAt` with the local clock for a
 * message that has none, and a locally invented time is not the time the
 * message was sent. Only the server knows that.
 */
export function toThreadMessages(conversation: ConversationDetail): ThreadMessageLike[] {
  return conversation.messages.map((message) => ({
    id: String(message.id),
    role: message.role,
    content: messageParts(message),
    createdAt: new Date(message.created_at),
    metadata: { custom: { sentAt: message.created_at } },
  }));
}