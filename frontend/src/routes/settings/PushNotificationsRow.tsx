/**
 * The "Push notifications" switch on the Notifications screen. It shows the
 * real state (unsupported, blocked, off, on) instead of a bare toggle, so a
 * user who cannot turn it on learns why.
 */
import { useEffect, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

import {
  disablePush,
  enablePush,
  getPushState,
  PushNotConfiguredError,
  type PushState,
} from "../../utils/push";

const STATUS_TEXT: Record<PushState, string> = {
  unsupported:
    "This browser cannot receive push notifications. On iPhone, add the app to your Home Screen first.",
  denied: "Blocked in your browser settings. Allow notifications for this site to turn them on.",
  off: "Off. Alerts arrive only while the app is open.",
  on: "On. You get alerts even when the app is closed.",
};

export function PushNotificationsRow() {
  const [state, setState] = useState<PushState | null>(null);
  const [busy, setBusy] = useState(false);
  const [notConfigured, setNotConfigured] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getPushState()
      .then((next) => {
        if (!cancelled) setState(next);
      })
      .catch(() => {
        if (!cancelled) setState("off");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function toggle(checked: boolean) {
    setError(null);
    setNotConfigured(false);
    setBusy(true);
    try {
      if (checked) {
        await enablePush();
      } else {
        await disablePush();
      }
    } catch (e) {
      if (e instanceof PushNotConfiguredError) {
        setNotConfigured(true);
      } else {
        setError(e instanceof Error && e.message ? e.message : "Could not change push notifications.");
      }
    } finally {
      setState(await getPushState().catch((): PushState => "off"));
      setBusy(false);
    }
  }

  const unavailable = state === "unsupported" || state === "denied";
  const statusText = notConfigured
    ? "Not set up on the server yet, so it cannot be turned on."
    : state === null
      ? "Checking status."
      : STATUS_TEXT[state];

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-start gap-3">
        <span className="flex min-h-11 min-w-11 items-center justify-center">
          <Switch
            id="push-notifications"
            aria-label="Push notifications"
            aria-describedby="push-status"
            checked={state === "on"}
            disabled={busy || state === null || unavailable || notConfigured}
            onCheckedChange={(checked) => void toggle(checked)}
          />
        </span>
        <div className="flex flex-col gap-0.5">
          <Label htmlFor="push-notifications">Push notifications</Label>
          <p id="push-status" className="text-xs text-muted-foreground">
            {statusText}
          </p>
        </div>
      </div>
      {error ? (
        <Alert variant="destructive">
          <AlertTitle>Not changed</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}
    </div>
  );
}
