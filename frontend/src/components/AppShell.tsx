import { Outlet } from "react-router-dom";
import { BottomNav } from "./BottomNav";
import { TopHeader } from "./TopHeader";

/** Phone-first app frame: header + envstrip, a scrollable stage, bottom tab nav. */
export function AppShell() {
  return (
    <div className="app-shell">
      <TopHeader />
      <div className="stage">
        <Outlet />
      </div>
      <BottomNav />
    </div>
  );
}
