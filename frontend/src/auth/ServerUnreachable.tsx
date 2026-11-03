/**
 * The screen for "we have a token, but the server is not answering".
 *
 * The old behaviour sent the user to /login whenever the profile request
 * failed, including when the server was simply unreachable. That turned a
 * dropped connection into a lost session: the token was thrown away and the
 * user had to type a password to get back into an app they were already signed
 * in to. Restarting the backend on a dev box was enough to do it.
 *
 * So this screen says what is actually true and offers the one action that
 * helps, which is trying again. The token stays where it is, so a retry that
 * succeeds puts the user straight back where they were.
 */
import { RefreshCw, TriangleAlert } from "lucide-react";

import { Button } from "@/components/ui/button";

export function ServerUnreachable({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="screen-loading">
      <div role="alert" className="flex max-w-sm flex-col items-center gap-3 px-6 text-center">
        <TriangleAlert aria-hidden="true" className="size-6 text-(--emergency)" />
        <p className="m-0 text-sm font-semibold text-(--brand-ink)">
          The server is not answering
        </p>
        <p className="m-0 text-[13.5px] text-(--ink-soft)">
          Your session is still signed in. Nothing was lost. Try again once the
          server is back.
        </p>
        <Button type="button" onClick={onRetry}>
          <RefreshCw aria-hidden="true" className="size-4" />
          Try again
        </Button>
      </div>
    </div>
  );
}
