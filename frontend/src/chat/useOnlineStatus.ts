/**
 * Whether the device has a network right now.
 *
 * `navigator.onLine` only says whether the device is attached to a network, not
 * whether the server is reachable. It is still the honest signal for "the
 * socket is dead", and the chat uses it to refuse a send rather than let a
 * message disappear into a failed request.
 */
import { useSyncExternalStore } from "react";

function subscribe(onChange: () => void): () => void {
  window.addEventListener("online", onChange);
  window.addEventListener("offline", onChange);
  return () => {
    window.removeEventListener("online", onChange);
    window.removeEventListener("offline", onChange);
  };
}

function getSnapshot(): boolean {
  return typeof navigator === "undefined" ? true : navigator.onLine;
}

export function useOnlineStatus(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, () => true);
}
