/**
 * The 민감정보 consent state, shared by every screen that shows it.
 *
 * One place holds it, so the gate in front of the chat and the row in Settings
 * cannot disagree about whether consent was given. The withdrawal is a write
 * like any other: the server owns the record, and this only reads it back.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import {
  readConsent,
  readPolicy,
  writeConsent,
  type ConsentState,
  type PolicyDocument,
} from "../api/consent";

interface ConsentContextValue {
  /** "loading" until the server has answered. */
  status: "loading" | "ready" | "error";
  consent: ConsentState | null;
  policy: PolicyDocument | null;
  /** True only when the server says the consent is in place. */
  granted: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  setGranted: (granted: boolean) => Promise<void>;
}

const ConsentContext = createContext<ConsentContextValue | undefined>(undefined);

export function ConsentProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<ConsentContextValue["status"]>("loading");
  const [consent, setConsent] = useState<ConsentState | null>(null);
  const [policy, setPolicy] = useState<PolicyDocument | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      // The policy is public and the consent is per user, so they are read
      // together. A missing policy must not stop the consent state from
      // arriving: the gate can still ask, it just cannot list the items.
      const [nextConsent, nextPolicy] = await Promise.all([
        readConsent(),
        readPolicy().catch(() => null),
      ]);
      setConsent(nextConsent);
      setPolicy(nextPolicy);
      setStatus("ready");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not read your privacy settings.");
      setStatus("error");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const setGranted = useCallback(
    async (granted: boolean) => {
      setError(null);
      try {
        setConsent(await writeConsent(granted));
        setStatus("ready");
      } catch (e) {
        const message = e instanceof Error ? e.message : "Could not record your choice.";
        setError(message);
        throw e;
      }
    },
    [],
  );

  const value = useMemo<ConsentContextValue>(
    () => ({
      status,
      consent,
      policy,
      granted: consent?.granted === true,
      error,
      refresh,
      setGranted,
    }),
    [status, consent, policy, error, refresh, setGranted],
  );

  return <ConsentContext.Provider value={value}>{children}</ConsentContext.Provider>;
}

export function useConsent(): ConsentContextValue {
  const ctx = useContext(ConsentContext);
  if (!ctx) throw new Error("useConsent must be used inside <ConsentProvider>");
  return ctx;
}
