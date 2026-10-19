import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { ApiError, api, tokens } from "../api/client";
import type { TokenPair, User } from "../api/types";
import { isAppMode } from "../brand";
import { forgetOffline, hasOfflineSession, rememberOffline, signInOffline } from "./offlineAuth";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  /** Reload the signed-in user's profile from the server (after a password change, for example). */
  refreshUser: () => Promise<void>;
  /** True when the signed-in user holds every listed permission. */
  can: (...codes: string[]) => boolean;
  /** After a password change: keep the offline sign-in of this device in step with the new password. */
  rememberPassword: (newPassword: string) => Promise<void>;
}

const USER_KEY = "fm_user";
/** The signed-in profile, kept on the device so the field tool can open without network. */
function cacheUser(u: User | null) { try { if (u) localStorage.setItem(USER_KEY, JSON.stringify(u)); else localStorage.removeItem(USER_KEY); } catch { /* private mode */ } }
function readCachedUser(): User | null { try { const s = localStorage.getItem(USER_KEY); return s ? (JSON.parse(s) as User) : null; } catch { return null; } }

const Ctx = createContext<AuthState>({ user: null, loading: true, login: async () => {}, logout: () => {}, refreshUser: async () => {}, can: () => false, rememberPassword: async () => {} });

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
      .then((u) => { setUser(u); cacheUser(u); })
      .catch((e) => {
        // a rejected token signs the user out; no network (the field tool offline) keeps the last known profile
        if (e instanceof ApiError && (e.status === 401 || e.status === 403)) { tokens.clear(); cacheUser(null); return; }
        const cached = readCachedUser();
        if (cached) setUser(cached); else tokens.clear();
      })
      .finally(() => setLoading(false));
    const onLogout = () => setUser(null);
    window.addEventListener("fm:logout", onLogout);
    return () => window.removeEventListener("fm:logout", onLogout);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    let pair: TokenPair;
    try {
      pair = await api.post<TokenPair>("/auth/login", { username, password });
    } catch (e) {
      if (e instanceof ApiError) {
        if (e.status === 401 || e.status === 403) forgetOffline(username); // the server refused this account: no offline sign-in either
        throw e;
      }
      // no network: unlock the session saved on this device at the last online sign-in
      const saved = await signInOffline(username, password);
      if (!saved) {
        throw new Error(hasOfflineSession(username)
          ? "No network. The password does not match the one used at the last sign-in on this device."
          : "No network, and this account has not signed in on this device yet. Connect once to sign in; after that you can sign in offline.");
      }
      tokens.set(saved.tokens);
      setUser(saved.user);
      cacheUser(saved.user);
      return;
    }
    if (pair.user.role === "FIELD_MONITOR") throw new Error("Field Monitor accounts use the tablet app, not the dashboard");
    tokens.set(pair);
    setUser(pair.user);
    cacheUser(pair.user);
    if (pair.user.permissions?.includes("me_kpi.collect")) void rememberOffline(username, password, pair, pair.user);
  }, []);

  const logout = useCallback(() => {
    const r = tokens.refresh;
    // the field app keeps the session usable for offline sign-in (encrypted with the officer's password), so it is not revoked
    if (r && !isAppMode) api.post("/auth/logout", { refresh_token: r }).catch(() => {});
    tokens.clear();
    cacheUser(null);
    setUser(null);
  }, []);

  const rememberPassword = useCallback(async (newPassword: string) => {
    const u = user ?? readCachedUser();
    const access = tokens.access, refresh = tokens.refresh;
    if (!u || !access || !refresh || !u.permissions?.includes("me_kpi.collect")) return;
    await rememberOffline(u.username, newPassword, { access_token: access, refresh_token: refresh } as TokenPair, { ...u, must_change_password: false });
  }, [user]);

  const refreshUser = useCallback(async () => { const u = await api.get<User>("/auth/me"); setUser(u); cacheUser(u); }, []);

  const can = useCallback((...codes: string[]) => !!user && codes.every((c) => user.permissions?.includes(c)), [user]);

  return <Ctx.Provider value={{ user, loading, login, logout, refreshUser, can, rememberPassword }}>{children}</Ctx.Provider>;
}

export const useAuth = () => useContext(Ctx);
