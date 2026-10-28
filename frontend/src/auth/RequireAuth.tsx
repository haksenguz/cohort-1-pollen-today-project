import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "./AuthContext";
import { ConsentProvider } from "./ConsentContext";

/** Guards a route: redirects to /login when there is no authenticated user. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const location = useLocation();

  if (status === "loading") {
    return <div className="screen-loading">Loading…</div>;
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
