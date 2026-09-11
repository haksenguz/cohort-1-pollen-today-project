/**
 * Captures the browser's beforeinstallprompt event and exposes a small
 * "Install the app" toast the user can tap at any time. iOS Safari does
 * NOT fire beforeinstallprompt — for iOS users, the toast shows a one-line
 * hint to use Safari's Share → "Add to Home Screen" instead. We detect iOS
 * via userAgent + the standalone-mode check.
 */
import { useCallback, useEffect, useMemo, useState } from "react";

interface BeforeInstallPromptEvent extends Event {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

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

  if (installed || dismissed) return null;

  if (isIos && showIosHint) {
    return (
      <div className="pwa-toast" role="status">
        <span>
          On iPhone: tap <b>Share</b> then <b>Add to Home Screen</b>.
        </span>
        <button
          type="button"
          className="pwa-toast-x"
          aria-label="Dismiss install hint"
          onClick={() => setShowIosHint(false)}
        >
          ×
        </button>
      </div>
    );
  }

  if (!deferred) return null;

  return (
    <div className="pwa-toast" role="status">
      <span>Install for one-tap access.</span>
      <button type="button" className="pwa-toast-btn" onClick={() => void install()}>
        Install
      </button>
      <button
        type="button"
        className="pwa-toast-x"
        aria-label="Dismiss install prompt"
        onClick={dismiss}
      >
        ×
      </button>
    </div>
  );
}