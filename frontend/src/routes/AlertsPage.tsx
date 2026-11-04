/**
 * Alerts screen (I6). Lists the user's stored alerts, lets them mark
 * an alert as read, and toggles between "all" and "unread only" via
 * the backend's `unread_only` query parameter.
 *
 * The alerts read as one list, the way ChatGPT draws its notification and
 * activity lists: a leading icon, the alert text, and the meta (the time and
 * the level) on one line under it. The alert text is the server's, word for
 * word.
 */
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Bell, CloudSun, Flower2, Wind } from "lucide-react";

import { ApiError, listAlerts, markAlertRead } from "../api/client";
import type { AlertResponse } from "../api/types";
import { formatRelativeTime, formatRisk, riskClass } from "../utils/format";

/**
 * The leading icon for an alert. The kind of the alert picks the icon, so a
 * pollen alert does not look like a weather one.
 */
function alertIcon(alertType: string): ReactNode {
  const key = alertType.toUpperCase();
  const Icon = key.includes("POLLEN")
    ? Flower2
    : key.includes("AIR_QUALITY") || key.startsWith("PM")
      ? Wind
      : key.includes("WEATHER")
        ? CloudSun
        : Bell;
  return <Icon className="size-4" aria-hidden="true" />;
}

export function AlertsPage() {
  const [alerts, setAlerts] = useState<AlertResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [pendingId, setPendingId] = useState<number | null>(null);

  // No poll here. Background delivery (B-010) is mounted once in AppShell, above
  // the router, because the whole point of an alert is to reach you while you
  // are on Chat or Today — polling from this screen would only ever notify you
  // when you were already looking at the alerts. This page's own list, its
  // filter and markAlertRead stay local, and the hook holds no alert state, so
  // a tick cannot clobber `alerts` or race markAlertRead below.

  useEffect(() => {
    let cancelled = false;
    // oxlint-disable-next-line react/set-state-in-effect -- reset-before-refetch on filter change
    setError(null);
    setAlerts(null);

    listAlerts({ unreadOnly })
      .then((data) => {
        if (cancelled) return;
        setAlerts(data);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(toMessage(err));
      });

    return () => {
      cancelled = true;
    };
  }, [unreadOnly]);

  const onRowClick = async (id: number) => {
    setPendingId(id);
    try {
      const updated = await markAlertRead(id);
      setAlerts((current) =>
        current === null
          ? current
          : current.map((a) => (a.id === id ? updated : a)),
      );
    } catch (err) {
      setError(toMessage(err));
    } finally {
      setPendingId(null);
    }
  };

  if (error && alerts === null) {
    return (
      <>
        <h2 className="vt">Alerts</h2>
        <p className="vsub">Environmental warnings matched to your allergy profile.</p>
        <div className="note">
          <span>Could not load alerts: {error}</span>
        </div>
      </>
    );
  }

  if (alerts === null) {
    return (
      <div className="screen-loading" role="status" aria-live="polite">
        Loading alerts…
      </div>
    );
  }

  return (
    <>
      <h2 className="vt">Alerts</h2>
      <p className="vsub">Environmental warnings matched to your allergy profile.</p>

      <div className="filter-row">
        <label className="filter-toggle">
          <input
            type="checkbox"
            checked={unreadOnly}
            onChange={(e) => setUnreadOnly(e.target.checked)}
            aria-label="Unread only"
          />
          <span>Unread only</span>
        </label>
      </div>

      {alerts.length === 0 ? (
        <div className="note">
          <span>
            No alerts yet. One is created when the environment crosses your
            threshold, and the app picks it up while it is open.
          </span>
        </div>
      ) : (
        <ul className="alert-list">
          {alerts.map((a) => (
            <li
              key={a.id}
              className={`alert-row ${a.is_read ? "is-read" : "is-unread"}`}
              onClick={() => {
                if (!a.is_read && pendingId === null) void onRowClick(a.id);
              }}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if ((e.key === "Enter" || e.key === " ") && !a.is_read && pendingId === null) {
                  e.preventDefault();
                  void onRowClick(a.id);
                }
              }}
              aria-busy={pendingId === a.id}
            >
              <span className="alert-icon">{alertIcon(a.alert_type)}</span>
              <span className="alert-body">
                <span className="alert-msg">{a.message}</span>
                <span className="alert-meta">
                  <span className={`risk-dot ${riskClass(a.risk_level)}`} aria-hidden="true" />
                  <span>{formatRelativeTime(a.created_at)}</span>
                  <span aria-hidden="true">·</span>
                  <span>{formatRisk(a.risk_level)}</span>
                  <span aria-hidden="true">·</span>
                  <span className="alert-type">{a.alert_type.replace(/_/g, " ").toLowerCase()}</span>
                </span>
              </span>
            </li>
          ))}
        </ul>
      )}

      {error && (
        <div className="note">
          <span>{error}</span>
        </div>
      )}
    </>
  );
}

function toMessage(err: unknown): string {
  if (err instanceof ApiError) return err.detail;
  if (err instanceof Error) return err.message;
  return "Unknown error";
}
