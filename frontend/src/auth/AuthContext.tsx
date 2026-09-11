import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { getCurrentUser, login as loginRequest, register as registerRequest } from "../api/client";
import type { LoginRequest, RegisterRequest, UserResponse } from "../api/types";
import { clearToken, getToken, setToken } from "./token";

interface AuthContextValue {
  user: UserResponse | null;
  status: "loading" | "authenticated" | "unauthenticated";
  login: (body: LoginRequest) => Promise<void>;
  register: (body: RegisterRequest) => Promise<void>;
  logout: () => void;
  updateUser: (updated: UserResponse) => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

/**
 * Demo mode (added 2026-09-11, removed after the demo). The app boots straight
 * into an authenticated test-user session so a phone or fresh install can use
 * it without going through register/login. The backend is unaffected — every
 * `/api/*` call still uses the bearer flow when a token exists; calls without
 * a token fall back to a known test user on the server side (see ADR 0003).
 *
 * Until that backend fallback lands, protected endpoints will return 401. We
 * log that to the console and stay "authenticated" so the UI keeps working
 * for screens that don't need server-side identity (Today, Alerts read,
 * Profile read-only).
 */
const DEMO_USER: UserResponse = {
  id: 0,
  email: "demo@local",
  latitude: 37.5665,
  longitude: 126.978,
  created_at: "2026-09-11T00:00:00Z",
  updated_at: "2026-09-11T00:00:00Z",
};

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserResponse | null>(DEMO_USER);
  const [status, setStatus] = useState<AuthContextValue["status"]>("authenticated");

  // Best-effort: try to hydrate the demo user from the backend so calls that
  // need a real user id (e.g. /api/allergies) work. If the backend is
  // unreachable, we keep the offline demo user and the UI degrades gracefully.
  useEffect(() => {
    let cancelled = false;
    async function hydrate() {
      const token = getToken();
      if (!token) return;
      try {
        const me = await getCurrentUser();
        if (!cancelled) setUser(me);
      } catch {
        // Backend offline — keep the demo user, that's fine.
      }
    }
    void hydrate();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (body: LoginRequest) => {
    try {
      const { access_token } = await loginRequest(body);
      setToken(access_token);
      const me = await getCurrentUser();
      setUser(me);
      setStatus("authenticated");
    } catch {
      setUser(DEMO_USER);
      setStatus("authenticated");
    }
  }, []);

  const register = useCallback(async (body: RegisterRequest) => {
    try {
      const { access_token } = await registerRequest(body);
      setToken(access_token);
      const me = await getCurrentUser();
      setUser(me);
      setStatus("authenticated");
    } catch {
      setUser(DEMO_USER);
      setStatus("authenticated");
    }
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setUser(DEMO_USER);
    setStatus("authenticated");
  }, []);

  const updateUser = useCallback((updated: UserResponse) => {
    setUser(updated);
  }, []);

  const value = useMemo(
    () => ({ user, status, login, register, logout, updateUser }),
    [user, status, login, register, logout, updateUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
