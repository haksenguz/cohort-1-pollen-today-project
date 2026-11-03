import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  ApiError,
  getCurrentUser,
  login as loginRequest,
  register as registerRequest,
} from "../api/client";
import type { LoginRequest, RegisterRequest, UserResponse } from "../api/types";
import { clearToken, getToken, setToken } from "./token";

interface AuthContextValue {
  user: UserResponse | null;
  status: "loading" | "authenticated" | "unauthenticated" | "unreachable";
  login: (body: LoginRequest) => Promise<void>;
  register: (body: RegisterRequest) => Promise<void>;
  logout: () => void;
  updateUser: (updated: UserResponse) => void;
  /** Ask the server who we are again, after it could not be reached. */
  retry: () => void;
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
 *
 * "Unreachable" is the third state, and it is not a flavour of signed out. A
 * token the server refused is dead and has to go. A server that could not be
 * reached has not said anything about the token at all, and throwing it away
 * turns a dropped connection into a lost session.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserResponse | null>(null);
  // The first answer is known without asking anyone: no token, no session.
  const [status, setStatus] = useState<AuthContextValue["status"]>(() =>
    getToken() ? "loading" : "unauthenticated",
  );
  // A request that outlives the provider must not set state on an unmounted
  // tree. The flag is set on every mount so a StrictMode remount starts clean.
  const alive = useRef(true);

  const hydrate = useCallback(async () => {
    // The caller has already established that there is a token. A token that
    // disappears mid-flight fails the request, and the catch below handles it.
    try {
      const me = await getCurrentUser();
      if (!alive.current) return;
      setUser(me);
      setStatus("authenticated");
    } catch (error) {
      // Two failures land here and they need opposite answers.
      //
      // The server answered and refused the token: it is dead. Left in place it
      // fails every later request, and nothing on screen tells "signed out"
      // from "broken", so it goes.
      //
      // The server could not be reached, or broke on its own: the token is
      // still good. Dropping it signs the user out because their train went
      // into a tunnel, and they have to type a password to get back into an app
      // they were already signed in to.
      const refused = error instanceof ApiError && (error.status === 401 || error.status === 403);
      if (refused) {
        clearToken();
        if (!alive.current) return;
        setUser(null);
        setStatus("unauthenticated");
        return;
      }
      if (!alive.current) return;
      setStatus("unreachable");
    }
  }, []);

  useEffect(() => {
    alive.current = true;
    // No token means signed out, and the initial state already says so.
    // Asking the server anyway would be a request that cannot succeed.
    if (getToken()) void hydrate();
    return () => {
      alive.current = false;
    };
  }, [hydrate]);

  const retry = useCallback(() => {
    // The status moves back to loading here, in the click, rather than inside
    // the request. Setting it in the effect would be a render that changes
    // nothing, and the linter is right to say so.
    if (!getToken()) {
      setStatus("unauthenticated");
      return;
    }
    setStatus("loading");
    void hydrate();
  }, [hydrate]);

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
    () => ({ user, status, login, register, logout, updateUser, retry }),
    [user, status, login, register, logout, updateUser, retry],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
