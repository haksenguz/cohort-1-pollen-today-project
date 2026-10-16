/**
 * useAlertPolling — background delivery for alerts while the app is open.
 *
 * B-010, stopgap option (a). The backend writes alert rows on a 60-minute
 * APScheduler cadence, but the only way to learn one existed was to open
 * /alerts. This polls GET /api/alerts and toasts any unread alert that
 * appeared *after* the first successful load.
 *
 * Deliberately NOT web push (option b): a service-worker push handler and a
 * Notification permission prompt change the permission story and need a
 * product decision. This hook only runs while a document is open.
 *
 * Mount it once, near the app root. The seen-set and the timer live at module
 * scope rather than in component state, so an extra mount (a route-level one,
 * say) costs no extra requests and can never toast the same alert twice — and
 * an alert that arrives while the user is on another screen is still toasted
 * after a remount.
 *
 * Options, all explicit:
 *   intervalMs    default 60_000, matching the backend's CHECK_INTERVAL_MINUTES
 *                 so the app polls about as often as the backend can produce
 *                 something new. A spiky pollen hour is real, but not worth a
 *                 battery-flattening poll on a phone.
 *   pollOnMount   default false. The first load is the *baseline*: those alerts
 *                 predate this hook, so they are never toasted. Turn it on when
 *                 the caller wants that baseline immediately instead of one
 *                 interval in.
 *   pollOnVisible default true. Becoming visible fires one immediate poll
 *                 before the interval resumes — the user may have backgrounded
 *                 the app across an entire alert window.
 *   enabled       default true. False mounts nothing and polls nothing.
 *
 * The hook holds no alert state of its own, so it cannot race a screen's own
 * fetch or clobber a markAlertRead PATCH with a stale list. Toasts are the only
 * thing that leaves this module.
 */
import { useCallback, useEffect } from "react";
import { toast } from "sonner";

import { listAlerts } from "../api/client";
import type { AlertResponse } from "../api/types";
import { formatRisk } from "../utils/format";

export const ALERT_POLL_INTERVAL_MS = 60_000;

export interface AlertPollingOptions {
  intervalMs?: number;
  pollOnMount?: boolean;
  pollOnVisible?: boolean;
  enabled?: boolean;
}

export interface AlertPolling {
  /** Poll right now. Fires even while the document is visible-gated off. */
  pollNow: () => void;
}

// ---- module-scoped loop state ------------------------------------------

/** Ids already accounted for — either toasted or absorbed into the baseline. */
const seenAlertIds = new Set<number>();
/** False until the first successful load; that load is never toasted. */
let baselineTaken = false;
let timer: ReturnType<typeof setInterval> | null = null;
let mountCount = 0;
let inFlight = false;

function stopLoop(): void {
  if (timer !== null) {
    clearInterval(timer);
    timer = null;
  }
}

function startLoop(intervalMs: number): void {
  stopLoop();
  timer = setInterval(() => {
    void poll();
  }, intervalMs);
}

async function poll(): Promise<void> {
  // One request in flight at a time: on a slow network an interval tick must
  // not stack up behind the previous one.
  if (inFlight) return;
  inFlight = true;
  try {
    announce(await listAlerts());
  } catch {
    // A background poll has no user-facing surface to fail onto, and the next
    // tick retries anyway. Surfacing it would be noise the user cannot act on.
  } finally {
    inFlight = false;
  }
}

function announce(alerts: AlertResponse[]): void {
  for (const alert of alerts) {
    if (seenAlertIds.has(alert.id)) continue;
    // Record it either way. An alert already read elsewhere is seen, and
    // re-checking it on every tick would be the only way to notice.
    seenAlertIds.add(alert.id);
    if (!baselineTaken || alert.is_read) continue;
    toastAlert(alert);
  }
  baselineTaken = true;
}

function toastAlert(alert: AlertResponse): void {
  // Stable id: sonner replaces rather than stacks, so a re-poll can never
  // leave two copies of the same alert on screen.
  const options = {
    id: `alert-${alert.id}`,
    description: `${formatRisk(alert.risk_level)} · ${alert.alert_type.replace(/_/g, " ").toLowerCase()}`,
  };

  if (alert.risk_level === "EMERGENCY") {
    // Same call as OfflineBanner's: a warning that expires on a timer is one
    // the user never reads.
    toast.error(alert.message, { ...options, duration: Infinity });
  } else if (alert.risk_level === "HIGH") {
    toast.warning(alert.message, { ...options, duration: Infinity });
  } else {
    toast(alert.message, options);
  }
}

// ---- the hook -----------------------------------------------------------

/**
 * Starts alert polling for as long as the calling component is mounted.
 * Mount once at the app root; extra mounts are harmless by design.
 */
export function useAlertPolling(options: AlertPollingOptions = {}): AlertPolling {
  const {
    intervalMs = ALERT_POLL_INTERVAL_MS,
    pollOnMount = false,
    pollOnVisible = true,
    enabled = true,
  } = options;

  const pollNow = useCallback(() => {
    void poll();
  }, []);

  useEffect(() => {
    if (!enabled) return;

    mountCount += 1;
    if (document.visibilityState !== "hidden") startLoop(intervalMs);
    if (pollOnMount) pollNow();

    const onVisibilityChange = () => {
      if (document.visibilityState === "hidden") {
        stopLoop();
        return;
      }
      startLoop(intervalMs);
      if (pollOnVisible) pollNow();
    };
    document.addEventListener("visibilitychange", onVisibilityChange);

    return () => {
      document.removeEventListener("visibilitychange", onVisibilityChange);
      mountCount -= 1;
      if (mountCount === 0) stopLoop();
    };
  }, [enabled, intervalMs, pollNow, pollOnMount, pollOnVisible]);

  return { pollNow };
}