/**
 * New-version toast. Listens for the SW update event from vite-plugin-pwa's
 * virtual:pwa-register/react module and shows a small toast with a Refresh
 * button. Clicking calls updateServiceWorker(true) which reloads the page
 * onto the fresh SW.
 *
 * iOS PWA users have a longer reload cycle because the OS caches resources
 * aggressively — this toast gives them a clear "tap to update" signal
 * instead of the silent autoUpdate reload.
 */
import { useRegisterSW } from "virtual:pwa-register/react";
import { useEffect, useState } from "react";

export function UpdatePrompt() {
  const [visible, setVisible] = useState(false);
  const {
    needRefresh: [needRefresh, setNeedRefresh],
    updateServiceWorker,
  } = useRegisterSW({
    onRegisteredSW() {
      // Don't surface offline-ready here — InstallPrompt covers that.
    },
    onRegisterError() {
      // Service worker registration failed (likely iOS private mode).
      // Stay quiet; the rest of the app still works.
    },
  });

  useEffect(() => {
    setVisible(Boolean(needRefresh));
  }, [needRefresh]);

  if (!visible) return null;

  return (
    <div className="pwa-toast" role="alert" aria-live="polite">
      <span>A new version is ready.</span>
      <button
        type="button"
        className="pwa-toast-btn"
        onClick={() => {
          void updateServiceWorker(true);
        }}
      >
        Refresh
      </button>
      <button
        type="button"
        className="pwa-toast-x"
        aria-label="Dismiss update"
        onClick={() => {
          setNeedRefresh(false);
          setVisible(false);
        }}
      >
        ×
      </button>
    </div>
  );
}