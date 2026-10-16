import { useNavigate } from "react-router-dom";
import { ChevronRightIcon, LeafIcon } from "./icons";

export function TopHeader() {
  const navigate = useNavigate();

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
