import { ArrowLeft } from "lucide-react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";

import { getCurrentEnvironment } from "../api/client";
import type { RiskLevel } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { formatRisk, riskClass } from "../utils/format";
import { LeafIcon } from "./icons";
import { useSwr } from "../utils/swrCache";
import { SCREEN_TITLE } from "../routes/settings/screenTitles";
import { isSettingsScreenId } from "../routes/settings/settingsScreenIds";

/** What the header calls the screen the user is on. Unknown routes keep the brand. */
function titleFor(pathname: string, subscreen: string | null): string {
  if (pathname.startsWith("/settings") && subscreen && isSettingsScreenId(subscreen)) {
    return SCREEN_TITLE[subscreen];
  }
  if (pathname.startsWith("/chat")) return "Chat";
  if (pathname.startsWith("/today")) return "Today";
  if (pathname.startsWith("/alerts")) return "Alerts";
  if (pathname.startsWith("/settings")) return "Settings";
  return "Allergy Companion";
}

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
  const { pathname } = useLocation();
  const [params] = useSearchParams();
  const subscreen = pathname.startsWith("/settings") ? params.get("screen") : null;
  const inSubscreen = subscreen !== null && isSettingsScreenId(subscreen);
  const title = titleFor(pathname, subscreen);
  const { user } = useAuth();
  const lat = user?.latitude ?? null;
  const lon = user?.longitude ?? null;

  // Shares its cache key with the Today screen, so opening Today after the
  // header has loaded costs no second request. `undefined` means "no reading
  // yet", `null` means "the providers gave nothing to score": the pill never
  // claims a level it does not have.
  const reading = useSwr(
    lat !== null && lon !== null ? `env:${lat.toFixed(2)},${lon.toFixed(2)}` : null,
    () => getCurrentEnvironment(lat as number, lon as number),
    { freshMs: 30 * 60_000, maxAgeMs: 6 * 3_600_000 },
  );
  const risk: RiskLevel | null | undefined = reading.data
    ? reading.data.risk
    : reading.loading
      ? undefined
      : null;

  const level = risk === undefined ? "" : formatRisk(risk);
  const dotClass = riskClass(risk ?? null);

  return (
    <header className="top" data-subscreen={inSubscreen ? "true" : undefined}>
      <div className="brandrow">
        {inSubscreen ? (
          <button
            type="button"
            className="top-back"
            aria-label="Back to settings"
            onClick={() => navigate("/settings", { replace: true })}
          >
            <ArrowLeft aria-hidden="true" />
          </button>
        ) : (
          <span className="mark" aria-hidden="true">
            <LeafIcon />
          </span>
        )}
        {/* Keyed on the title so the text fades in again on every change. */}
        <span className="brand brand-name brand-swap" key={title}>
          {title}
        </span>
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
