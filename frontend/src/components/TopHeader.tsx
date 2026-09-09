import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronRightIcon, LeafIcon, ThemeIcon } from "./icons";

type ThemePref = "system" | "light" | "dark";

const ORDER: ThemePref[] = ["system", "light", "dark"];
const STORAGE_KEY = "allergy_companion_theme";

function applyTheme(pref: ThemePref) {
  if (pref === "system") {
    document.documentElement.removeAttribute("data-theme");
  } else {
    document.documentElement.setAttribute("data-theme", pref);
  }
}

export function TopHeader() {
  const navigate = useNavigate();
  const [pref, setPref] = useState<ThemePref>(() => {
    try {
      return (localStorage.getItem(STORAGE_KEY) as ThemePref) ?? "system";
    } catch {
      return "system";
    }
  });

  useEffect(() => {
    applyTheme(pref);
    try {
      localStorage.setItem(STORAGE_KEY, pref);
    } catch {
      // ignore
    }
  }, [pref]);

  function cycleTheme() {
    const next = ORDER[(ORDER.indexOf(pref) + 1) % ORDER.length];
    setPref(next);
  }

  return (
    <header className="top">
      <div className="brandrow">
        <span className="mark" aria-hidden="true">
          <LeafIcon />
        </span>
        <div className="brand">
          Allergy Companion
          <small>Your pocket allergy guide</small>
        </div>
        <span className="spacer" />
        <button className="iconbtn" onClick={cycleTheme} title={`Theme: ${pref}`} aria-label="Toggle theme">
          <ThemeIcon />
        </button>
      </div>
      <button className="envstrip" onClick={() => navigate("/today")}>
        <span className="risk-dot" style={{ background: "var(--brand)" }} />
        <span className="lbl">See today&apos;s pollen, air quality and risk</span>
        <span className="go">
          Open <ChevronRightIcon />
        </span>
      </button>
    </header>
  );
}
