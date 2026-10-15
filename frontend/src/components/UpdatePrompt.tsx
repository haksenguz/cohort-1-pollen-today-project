/**
 * New-version notification. Listens for the SW update event from
 * vite-plugin-pwa's virtual:pwa-register/react module and fires a toast with a
 * Refresh action. Clicking calls updateServiceWorker(true), which reloads the
 * page onto the fresh SW.
 *
 * iOS PWA users have a longer reload cycle because the OS caches resources
 * aggressively — this gives them a clear "tap to update" signal instead of
 * the silent autoUpdate reload.
 *
 * Renders nothing of its own; the shared Toaster in AppShell owns the chrome.
 */
import { useRegisterSW } from "virtual:pwa-register/react";
import { useEffect, useRef } from "react";
import { toast } from "sonner";

export function UpdatePrompt() {
  const announced = useRef(false);
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
    if (!needRefresh || announced.current) return;
    announced.current = true;

    toast("A new version is ready.", {
      // An update the user never applies is an update they never get, so this
      // waits for a decision instead of timing out.
      duration: Infinity,
      action: {
        label: "Refresh",
        onClick: () => {
          void updateServiceWorker(true);
        },
      },
      cancel: {
        label: "Later",
        onClick: () => setNeedRefresh(false),
      },
    });
  }, [needRefresh, setNeedRefresh, updateServiceWorker]);

  return null;
}
