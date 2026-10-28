import { Outlet, useLocation } from "react-router-dom";
import { BottomNav } from "./BottomNav";
import { ConsentGate } from "./ConsentGate";
import { TopHeader } from "./TopHeader";
import { Toaster } from "./ui/sonner";
import { useAlertPolling } from "../hooks/useAlertPolling";

/** Phone-first app frame: header + envstrip, a scrollable stage, bottom tab nav. */
export function AppShell() {
  // Mounted here, not on AlertsPage. The point of an alert is that it reaches
  // you while you are somewhere else — outdoors, on Chat, on Today. Scoping the
  // poll to the alerts screen would only ever notify you when you were already
  // looking at the alerts. The hook keeps its seen-set and timer at module
  // scope, so this costs one request per interval regardless of navigation.
  useAlertPolling();

  const location = useLocation();
  // The chat is the 민감정보 flow, so it is the one that asks first. Every
  // other screen stays open, because the settings row that withdraws the
  // agreement has to be reachable while the chat is closed.
  const isSensitiveFlow =
    location.pathname === "/chat" || location.pathname.startsWith("/chat/");

  return (
    <div className="app-shell">
      <TopHeader />
      <div className="stage">
        {isSensitiveFlow ? (
          <ConsentGate>
            <Outlet />
          </ConsentGate>
        ) : (
          <Outlet />
        )}
      </div>
      <BottomNav />
      {/* Mounted once, here, because every notification in the app routes
          through it. Install / update / offline are no longer per-component
          fixed panels. */}
      <Toaster />
    </div>
  );
}
