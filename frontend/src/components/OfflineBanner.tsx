/**
 * Offline notification. Listens to window online/offline events and fires a
 * toast when the device loses the network. The PWA still runs because the SW
 * precaches the shell; some /api/* calls will fail and show their own errors
 * per page.
 *
 * Renders nothing of its own; the shared Toaster in AppShell owns the chrome.
 * The old version was a fixed bar pinned to the top of the viewport, which
 * pushed the whole page down every time the connection flickered.
 */
import { useEffect } from "react";
import { toast } from "sonner";

const OFFLINE_TOAST_ID = "offline";

export function OfflineBanner() {
  useEffect(() => {
    const goOnline = () => toast.dismiss(OFFLINE_TOAST_ID);
    const goOffline = () => {
      toast("You are offline.", {
        id: OFFLINE_TOAST_ID,
        description: "Showing the last known data. Alerts resume when you reconnect.",
        // Stays put while offline: a notification that vanishes on a timer is
        // one the user never reads.
        duration: Infinity,
      });
    };

    // The app can mount while already offline (a cold PWA launch with no
    // network), in which case no 'offline' event will ever fire.
    if (typeof navigator !== "undefined" && !navigator.onLine) goOffline();

    window.addEventListener("online", goOnline);
    window.addEventListener("offline", goOffline);
    return () => {
      window.removeEventListener("online", goOnline);
      window.removeEventListener("offline", goOffline);
    };
  }, []);

  return null;
}
