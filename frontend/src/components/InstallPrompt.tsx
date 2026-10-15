/**
 * Captures the browser's beforeinstallprompt event and surfaces an "Install the
 * app" notification. iOS Safari does NOT fire beforeinstallprompt — for iOS
 * users the notification is a one-line hint to use Safari's Share → "Add to
 * Home Screen" instead. We detect iOS via userAgent + the standalone-mode
 * check.
 *
 * This component renders nothing of its own. It fires toasts into the shared
 * Toaster mounted in AppShell, because the hand-rolled .pwa-toast panel it
 * used to render was fixed to the bottom of the viewport, where it sat on top
 * of the tab nav and of primary actions (it covered the "Save key" button on
 * /login). It also had no auto-dismiss and no stacking.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

interface BeforeInstallPromptEvent extends Event {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

/** The iOS hint is informational, so it leaves on its own. */
const IOS_HINT_MS = 8000;

function isIosDevice(): boolean {
  if (typeof navigator === "undefined") return false;
  const ua = navigator.userAgent || "";
  return /iPad|iPhone|iPod/.test(ua) && !/CriOS|FxiOS|EdgiOS/.test(ua);
}

function isStandalone(): boolean {
  if (typeof window === "undefined") return false;
  // iOS uses navigator.standalone; Android/Chrome use display-mode media.
  const iosStandalone =
    typeof (navigator as Navigator & { standalone?: boolean }).standalone ===
    "boolean"
      ? (navigator as Navigator & { standalone?: boolean }).standalone === true
      : false;
  const mediaStandalone =
    typeof window.matchMedia === "function" &&
    window.matchMedia("(display-mode: standalone)").matches;
  return Boolean(iosStandalone || mediaStandalone);
}

const STORAGE_KEY = "allergy_pwa_install_dismissed_at";
const COOLDOWN_MS = 7 * 24 * 60 * 60 * 1000; // 7 days

export function InstallPrompt() {
  const [deferred, setDeferred] = useState<BeforeInstallPromptEvent | null>(null);
  const [installed, setInstalled] = useState<boolean>(false);
  const [dismissed, setDismissed] = useState<boolean>(true); // start hidden
  const [showIosHint, setShowIosHint] = useState<boolean>(false);
  // One toast per trigger. Without this, any re-render that lands on the same
  // state would fire a duplicate.
  const announced = useRef<string | null>(null);

  const isIos = useMemo(isIosDevice, []);
  const standalone = useMemo(isStandalone, []);

  useEffect(() => {
    if (standalone) {
      setInstalled(true);
      return;
    }

    // Already-installed or recently-dismissed? Don't pester.
    try {
      const ts = localStorage.getItem(STORAGE_KEY);
      if (ts && Date.now() - Number(ts) < COOLDOWN_MS) {
        setDismissed(true);
      } else {
        setDismissed(false);
      }
    } catch {
      setDismissed(false);
    }
  }, [standalone]);

  useEffect(() => {
    if (isIos && !standalone) {
      // iOS path: surface the Share hint once per session.
      setShowIosHint(true);
      return;
    }
    const handler = (e: Event) => {
      e.preventDefault();
      setDeferred(e as BeforeInstallPromptEvent);
    };
    window.addEventListener("beforeinstallprompt", handler);
    const installedHandler = () => {
      setInstalled(true);
      setDeferred(null);
    };
    window.addEventListener("appinstalled", installedHandler);
    return () => {
      window.removeEventListener("beforeinstallprompt", handler);
      window.removeEventListener("appinstalled", installedHandler);
    };
  }, [isIos, standalone]);

  const install = useCallback(async () => {
    if (!deferred) return;
    await deferred.prompt();
    const { outcome } = await deferred.userChoice;
    if (outcome === "accepted") setInstalled(true);
    setDeferred(null);
  }, [deferred]);

  const dismiss = useCallback(() => {
    try {
      localStorage.setItem(STORAGE_KEY, String(Date.now()));
    } catch {
      // localStorage unavailable — ignore.
    }
    setDismissed(true);
    setDeferred(null);
  }, []);

  useEffect(() => {
    if (installed || dismissed) return;

    if (isIos && showIosHint) {
      if (announced.current === "ios") return;
      announced.current = "ios";
      toast("On iPhone: tap Share, then Add to Home Screen.", {
        description: "Installs it to your home screen for one-tap access.",
        duration: IOS_HINT_MS,
      });
      return;
    }

    if (!deferred) return;
    if (announced.current === "install") return;
    announced.current = "install";

    toast("Install for one-tap access.", {
      // The user has to notice this and choose. It stays until they act or
      // dismiss it rather than vanishing on a timer.
      duration: Infinity,
      action: {
        label: "Install",
        onClick: () => {
          void install();
        },
      },
      cancel: {
        label: "Not now",
        onClick: dismiss,
      },
    });
  }, [deferred, dismissed, installed, isIos, showIosHint, install, dismiss]);

  return null;
}