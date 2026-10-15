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
 * No demo session.
 *
 * This used to boot straight to "authenticated" with a hardcoded DEMO_USER so a
 * fresh install could poke at the app without registering. But every protected
 * endpoint is Bearer-authenticated, so that state was a lie the app could not
 * honour: POST /api/chat returned 401 "Could not validate credentials" on every
 * turn, and because the chat screen had no recovery path for a dead token it
 * read as a permanently stuck agent.
 *
 * Demo mode's own note admitted it - "protected endpoints will return 401" -
 * and the server-side fallback it was waiting on never landed. Authentication
 * is honest now: no token means signed out, RequireAuth sends you to /login,
 * and /login is the only place a token can be obtained.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [status, setStatus] = useState<AuthContextValue["status"]>("loading");

  useEffect(() => {
    let cancelled = false;
    async function hydrate() {
      if (!getToken()) {
        if (!cancelled) setStatus("unauthenticated");
        return;
      }
      try {
        const me = await getCurrentUser();
        if (cancelled) return;
        setUser(me);
        setStatus("authenticated");
      } catch {
        // Drop a stale or rejected token. Left in place it fails every later
        // request, and nothing on screen distinguishes "signed out" from
        // "broken".
        clearToken();
        if (!cancelled) setStatus("unauthenticated");
      }
    }
    void hydrate();
    return () => {
      cancelled = true;
    };
  }, []);

  // Failures propagate so the login form can show the server's own message.
  // Swallowing them and reporting success is what made a wrong password look
  // like a successful sign-in.
  const login = useCallback(async (body: LoginRequest) => {
    const { access_token } = await loginRequest(body);
    setToken(access_token);
    const me = await getCurrentUser();
    setUser(me);
    setStatus("authenticated");
  }, []);

  const register = useCallback(async (body: RegisterRequest) => {
    const { access_token } = await registerRequest(body);
    setToken(access_token);
    const me = await getCurrentUser();
    setUser(me);
    setStatus("authenticated");
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
    setStatus("unauthenticated");
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
