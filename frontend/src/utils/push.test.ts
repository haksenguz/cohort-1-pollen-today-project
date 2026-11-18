import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  getPushVapidKey: vi.fn(),
  subscribePush: vi.fn(),
  unsubscribePush: vi.fn(),
}));
vi.mock("../api/client", () => api);

import {
  disablePush,
  enablePush,
  getPushState,
  isPushSupported,
  PushNotConfiguredError,
  urlBase64ToUint8Array,
} from "./push";

type FakeSub = {
  endpoint: string;
  toJSON: () => { keys?: { p256dh: string; auth: string } };
  unsubscribe: ReturnType<typeof vi.fn>;
};

function makeSub(overrides: Partial<FakeSub> = {}): FakeSub {
  return {
    endpoint: "https://push.example/abc",
    toJSON: () => ({ keys: { p256dh: "P", auth: "A" } }),
    unsubscribe: vi.fn().mockResolvedValue(true),
    ...overrides,
  };
}

let existing: FakeSub | null;
let permission: NotificationPermission;
let requestPermission: ReturnType<typeof vi.fn>;
let subscribe: ReturnType<typeof vi.fn>;
let getRegistration: ReturnType<typeof vi.fn>;

function installBrowser({ supported = true }: { supported?: boolean } = {}) {
  existing = null;
  permission = "default";
  requestPermission = vi.fn(async () => permission);
  subscribe = vi.fn(async () => makeSub());
  const registration = {
    pushManager: {
      getSubscription: vi.fn(async () => existing),
      subscribe,
    },
  };
  getRegistration = vi.fn(async () => registration);

  if (supported) {
    vi.stubGlobal("PushManager", class {});
    vi.stubGlobal("Notification", {
      requestPermission,
      get permission() {
        return permission;
      },
    });
    Object.defineProperty(navigator, "serviceWorker", {
      configurable: true,
      value: { getRegistration },
    });
  } else {
    vi.stubGlobal("PushManager", undefined);
    vi.stubGlobal("Notification", undefined);
    Object.defineProperty(navigator, "serviceWorker", {
      configurable: true,
      value: undefined,
    });
  }
}

beforeEach(() => {
  vi.clearAllMocks();
  api.getPushVapidKey.mockResolvedValue({ public_key: "BElDdGVzdEtleQ" });
  api.subscribePush.mockResolvedValue(undefined);
  api.unsubscribePush.mockResolvedValue(undefined);
  installBrowser();
});

afterEach(() => {
  vi.unstubAllGlobals();
  Reflect.deleteProperty(navigator, "serviceWorker");
});

describe("isPushSupported", () => {
  it("is true when serviceWorker, PushManager and Notification exist", () => {
    expect(isPushSupported()).toBe(true);
  });

  it("is false when PushManager is missing", () => {
    installBrowser({ supported: false });
    expect(isPushSupported()).toBe(false);
  });
});

describe("getPushState", () => {
  it("is unsupported without the browser APIs", async () => {
    installBrowser({ supported: false });
    expect(await getPushState()).toBe("unsupported");
  });

  it("is denied when the permission is blocked", async () => {
    permission = "denied";
    expect(await getPushState()).toBe("denied");
  });

  it("is off with permission but no subscription", async () => {
    permission = "granted";
    expect(await getPushState()).toBe("off");
  });

  it("is on with permission and a subscription", async () => {
    permission = "granted";
    existing = makeSub();
    expect(await getPushState()).toBe("on");
  });
});

describe("urlBase64ToUint8Array", () => {
  it("decodes base64url without padding into bytes", () => {
    // "-_8" decodes to 0xfb 0xff once mapped to standard base64.
    expect(Array.from(urlBase64ToUint8Array("-_8"))).toEqual([0xfb, 0xff]);
  });
});

describe("enablePush", () => {
  it("throws PushNotConfiguredError when the server has no key", async () => {
    api.getPushVapidKey.mockResolvedValue({ public_key: null });
    await expect(enablePush()).rejects.toBeInstanceOf(PushNotConfiguredError);
    expect(requestPermission).not.toHaveBeenCalled();
  });

  it("refuses when the permission is not granted", async () => {
    permission = "denied";
    await expect(enablePush()).rejects.toThrow(/blocked/i);
    expect(subscribe).not.toHaveBeenCalled();
    expect(api.subscribePush).not.toHaveBeenCalled();
  });

  it("subscribes with the server key and posts the subscription", async () => {
    permission = "granted";
    await enablePush();
    expect(subscribe).toHaveBeenCalledWith(
      expect.objectContaining({ userVisibleOnly: true }),
    );
    expect(api.subscribePush).toHaveBeenCalledWith({
      endpoint: "https://push.example/abc",
      keys: { p256dh: "P", auth: "A" },
    });
  });

  it("rejects an incomplete subscription and cleans it up", async () => {
    permission = "granted";
    const bad = makeSub({ toJSON: () => ({}) });
    subscribe.mockResolvedValueOnce(bad);
    await expect(enablePush()).rejects.toThrow(/incomplete/i);
    expect(bad.unsubscribe).toHaveBeenCalled();
    expect(api.subscribePush).not.toHaveBeenCalled();
  });
});

describe("disablePush", () => {
  it("deletes on the server, then unsubscribes in the browser", async () => {
    existing = makeSub();
    await disablePush();
    expect(api.unsubscribePush).toHaveBeenCalledWith({ endpoint: "https://push.example/abc" });
    expect(existing.unsubscribe).toHaveBeenCalled();
  });

  it("keeps the browser subscription when the server delete fails", async () => {
    existing = makeSub();
    api.unsubscribePush.mockRejectedValueOnce(new Error("down"));
    await expect(disablePush()).rejects.toThrow("down");
    expect(existing.unsubscribe).not.toHaveBeenCalled();
  });

  it("does nothing when there is no subscription", async () => {
    await disablePush();
    expect(api.unsubscribePush).not.toHaveBeenCalled();
  });
});
