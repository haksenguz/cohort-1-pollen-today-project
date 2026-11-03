import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "./AuthContext";
import { ServerUnreachable } from "./ServerUnreachable";
import { ConsentProvider } from "./ConsentContext";

/** Guards a route: redirects to /login when there is no authenticated user. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { status, retry } = useAuth();
  const location = useLocation();

  if (status === "loading") {
    return <div className="screen-loading">Loading…</div>;
  }

  // The token is still good and the server is not answering. Sending the user
  // to /login would ask for a password for a session that never died, so this
  // screen waits and offers a retry instead.
  if (status === "unreachable") {
    return <ServerUnreachable onRetry={retry} />;
  }

  if (status === "unauthenticated") {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  // The consent state lives above every authenticated screen, so the gate in
  // front of the chat and the row in Settings read the same record.
  return (
    <ConsentProvider>
      {children}
    </ConsentProvider>
  );
}
