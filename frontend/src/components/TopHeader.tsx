import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getCurrentEnvironment } from "../api/client";
import type { RiskLevel } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { formatRisk, riskClass } from "../utils/format";
import { LeafIcon } from "./icons";

/**
 * The header is one slim row (B-028).
 *
 * The brand sits on the left and the current risk on the right, the way
 * ChatGPT's mobile header does: identity first, actions second, and never a
 * second row of chrome. The old second row was a full-width strip that
 * repeated what the Today tab already says, and it cost about 114 pixels
 * before the first message.
 *
 * The risk pill is the way into Today, so it carries the risk level and the
 * dot that colours it. Both come from `utils/format.ts`: the component never
 * decides what a risk level looks like or what it is called.
 */
export function TopHeader() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [risk, setRisk] = useState<RiskLevel | null | undefined>(undefined);

  const lat = user?.latitude ?? null;
  const lon = user?.longitude ?? null;

  useEffect(() => {
    // `undefined` means "no reading yet", `null` means "the providers gave
    // nothing to score". The two are different, so the pill never claims a
    // level it does not have.
    if (lat === null || lon === null) {
      setRisk(null);
      return;
    }

    let cancelled = false;
    setRisk(undefined);
    getCurrentEnvironment(lat, lon)
      .then((env) => {
        if (!cancelled) setRisk(env.risk);
      })
      .catch(() => {
        // A provider that is down is not a low-risk day, so the pill keeps the
        // unavailable state instead of inventing a level.
        if (!cancelled) setRisk(null);
      });

    return () => {
      cancelled = true;
    };
  }, [lat, lon]);

  const level = risk === undefined ? "" : formatRisk(risk);
  const dotClass = riskClass(risk ?? null);

  return (
    <header className="top">
      <div className="brandrow">
        <span className="mark" aria-hidden="true">
          <LeafIcon />
        </span>
        <span className="brand brand-name">Allergy Companion</span>
      </div>
      <button
        type="button"
        className="riskpill"
        onClick={() => navigate("/today")}
        /* The visible label is the risk level, so it belongs in the accessible
           name too. The name also says where the control goes. */
        aria-label={
          level
            ? `${level}. Today's pollen and air quality, open Today`
            : "Today's pollen and air quality, open Today"
        }
      >
        <span className={`risk-dot ${dotClass}`} aria-hidden="true" />
        {level ? <span className="riskpill-lvl">{level}</span> : null}
      </button>
    </header>
  );
}
