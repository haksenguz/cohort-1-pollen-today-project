/**
 * Alerts inbox. Fetches the user's alerts once, then filters, groups and marks
 * read on the client, so the unread count and the chips never disagree with
 * the list. Marking read is optimistic: the row changes at once and goes back
 * if the server refuses.
 */
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { RefreshCw, Settings } from "lucide-react";

import { ApiError, listAlerts, markAlertRead } from "../api/client";
import type { AlertResponse } from "../api/types";
import { AlertFilters, buildFilterOptions } from "./alerts/AlertFilters";
import { AlertRow } from "./alerts/AlertRow";
import {
  AlertsCaughtUp,
  AlertsError,
  AlertsNoMatch,
  AlertsSkeleton,
} from "./alerts/AlertStates";
import {
  collapseRuns,
  filterAlerts,
  groupByDay,
  typeLabel,
  typesPresent,
} from "./alerts/alertModel";

export function AlertsPage() {
  const [alerts, setAlerts] = useState<AlertResponse[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [filter, setFilter] = useState("all");
  const [pendingIds, setPendingIds] = useState<ReadonlySet<number>>(new Set());
  const [reloadKey, setReloadKey] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const [now, setNow] = useState<Date>(() => new Date());

  // Ids with a PATCH in flight. A ref, not state, so two taps in one tick
  // cannot both send the same request.
  const pendingRef = useRef(new Set<number>());

  // No poll here. Background delivery is mounted once in AppShell, above the
  // router. This page loads its own list and reloads only on Refresh/Retry.
  useEffect(() => {
    let cancelled = false;
    listAlerts()
      .then((data) => {
        if (cancelled) return;
        setAlerts(data);
        setLoadError(null);
        setNow(new Date());
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setLoadError(toMessage(err));
      })
      .finally(() => {
        if (!cancelled) setRefreshing(false);
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  const refresh = () => {
    setRefreshing(true);
    setReloadKey((k) => k + 1);
  };

  const markRead = (ids: number[]) => {
    const targets = ids.filter((id) => !pendingRef.current.has(id));
    if (targets.length === 0) return;
    targets.forEach((id) => pendingRef.current.add(id));
    setPendingIds(new Set(pendingRef.current));
    setAlerts((cur) =>
      cur ? cur.map((a) => (targets.includes(a.id) ? { ...a, is_read: true } : a)) : cur,
    );

    let failed = 0;
    void Promise.allSettled(
      targets.map(async (id) => {
        try {
          const updated = await markAlertRead(id);
          setAlerts((cur) => (cur ? cur.map((a) => (a.id === id ? updated : a)) : cur));
        } catch {
          failed += 1;
          setAlerts((cur) =>
            cur ? cur.map((a) => (a.id === id ? { ...a, is_read: false } : a)) : cur,
          );
        } finally {
          pendingRef.current.delete(id);
          setPendingIds(new Set(pendingRef.current));
        }
      }),
    ).then(() => {
      if (failed > 0) {
        setNotice(
          failed === 1
            ? "One alert could not be marked read. Try again."
            : `${failed} alerts could not be marked read. Try again.`,
        );
      }
    });
  };

  const list = alerts ?? [];
  const unreadCount = list.filter((a) => !a.is_read).length;
  const options = buildFilterOptions(list, typesPresent(list));
  const groups = groupByDay(collapseRuns(filterAlerts(list, filter)), now);
  const activeLabel = options.find((o) => o.key === filter)?.label ?? typeLabel(filter);

  const toolbar = (
    <div className="al-toolbar">
      <h2 className="sr-only">Alerts</h2>
      <p className="al-subtitle">Environmental warnings matched to your allergy profile.</p>
      <div className="al-toolbar-actions">
        <button
          type="button"
          className="al-icon-btn"
          onClick={refresh}
          disabled={refreshing}
          aria-label="Refresh alerts"
        >
          <RefreshCw className={`size-[18px]${refreshing ? " al-spin" : ""}`} aria-hidden="true" />
        </button>
        <Link to="/settings?screen=notifications" className="al-icon-btn" aria-label="Notification settings">
          <Settings className="size-[18px]" aria-hidden="true" />
        </Link>
      </div>
    </div>
  );

  if (alerts === null) {
    return (
      <div className="al-page">
        {toolbar}
        {loadError ? (
          <AlertsError message={loadError} onRetry={refresh} />
        ) : (
          <AlertsSkeleton />
        )}
      </div>
    );
  }

  return (
    <div className="al-page">
      {toolbar}

      {list.length === 0 ? (
        <>
          {loadError && <Notice text={loadError} onRetry={refresh} />}
          <AlertsCaughtUp />
        </>
      ) : (
        <>
          <section className="al-summary" aria-label="Alert summary">
            <p className="al-count" aria-live="polite">
              {unreadCount > 0 ? `${unreadCount} unread` : "All read"}
            </p>
            <button
              type="button"
              className="al-btn al-btn--accent"
              onClick={() => markRead(list.filter((a) => !a.is_read).map((a) => a.id))}
              disabled={unreadCount === 0}
            >
              Mark all read
            </button>
          </section>

          <AlertFilters options={options} active={filter} onSelect={setFilter} />

          {loadError && <Notice text={loadError} onRetry={refresh} />}
          {notice && <Notice text={notice} onDismiss={() => setNotice(null)} />}

          {groups.length === 0 ? (
            <AlertsNoMatch
              label={filter === "unread" ? "No unread alerts" : `No ${activeLabel.toLowerCase()} alerts`}
              onShowAll={() => setFilter("all")}
            />
          ) : (
            groups.map((group) => (
              <section key={group.label} className="al-day" aria-labelledby={`al-day-${group.label}`}>
                <h3 className="al-day-title" id={`al-day-${group.label}`}>
                  {group.label}
                </h3>
                <ul className="al-list">
                  {group.runs.map((run) => (
                    <AlertRow
                      key={run.key}
                      run={run}
                      now={now}
                      pendingIds={pendingIds}
                      onMarkRead={markRead}
                    />
                  ))}
                </ul>
              </section>
            ))
          )}
        </>
      )}
    </div>
  );
}

function Notice({
  text,
  onRetry,
  onDismiss,
}: {
  text: string;
  onRetry?: () => void;
  onDismiss?: () => void;
}) {
  return (
    <div className="al-notice" role="alert">
      <span>{text}</span>
      {onRetry && (
        <button type="button" className="al-action" onClick={onRetry}>
          Retry
        </button>
      )}
      {onDismiss && (
        <button type="button" className="al-action" onClick={onDismiss}>
          Dismiss
        </button>
      )}
    </div>
  );
}

function toMessage(err: unknown): string {
  if (err instanceof ApiError) return err.detail;
  if (err instanceof Error) return err.message;
  return "Unknown error";
}
