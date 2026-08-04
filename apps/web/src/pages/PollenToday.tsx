import {
  ALL_REGIONS,
  PollenType,
  RiskLevel,
  type Region,
} from "@pollen/contracts";
import { useEffect, useState } from "react";
import { gql } from "../lib/graphql";
import {
  FORECAST_QUERY,
  type ForecastData,
  type ForecastVars,
} from "../lib/queries";

/**
 * Pollen Today — rough first pass.
 *
 * Reconstructed from the kickoff deck, not from the mentor's design file
 * (that link is not publicly readable). Layout, copy and the four risk colours
 * are placeholders until the Figma lands — see OPEN_QUESTIONS.md §3.
 */

const RISK_COLOR: Record<RiskLevel, string> = {
  [RiskLevel.LOW]: "var(--risk-low)",
  [RiskLevel.MODERATE]: "var(--risk-moderate)",
  [RiskLevel.HIGH]: "var(--risk-high)",
  [RiskLevel.VERY_HIGH]: "var(--risk-very-high)",
};

const RISK_LABEL: Record<RiskLevel, string> = {
  [RiskLevel.LOW]: "Low",
  [RiskLevel.MODERATE]: "Moderate",
  [RiskLevel.HIGH]: "High",
  [RiskLevel.VERY_HIGH]: "Very high",
};

const ADVICE: Record<RiskLevel, string> = {
  [RiskLevel.LOW]: "A good day to be outside.",
  [RiskLevel.MODERATE]: "Most people are fine. Sensitive people, take care.",
  [RiskLevel.HIGH]: "Take your medication before you go out, not after.",
  [RiskLevel.VERY_HIGH]: "Stay indoors where you can. Windows closed.",
};

function dayOfWeek(iso: string): string {
  return new Date(`${iso}T00:00:00+09:00`).toLocaleDateString("en-US", {
    weekday: "short",
    timeZone: "Asia/Seoul",
  });
}

export function PollenToday() {
  const [region, setRegion] = useState<Region>(ALL_REGIONS[0]!);
  const [data, setData] = useState<ForecastData["forecast"] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError(null);

    gql<ForecastData, ForecastVars>(FORECAST_QUERY, {
      region,
      pollenType: PollenType.WEEDS,
    })
      .then(({ forecast }) => {
        if (!cancelled) setData(forecast);
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      });

    return () => {
      cancelled = true;
    };
  }, [region]);

  const today = data?.days[0];

  return (
    <div className="wrap">
      <header className="masthead">
        <h1>Pollen Today</h1>
        <select
          className="region-select"
          value={region}
          onChange={(e) => setRegion(e.target.value as Region)}
          aria-label="Region"
        >
          {ALL_REGIONS.map((r) => (
            <option key={r} value={r}>
              {r.charAt(0) + r.slice(1).toLowerCase()}
            </option>
          ))}
        </select>
      </header>

      {error && (
        <div className="card">
          <p>
            Could not load the forecast ({error}). Is the API running on :8000?
          </p>
        </div>
      )}

      {!data && !error && (
        <div className="today" style={{ background: "var(--border)" }}>
          <p className="label">Tomorrow</p>
          <p className="level">…</p>
          <p className="sub">Loading</p>
        </div>
      )}

      {today && (
        <>
          <section
            className="today"
            style={{ background: RISK_COLOR[today.riskLevel] }}
            aria-live="polite"
          >
            <p className="label">Tomorrow · Ragweed</p>
            <p className="level">{RISK_LABEL[today.riskLevel]}</p>
            <p className="sub">{ADVICE[today.riskLevel]}</p>
          </section>

          <h2 className="section-title">Next three days</h2>
          <div className="days">
            {data.days.map((d) => (
              <div className="day" key={d.date}>
                <div className="dow">{dayOfWeek(d.date)}</div>
                <div
                  className="dot"
                  style={{ background: RISK_COLOR[d.riskLevel] }}
                />
                <div className="lvl">{RISK_LABEL[d.riskLevel]}</div>
              </div>
            ))}
          </div>

          <div className="legend">
            {(Object.values(RiskLevel) as RiskLevel[]).map((lvl) => (
              <span key={lvl}>
                <i style={{ background: RISK_COLOR[lvl] }} />
                {RISK_LABEL[lvl]}
              </span>
            ))}
          </div>
        </>
      )}

      <h2 className="section-title">
        Get the morning warning
        <span className="stub">stub</span>
      </h2>
      <div className="card">
        <p>
          One public Telegram channel per region. We post the evening before
          when tomorrow is High or above. No account, no email, no phone number.
        </p>
        <a className="btn" href="#" aria-disabled="true">
          Open the {region.charAt(0) + region.slice(1).toLowerCase()} channel
        </a>
      </div>

      <p className="disclaimer">
        Pollen risk data published by the Korea Meteorological Administration.
        This is not medical advice — for guidance on managing allergy symptoms,
        follow KMA and your doctor.
        {data && <> Model {data.modelVersion}.</>}
      </p>
    </div>
  );
}
