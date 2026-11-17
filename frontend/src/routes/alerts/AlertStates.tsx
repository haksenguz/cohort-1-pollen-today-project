/** Loading, error, and empty states for the Alerts screen. */
import { Link } from "react-router-dom";
import { CircleCheck, Filter, RefreshCw, TriangleAlert } from "lucide-react";

export function AlertsSkeleton() {
  return (
    <div className="al-list" role="status" aria-live="polite">
      <span className="sr-only">Loading alerts</span>
      {[0, 1, 2].map((i) => (
        <span key={i} className="al-skel" aria-hidden="true" />
      ))}
    </div>
  );
}

export function AlertsError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="al-empty" role="alert">
      <span className="al-empty-icon al-empty-icon--warn">
        <TriangleAlert className="size-6" aria-hidden="true" />
      </span>
      <p className="al-empty-title">Could not load alerts</p>
      <p className="al-empty-text">{message}</p>
      <button type="button" className="al-btn al-btn--accent" onClick={onRetry}>
        <RefreshCw className="size-4" aria-hidden="true" />
        Retry
      </button>
    </div>
  );
}

export function AlertsCaughtUp() {
  return (
    <div className="al-empty">
      <span className="al-empty-icon">
        <CircleCheck className="size-6" aria-hidden="true" />
      </span>
      <p className="al-empty-title">You are all caught up</p>
      <p className="al-empty-text">
        Alerts appear here when pollen, air quality or weather crosses your thresholds.
      </p>
      <Link to="/settings?screen=notifications" className="al-action al-action--primary">
        Notification settings
      </Link>
    </div>
  );
}

export function AlertsNoMatch({ label, onShowAll }: { label: string; onShowAll: () => void }) {
  return (
    <div className="al-empty">
      <span className="al-empty-icon">
        <Filter className="size-6" aria-hidden="true" />
      </span>
      <p className="al-empty-title">{label}</p>
      <button type="button" className="al-btn" onClick={onShowAll}>
        Show all alerts
      </button>
    </div>
  );
}
