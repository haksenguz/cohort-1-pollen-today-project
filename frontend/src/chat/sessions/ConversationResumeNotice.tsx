/**
 * What the chat screen shows while a resumed conversation is being fetched, or
 * after it failed.
 *
 * Split out so the screen body stays a thread and a composer. The screen owns
 * the decision of when to show this instead of the thread; this only owns the
 * two states the thread cannot render honestly.
 */
import { AlertCircle } from "lucide-react";

import type { ConversationResumeError } from "./useConversationResume";
import { Alert, AlertDescription, AlertTitle } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";

export function ConversationResumeLoading() {
  return (
    <div className="screen-loading" role="status" aria-live="polite">
      Loading conversation…
    </div>
  );
}

export function ConversationResumeNotice({
  error,
  onRetry,
}: {
  error: ConversationResumeError;
  onRetry: () => void;
}) {
  return (
    <div className="flex flex-col gap-4">
      <Alert variant={error.kind === "not-found" ? "default" : "destructive"}>
        {error.kind === "not-found" ? null : <AlertCircle />}
        <AlertTitle>
          {error.kind === "not-found" ? "Conversation not found" : "Could not load this conversation"}
        </AlertTitle>
        <AlertDescription>{error.message}</AlertDescription>
      </Alert>

      {/* A 404 is permanent: it means the conversation is gone or was never
          this user's, and asking again cannot change that. Only the
          transport-shaped failures get a retry. */}
      {error.kind !== "not-found" && (
        <Button className="min-h-11" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}