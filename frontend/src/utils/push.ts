/**
 * Web push helpers. The server owns the subscription list. This module asks
 * the browser for permission, creates or removes the subscription, and reports
 * the state the settings row shows.
 */
import { getPushVapidKey, subscribePush, unsubscribePush } from "../api/client";

export type PushState = "unsupported" | "denied" | "off" | "on";

/** Thrown when the server has no VAPID key, so the UI can say so plainly. */
export class PushNotConfiguredError extends Error {
  constructor() {
    super("Push notifications are not set up on the server yet.");
    this.name = "PushNotConfiguredError";
  }
}

export function isPushSupported(): boolean {
  return (
    typeof window !== "undefined" &&
    Boolean(navigator.serviceWorker) &&
    Boolean(window.PushManager) &&
    Boolean(window.Notification)
  );
}

async function currentRegistration(): Promise<ServiceWorkerRegistration | undefined> {
  return navigator.serviceWorker.getRegistration();
}

export async function getPushState(): Promise<PushState> {
  if (!isPushSupported()) return "unsupported";
  if (Notification.permission === "denied") return "denied";
  const registration = await currentRegistration();
  const subscription = await registration?.pushManager.getSubscription();
  return subscription && Notification.permission === "granted" ? "on" : "off";
}

/** VAPID public keys arrive base64url. PushManager wants raw bytes. */
export function urlBase64ToUint8Array(base64: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const normalized = (base64 + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(normalized);
  const bytes = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i += 1) bytes[i] = raw.charCodeAt(i);
  return bytes;
}

export async function enablePush(): Promise<void> {
  if (!isPushSupported()) {
    throw new Error("This browser does not support push notifications.");
  }
  const { public_key: publicKey } = await getPushVapidKey();
  if (!publicKey) throw new PushNotConfiguredError();

  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    throw new Error("Notifications are blocked for this site in your browser settings.");
  }

  const registration = await currentRegistration();
  if (!registration) {
    throw new Error("The app is still loading its background worker. Try again in a moment.");
  }

  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(publicKey),
  });
  const json = subscription.toJSON();
  const p256dh = json.keys?.p256dh;
  const auth = json.keys?.auth;
  if (!subscription.endpoint || !p256dh || !auth) {
    await subscription.unsubscribe();
    throw new Error("The browser returned an incomplete push subscription.");
  }
  await subscribePush({ endpoint: subscription.endpoint, keys: { p256dh, auth } });
}

export async function disablePush(): Promise<void> {
  if (!isPushSupported()) return;
  const registration = await currentRegistration();
  const subscription = await registration?.pushManager.getSubscription();
  if (!subscription) return;
  // Server first. If its delete fails, the browser keeps the subscription and
  // the toggle stays on, so the server never sends to a dead endpoint silently.
  await unsubscribePush({ endpoint: subscription.endpoint });
  await subscription.unsubscribe();
}
