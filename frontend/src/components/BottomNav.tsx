import { NavLink } from "react-router-dom";
import { AlertsTabIcon, ChatTabIcon, SettingsTabIcon, TodayTabIcon } from "./icons";

// Settings is a tab, not a header gear. On a 375px phone held one-handed the
// bottom of the screen is the reachable zone, and it is where the other three
// destinations already live.
const TABS = [
  { to: "/chat", label: "Chat", icon: ChatTabIcon },
  { to: "/today", label: "Today", icon: TodayTabIcon },
  { to: "/alerts", label: "Alerts", icon: AlertsTabIcon },
  { to: "/settings", label: "Settings", icon: SettingsTabIcon },
];

export function BottomNav() {
  return (
    <nav className="nav">
      {TABS.map(({ to, label, icon: Icon }) => (
        <NavLink key={to} to={to} className={({ isActive }) => (isActive ? "on" : "")}>
          <Icon />
          {label}
        </NavLink>
      ))}
    </nav>
  );
}
