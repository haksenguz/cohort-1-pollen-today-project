/**
 * The conversation list inside the history sheet.
 *
 * Loading, empty and error are three separate renders, not one list with
 * different text. "You have no conversations yet" and "we could not load
 * them" are different facts, and collapsing them into one blank panel is how
 * a user ends up staring at an outage thinking they lost their history.
 */
import { AlertCircle } from "lucide-react";
import { NavLink } from "react-router-dom";

import type { ConversationSummary } from "../api/types";
import {
  conversationPreview,
  conversationTitle,
} from "../chat/sessions/conversationSession";
import { cn } from "../lib/utils";
import { formatRelativeTime } from "../utils/format";
import { Alert, AlertDescription, AlertTitle } from "./ui/alert";
import { Button } from "./ui/button";
import { Skeleton } from "./ui/skeleton";

export type ConversationListState =
  | { status: "loading" }
  | { status: "error"; message: string; onRetry: () => void }
  | { status: "ready"; conversations: ConversationSummary[]; activeId?: number };

export function ChatHistoryList({ state }: { state: ConversationListState }) {
  if (state.status === "loading") {
    return (
      <div role="status" aria-live="polite" aria-busy="true">
        <span className="sr-only">Loading conversations</span>
        <ul className="flex flex-col gap-2">
          {[0, 1, 2].map((row) => (
            <li key={row} className="rounded-xl border border-border bg-card p-3">
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="mt-2 h-3 w-full" />
            </li>
          ))}
        </ul>
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <Alert variant="destructive">
        <AlertCircle />
        <AlertTitle>Could not load your conversations</AlertTitle>
        <AlertDescription className="flex flex-col items-start gap-3">
          <span>{state.message}</span>
          <Button variant="outline" className="min-h-11" onClick={state.onRetry}>
            Try again
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  if (state.conversations.length === 0) {
    return (
      <Alert>
        <AlertTitle>No conversations yet</AlertTitle>
        <AlertDescription>
          Conversations you start appear here, so you can pick one back up after a refresh.
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <ul className="flex flex-col gap-2">
      {state.conversations.map((conversation) => (
        <ConversationRow
          key={conversation.id}
          conversation={conversation}
          active={conversation.id === state.activeId}
        />
      ))}
    </ul>
  );
}

/**
 * One row is a link, not a clickable div: `NavLink` already gives it keyboard
 * activation, the right role, and the focus ring behaviour React Router's
 * link handling expects.
 */
function ConversationRow({
  conversation,
  active,
}: {
  conversation: ConversationSummary;
  active: boolean;
}) {
  const preview = conversationPreview(conversation);

  return (
    <li>
      <NavLink
        to={`/chat/${conversation.id}`}
        className={cn(
          "flex min-h-11 flex-col gap-1 rounded-xl border p-3 transition-colors hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none",
          active ? "border-primary bg-accent" : "border-border bg-card",
        )}
      >
        <span className="flex items-baseline gap-2">
          <span className="truncate text-sm font-semibold text-card-foreground">
            {conversationTitle(conversation)}
          </span>
          <span className="ml-auto shrink-0 text-xs text-muted-foreground">
            {formatRelativeTime(conversation.updated_at)}
          </span>
        </span>
        {preview !== null && (
          <span className="truncate text-sm text-muted-foreground">{preview}</span>
        )}
      </NavLink>
    </li>
  );
}