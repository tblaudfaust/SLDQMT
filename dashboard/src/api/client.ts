import type { TokenPair } from "./types";

const BASE = "/api/v1";
const ACCESS = "fm_access";
const REFRESH = "fm_refresh";

export const tokens = {
  get access() {
    return localStorage.getItem(ACCESS);
  },
  get refresh() {
    return localStorage.getItem(REFRESH);
  },
  set(pair: TokenPair) {
    localStorage.setItem(ACCESS, pair.access_token);
    localStorage.setItem(REFRESH, pair.refresh_token);
  },
  clear() {
    localStorage.removeItem(ACCESS);
    localStorage.removeItem(REFRESH);
  },
};

export class ApiError extends Error {
  constructor(public status: number, message: string, public body?: unknown) {
    super(message);
  }
}

let refreshing: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  if (!refreshing) {
    refreshing = (async () => {
      const r = tokens.refresh;
      if (!r) return false;
      const res = await fetch(`${BASE}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: r }),
      });
      if (!res.ok) {
        tokens.clear();
        return false;
      }
      tokens.set(await res.json());
      return true;
    })().finally(() => (refreshing = null));
  }
  return refreshing;
}

export function qs(params: Record<string, unknown>): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "" || v === false) continue;
    if (Array.isArray(v)) v.forEach((x) => p.append(k, String(x)));
    else p.set(k, String(v));
  }
  const s = p.toString();
  return s ? `?${s}` : "";
}

export async function request<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData) && !headers.has("Content-Type") && init.body) headers.set("Content-Type", "application/json");
  const access = tokens.access;
  if (access) headers.set("Authorization", `Bearer ${access}`);
  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (res.status === 401 && retry && (await tryRefresh())) return request<T>(path, init, false);
  if (!res.ok) {
    let message = res.statusText;
    let payload: unknown;
    try {
      const body = await res.json();
      payload = body;
      message = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      /* keep statusText */
    }
    if (res.status === 401) {
      tokens.clear();
      window.dispatchEvent(new Event("fm:logout"));
    }
    throw new ApiError(res.status, message, payload);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body: body instanceof FormData ? body : JSON.stringify(body ?? {}) }),
  put: <T>(path: string, body?: unknown) => request<T>(path, { method: "PUT", body: JSON.stringify(body ?? {}) }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: "PATCH", body: JSON.stringify(body ?? {}) }),
  delete: <T>(path: string, body?: unknown) => request<T>(path, { method: "DELETE", body: JSON.stringify(body ?? {}) }),
};

/** Download a report through fetch so the bearer token is sent. */
export async function download(path: string, filename: string) {
  const res = await fetch(`${BASE}${path}`, { headers: { Authorization: `Bearer ${tokens.access ?? ""}` } });
  if (!res.ok) throw new ApiError(res.status, await res.text());
  const blob = await res.blob();
  const cd = res.headers.get("content-disposition");
  const name = cd?.match(/filename="?([^"]+)"?/)?.[1] ?? filename;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

export function fmt(iso?: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString("en-GB", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "UTC" });
}

export function fmtDate(iso?: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" });
}
