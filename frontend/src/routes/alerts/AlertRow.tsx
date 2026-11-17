/**
 * One row of the Alerts list. A run of identical alerts renders as one row with
 * a count badge; expanding it lists each alert in the run.
 */
import { useState } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Bell, ChevronDown, CloudSun, Flower2, Wind } from "lucide-react";

import type { AlertResponse } from "../../api/types";
import { formatRisk, riskClass } from "../../utils/format";
import { isEnvironmentAlert, relativeAgo, typeLabel } from "./alertModel";
import type { AlertRun } from "./alertModel";

function alertIcon(alertType: string): ReactNode {
  const key = alertType.toUpperCase();
  const Icon =
    key === "POLLEN"
      ? Flower2
      : key === "AIR_QUALITY"
        ? Wind
        : key === "WEATHER"
          ? CloudSun
          : Bell;
  return <Icon className="size-[18px]" aria-hidden="true" />;
}

interface AlertRowProps {
  run: AlertRun;
  now: Date;
  pendingIds: ReadonlySet<number>;
  onMarkRead: (ids: number[]) => void;
}

export function AlertRow({ run, now, pendingIds, onMarkRead }: AlertRowProps) {
  const [expanded, setExpanded] = useState(false);
  const head = run.items[0];
  const count = run.items.length;
  const isRun = count > 1;
  const isRead = run.unread === 0;
  const tone = riskClass(head.risk_level);
  const pending = run.items.some((a) => pendingIds.has(a.id));

  const markRun = () => {
    const unreadIds = run.items.filter((a) => !a.is_read).map((a) => a.id);
    if (unreadIds.length > 0) onMarkRead(unreadIds);
  };

  // A single alert: tapping the text expands it and marks it read, the way the
  // screen always has. A run only expands, so one tap never marks five alerts.
  const onBodyTap = () => {
    setExpanded((v) => !v);
    if (!isRun && !head.is_read) markRun();
  };

  return (
    <li className={`al-row level-${tone} ${isRead ? "is-read" : "is-unread"}`} aria-busy={pending}>
      <span className="al-tile" aria-hidden="true">
        {alertIcon(head.alert_type)}
      </span>

      <div className="al-main">
        <button type="button" className="al-msg-btn" aria-expanded={expanded} onClick={onBodyTap}>
          <span className={`al-msg${expanded ? " is-open" : ""}`}>{head.message}</span>
          <span className="al-meta">
            <span className="al-chip-level">{formatRisk(head.risk_level)}</span>
            <time dateTime={head.created_at}>{relativeAgo(head.created_at, now)}</time>
            <span aria-hidden="true">·</span>
            <span>{typeLabel(head.alert_type)}</span>
            {isRun && (
              <span className="al-count-badge" aria-label={`${count} alerts`}>
                x{count}
              </span>
            )}
            <ChevronDown className={`al-chevron${expanded ? " is-open" : ""}`} aria-hidden="true" />
          </span>
        </button>

        <div className="al-actions">
          {isEnvironmentAlert(head.alert_type) && (
            <Link to="/today" className="al-action al-action--primary">
              Open Today
            </Link>
          )}
          {!isRead && (
            <button type="button" className="al-action" onClick={markRun} disabled={pending}>
              {isRun ? `Mark ${run.unread} read` : "Mark read"}
            </button>
          )}
        </div>

        {isRun && expanded && (
          <ul className="al-sub" aria-label={`${count} alerts with this message`}>
            {run.items.map((a) => (
              <SubItem key={a.id} alert={a} now={now} pending={pendingIds.has(a.id)} onMarkRead={onMarkRead} />
            ))}
          </ul>
        )}
      </div>

      {!isRead && <span className="al-dot" role="img" aria-label={`${run.unread} unread`} />}
    </li>
  );
}

function SubItem({
  alert,
  now,
  pending,
  onMarkRead,
}: {
  alert: AlertResponse;
  now: Date;
  pending: boolean;
  onMarkRead: (ids: number[]) => void;
}) {
  return (
    <li className={`al-sub-item ${alert.is_read ? "is-read" : "is-unread"}`}>
      <time dateTime={alert.created_at}>{relativeAgo(alert.created_at, now)}</time>
      {alert.is_read ? (
        <span className="al-read-label">Read</span>
      ) : (
        <button type="button" className="al-action" disabled={pending} onClick={() => onMarkRead([alert.id])}>
          Mark read
        </button>
      )}
    </li>
  );
}
