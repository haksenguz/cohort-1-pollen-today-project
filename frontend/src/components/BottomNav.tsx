import { NavLink } from "react-router-dom";
import { AlertsTabIcon, ChatTabIcon, TodayTabIcon } from "./icons";

const TABS = [
  { to: "/chat", label: "Chat", icon: ChatTabIcon },
  { to: "/today", label: "Today", icon: TodayTabIcon },
  { to: "/alerts", label: "Alerts", icon: AlertsTabIcon },
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
