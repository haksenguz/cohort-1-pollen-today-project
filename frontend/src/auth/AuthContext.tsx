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
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [status, setStatus] = useState<AuthContextValue["status"]>("loading");

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      const token = getToken();
      if (!token) {
        setStatus("unauthenticated");
        return;
      }
      try {
        const me = await getCurrentUser();
        if (!cancelled) {
          setUser(me);
          setStatus("authenticated");
        }
      } catch {
        clearToken();
        if (!cancelled) setStatus("unauthenticated");
      }
    }

    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

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

  const value = useMemo(
    () => ({ user, status, login, register, logout }),
    [user, status, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
