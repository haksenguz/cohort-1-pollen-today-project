/**
 * Today (risk + environment + nearby hospitals) — I6. Composes the
 * three data sources the shell needs: the current user (auth),
 * `/api/environment/current`, and `/api/hospitals/nearby`.
 *
 * The page degrades cleanly when:
 *   - the user has no saved location: prompt them to set one,
 *   - the environment endpoint fails: show the error,
 *   - the hospital provider is unkeyed: show a "provider unavailable" note
 *     instead of pretending there are zero results.
 */
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";

import { useAuth } from "../auth/AuthContext";
import { ApiError, getCurrentEnvironment, getNearbyHospitals } from "../api/client";
import type { EnvironmentResponse, HospitalNearbyResponse } from "../api/types";
import {
  formatDistance,
  formatPollen,
  formatPoints,
  formatRisk,
  riskClass,
} from "../utils/format";

export function TodayPage() {
  const { user, status } = useAuth();
  const navigate = useNavigate();
  const [env, setEnv] = useState<EnvironmentResponse | null>(null);
  const [envError, setEnvError] = useState<string | null>(null);
  const [hospitals, setHospitals] = useState<HospitalNearbyResponse | null>(null);
  const [hospitalsError, setHospitalsError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  const lat = user?.latitude ?? null;
  const lon = user?.longitude ?? null;
  const hasLocation = lat !== null && lon !== null;

  useEffect(() => {
    if (status === "loading") return;
    if (!hasLocation) return;

    let cancelled = false;
    // oxlint-disable-next-line react/set-state-in-effect -- reset-before-refetch on coord change
    setLoaded(false);
    setEnvError(null);
    setHospitalsError(null);

    Promise.allSettled([
      getCurrentEnvironment(lat as number, lon as number),
      getNearbyHospitals({ lat: lat as number, lon: lon as number }),
    ]).then(([envResult, hospResult]) => {
      if (cancelled) return;
      if (envResult.status === "fulfilled") {
        setEnv(envResult.value);
      } else {
        setEnvError(toMessage(envResult.reason));
      }
      if (hospResult.status === "fulfilled") {
        setHospitals(hospResult.value);
      } else {
        setHospitalsError(toMessage(hospResult.reason));
      }
      setLoaded(true);
    });

    return () => {
      cancelled = true;
    };
  }, [status, hasLocation, lat, lon]);

  if (status === "loading" || (hasLocation && !loaded && !envError)) {
    return (
      <div className="screen-loading" role="status" aria-live="polite">
        Loading today…
      </div>
    );
  }

  if (!hasLocation) {
    return (
      <>
        <h2 className="vt">Today</h2>
        <p className="vsub">Pollen, air quality and your risk score for today.</p>
        <div className="note">
          <span>Add a location to your profile to see your daily risk.</span>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="min-h-11 shrink-0"
            onClick={() => navigate("/settings?screen=location")}
          >
            Set your location
          </Button>
        </div>
      </>
    );
  }

  /**
   * I3 escape hatch. Without a POLLEN_API_KEY the backend returns a
   * deterministic *sample* and flags it with `pollen_is_sample`. Rendering those
   * numbers next to a small disclaimer still reads as a real reading, which is
   * the one thing this app must not do with health data — so the values are
   * withheld and the row says "unavailable" instead.
   *
   * The second case matters just as much: keyed, but the provider returns
   * nothing (off season, outage). All three levels null means "no data", not
   * "low", so it degrades the same way.
   */
  const pollenUnavailable =
    env?.pollen_is_sample === true ||
    (env !== null &&
      env.pollen.tree === null &&
      env.pollen.grass === null &&
      env.pollen.weed === null);

  if (envError && !env) {
    // The environment and the hospital lookup are separate providers, so one
    // of them being down must not take the other with it. Nearby care is the
    // part you need most when the pollen feed is broken, so the error goes in
    // the page and the hospital section still renders below it.
    return (
      <>
        <h2 className="vt">Today</h2>
        <p className="vsub">Pollen, air quality and your risk score for today.</p>
        <div className="note">
          <span>Could not load environment: {envError}</span>
        </div>
        <HospitalSection hospitals={hospitals} error={hospitalsError} />
      </>
    );
  }

  return (
    <>
      <h2 className="vt">Today</h2>
      <p className="vsub">Pollen, air quality and your risk score for today.</p>

      {env ? (
        <section className="risk-card" aria-label="Current risk">
          <div className="risk-head">
            <span className={`risk-dot ${riskClass(env.risk)}`} aria-hidden="true" />
            <span className="risk-label">{formatRisk(env.risk)}</span>
            {env.risk !== null && (
              <span className="risk-points">{formatPoints(env.points)} pts</span>
            )}
          </div>

          {env.risk === null && (
            <div className="note">
              <span>
                None of the providers answered, so there is no risk score to
                show. That is not the same as low risk.
              </span>
            </div>
          )}

          {env.pollen_is_sample && (
            <div className="note">
              <span>
                Live pollen data is not connected yet, so today&apos;s pollen
                levels are withheld rather than shown as an estimate, and the
                pollen is not part of the score above. Add the data.go.kr
                pollen key in <code>backend/.env</code> to see real values.
              </span>
            </div>
          )}

          <ul className="metric-list">
            {pollenUnavailable ? (
              <li>
                <span>Pollen</span>
                <b>Unavailable</b>
              </li>
            ) : (
              <>
                <li>
                  <span>Tree pollen</span>
                  <b>{formatPollen(env.pollen.tree)}</b>
                </li>
                <li>
                  <span>Grass pollen</span>
                  <b>{formatPollen(env.pollen.grass)}</b>
                </li>
                <li>
                  <span>Weed pollen</span>
                  <b>{formatPollen(env.pollen.weed)}</b>
                </li>
              </>
            )}
            <li>
              <span>PM2.5</span>
              <b>{env.air_quality.pm25 ?? "—"} µg/m³</b>
            </li>
            <li>
              <span>PM10</span>
              <b>{env.air_quality.pm10 ?? "—"} µg/m³</b>
            </li>
            <li>
              <span>Temperature</span>
              <b>{env.weather.temperature ?? "—"} °C</b>
            </li>
            <li>
              <span>Humidity</span>
              <b>{env.weather.humidity ?? "—"} %</b>
            </li>
            <li>
              <span>Wind</span>
              <b>{env.weather.wind ?? "—"} m/s</b>
            </li>
          </ul>
        </section>
      ) : null}

      <HospitalSection hospitals={hospitals} error={hospitalsError} />
    </>
  );
}

/**
 * Nearby care. It sits in its own component because the hospital lookup has to
 * survive a broken environment provider: the user who cannot see a pollen
 * count is the user who needs to know which clinic is close.
 */
function HospitalSection({
  hospitals,
  error,
}: {
  hospitals: HospitalNearbyResponse | null;
  error: string | null;
}) {
  return (
    <section className="hospital-section" aria-label="Nearby hospitals">
      <h3 className="vsect">Nearby care</h3>
      {error && (
        <div className="note">
          <span>Could not load nearby hospitals: {error}</span>
        </div>
      )}
      {hospitals && !hospitals.provider_available && (
        <div className="note">
          <span>
            Hospital search is offline — add the Naver client id and secret in{" "}
            <code>backend/.env</code> to enable nearby results.
          </span>
        </div>
      )}
      {hospitals && hospitals.provider_available && hospitals.count === 0 && (
        <div className="note">
          <span>No hospitals found within range.</span>
        </div>
      )}
      {hospitals && hospitals.results.length > 0 && (
        <ul className="hospital-list">
          {hospitals.results.map((h) => (
            <li key={`${h.rank}-${h.name}`} className="hospital-row">
              <div className="hospital-head">
                <b>{h.name}</b>
                <span className="hospital-dist">{formatDistance(h.distance_m)}</span>
              </div>
              {h.address && <div className="hospital-addr">{h.address}</div>}
              <div className="hospital-meta">
                {h.specialty && <span>{h.specialty}</span>}
                {h.phone && <span> · {h.phone}</span>}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function toMessage(err: unknown): string {
  if (err instanceof ApiError) return err.detail;
  if (err instanceof Error) return err.message;
  return "Unknown error";
}
