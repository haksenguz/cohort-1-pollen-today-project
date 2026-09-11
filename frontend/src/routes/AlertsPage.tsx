/**
 * Alerts screen (I6). Lists the user's stored alerts, lets them mark
 * an alert as read, and toggles between "all" and "unread only" via
 * the backend's `unread_only` query parameter.
 */
import { useEffect, useState } from "react";

import { ApiError, listAlerts, markAlertRead } from "../api/client";
import type { AlertResponse } from "../api/types";
import { formatRelativeTime, formatRisk, riskClass } from "../utils/format";

export function AlertsPage() {
  const [alerts, setAlerts] = useState<AlertResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [pendingId, setPendingId] = useState<number | null>(null);

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
          <span>No alerts yet. We will notify you when the environment crosses your threshold.</span>
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
              <div className="alert-head">
                <span className={`risk-dot ${riskClass(a.risk_level)}`} aria-hidden="true" />
                <b>{formatRisk(a.risk_level)}</b>
                <span className="alert-type">{a.alert_type.replace(/_/g, " ").toLowerCase()}</span>
                <span className="alert-time">{formatRelativeTime(a.created_at)}</span>
              </div>
              <div className="alert-msg">{a.message}</div>
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
