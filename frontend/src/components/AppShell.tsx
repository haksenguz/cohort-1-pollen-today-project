import { Outlet } from "react-router-dom";
import { BottomNav } from "./BottomNav";
import { TopHeader } from "./TopHeader";
import { Toaster } from "./ui/sonner";

/** Phone-first app frame: header + envstrip, a scrollable stage, bottom tab nav. */
export function AppShell() {
  return (
    <div className="app-shell">
      <TopHeader />
      <div className="stage">
        <Outlet />
      </div>
      <BottomNav />
      {/* Mounted once, here, because every notification in the app routes
          through it. Install / update / offline are no longer per-component
          fixed panels. */}
      <Toaster />
    </div>
  );
}
