/**
 * Tiny offline detector. Listens to window online/offline events and
 * surfaces a banner when the device has no network. The PWA still runs
 * because the SW precaches the shell; some /api/* calls will fail and
 * show their own errors per page.
 */
import { useEffect, useState } from "react";

export function OfflineBanner() {
  const [online, setOnline] = useState<boolean>(
    typeof navigator === "undefined" ? true : navigator.onLine,
  );

  useEffect(() => {
    const goOnline = () => setOnline(true);
    const goOffline = () => setOnline(false);
    window.addEventListener("online", goOnline);
    window.addEventListener("offline", goOffline);
    return () => {
      window.removeEventListener("online", goOnline);
      window.removeEventListener("offline", goOffline);
    };
  }, []);

  if (online) return null;

  return (
    <div className="pwa-offline" role="status" aria-live="polite">
      You are offline. Showing the last known data.
    </div>
  );
}