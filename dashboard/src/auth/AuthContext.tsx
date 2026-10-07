import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, tokens } from "../api/client";
import type { TokenPair, User } from "../api/types";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  /** Reload the signed-in user's profile from the server (after a password change, for example). */
  refreshUser: () => Promise<void>;
  /** True when the signed-in user holds every listed permission. */
  can: (...codes: string[]) => boolean;
}

const Ctx = createContext<AuthState>({ user: null, loading: true, login: async () => {}, logout: () => {}, refreshUser: async () => {}, can: () => false });

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!tokens.access) {
      setLoading(false);
      return;
    }
    api
      .get<User>("/auth/me")
      .then(setUser)
      .catch(() => tokens.clear())
      .finally(() => setLoading(false));
    const onLogout = () => setUser(null);
    window.addEventListener("fm:logout", onLogout);
    return () => window.removeEventListener("fm:logout", onLogout);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const pair = await api.post<TokenPair>("/auth/login", { username, password });
    if (pair.user.role === "FIELD_MONITOR") throw new Error("Field Monitor accounts use the tablet app, not the dashboard");
    tokens.set(pair);
    setUser(pair.user);
  }, []);

  const logout = useCallback(() => {
    const r = tokens.refresh;
    if (r) api.post("/auth/logout", { refresh_token: r }).catch(() => {});
    tokens.clear();
    setUser(null);
  }, []);

  const refreshUser = useCallback(async () => { setUser(await api.get<User>("/auth/me")); }, []);

  const can = useCallback((...codes: string[]) => !!user && codes.every((c) => user.permissions?.includes(c)), [user]);

  return <Ctx.Provider value={{ user, loading, login, logout, refreshUser, can }}>{children}</Ctx.Provider>;
}

export const useAuth = () => useContext(Ctx);
