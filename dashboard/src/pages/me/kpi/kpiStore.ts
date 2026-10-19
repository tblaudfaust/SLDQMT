import { useEffect, useState } from "react";
import { ApiError, api } from "../../../api/client";
import type { MeKpiGeo, MeKpiGeoEa, MeKpiReportIn, MeKpiSpec, MeKpiSyncOut } from "../../../api/types";

/* ------------------------------------------------------------------------------------------------
 * Offline store for the M&E field tool. Everything the officer needs in the field is kept on the device:
 * the form spec, the geography bundle (districts, chiefdoms, sections, SAs), drafts, the queue of reports
 * waiting to be sent, and the reports already sent. Sync runs when the app opens, when the network comes
 * back and when the officer taps "Send now". Every report carries a client_id, so re-sending is safe.
 * ---------------------------------------------------------------------------------------------- */

const KEY = "me-kpi-store-v1";

export type LocalReport = { client_id: string; data: MeKpiReportIn; status: "draft" | "pending" | "sent" | "error"; saved_at: string; sent_at?: string; server_id?: number; error?: string; summary: string };
type Store = { spec: MeKpiSpec | null; geo: MeKpiGeo | null; geo_at: string | null; spec_at: string | null; reports: LocalReport[]; user_id: number | null; eas_by_team: Record<string, MeKpiGeoEa[]> };

const empty = (): Store => ({ spec: null, geo: null, geo_at: null, spec_at: null, reports: [], user_id: null, eas_by_team: {} });
let store: Store = load();
const listeners = new Set<() => void>();

function load(): Store {
  try { const s = localStorage.getItem(KEY); return s ? { ...empty(), ...(JSON.parse(s) as Store) } : empty(); } catch { return empty(); }
}
function save() {
  try { localStorage.setItem(KEY, JSON.stringify(store)); } catch { /* storage full or private mode: keep in memory */ }
  listeners.forEach((l) => l());
}
function set(patch: Partial<Store>) { store = { ...store, ...patch }; save(); }

export const uuid = () => (crypto.randomUUID ? crypto.randomUUID() : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`);

/** React hook: the store, re-rendered on every change. */
export function useKpiStore() {
  const [, tick] = useState(0);
  useEffect(() => { const l = () => tick((n) => n + 1); listeners.add(l); return () => { listeners.delete(l); }; }, []);
  return store;
}

export function useOnline() {
  const [online, setOnline] = useState(navigator.onLine);
  useEffect(() => {
    const up = () => setOnline(true), down = () => setOnline(false);
    window.addEventListener("online", up); window.addEventListener("offline", down);
    return () => { window.removeEventListener("online", up); window.removeEventListener("offline", down); };
  }, []);
  return online;
}

/** Fetch the form spec and the officer's geography when online; keep the cached copies otherwise. */
export async function refreshReference(userId: number, force = false): Promise<{ spec: MeKpiSpec | null; geo: MeKpiGeo | null; fromCache: boolean }> {
  if (store.user_id !== null && store.user_id !== userId) {
    // another officer signed in on this device: their drafts and geography are not this officer's
    store = { ...empty(), user_id: userId }; save();
  } else if (store.user_id === null) set({ user_id: userId });
  const stale = !store.geo_at || Date.now() - new Date(store.geo_at).getTime() > 1000 * 60 * 60 * 12;
  if (!navigator.onLine || (!force && !stale && store.spec && store.geo)) return { spec: store.spec, geo: store.geo, fromCache: true };
  try {
    const [spec, geo] = await Promise.all([api.get<MeKpiSpec>("/me/kpi/form"), api.get<MeKpiGeo>("/me/kpi/geo")]);
    set({ spec, geo, spec_at: new Date().toISOString(), geo_at: new Date().toISOString() });
    return { spec, geo, fromCache: false };
  } catch {
    return { spec: store.spec, geo: store.geo, fromCache: true };
  }
}

export function summaryOf(d: MeKpiReportIn, geo: MeKpiGeo | null): string {
  const district = geo?.districts.find((x) => x.id === d.district_id)?.name;
  const team = geo?.teams.find((x) => x.id === d.team_id);
  const place = team ? `${team.code}${district ? ` · ${district}` : ""}` : d.practice_team || district || "";
  return `${d.report_date} · ${d.phase} · ${place}`.trim();
}

export function saveDraft(data: MeKpiReportIn, geo: MeKpiGeo | null) {
  const rest = store.reports.filter((r) => r.client_id !== data.client_id);
  const existing = store.reports.find((r) => r.client_id === data.client_id);
  const status: LocalReport["status"] = existing && existing.status !== "draft" ? existing.status : "draft";
  const entry: LocalReport = { client_id: data.client_id, data, status, saved_at: new Date().toISOString(), server_id: existing?.server_id, summary: summaryOf(data, geo) };
  set({ reports: [entry, ...rest].slice(0, 200) });
}

export function queueReport(data: MeKpiReportIn, geo: MeKpiGeo | null) {
  const rest = store.reports.filter((r) => r.client_id !== data.client_id);
  const existing = store.reports.find((r) => r.client_id === data.client_id);
  const entry: LocalReport = { client_id: data.client_id, data, status: "pending", saved_at: new Date().toISOString(), server_id: existing?.server_id, summary: summaryOf(data, geo) };
  set({ reports: [entry, ...rest].slice(0, 200) });
}

/** EAs of an SA fetched on demand (national scope): kept on the device for the next visit without network. */
export function cachedEas(teamId: number): MeKpiGeoEa[] | null { return store.eas_by_team?.[String(teamId)] ?? null; }
export function cacheEas(teamId: number, rows: MeKpiGeoEa[]) {
  const entries = Object.entries(store.eas_by_team ?? {}).slice(-150); // the last 150 SAs looked up
  set({ eas_by_team: { ...Object.fromEntries(entries), [String(teamId)]: rows } });
}

export function removeLocal(client_id: string) { set({ reports: store.reports.filter((r) => r.client_id !== client_id) }); }
export function getLocal(client_id: string) { return store.reports.find((r) => r.client_id === client_id) ?? null; }
export const pendingCount = () => store.reports.filter((r) => r.status === "pending" || r.status === "error").length;

let syncing: Promise<MeKpiSyncOut | null> | null = null;

/** Send every pending report; errors from the server are kept on the report so the officer can fix and re-send. */
export function syncNow(): Promise<MeKpiSyncOut | null> {
  if (syncing) return syncing;
  syncing = (async () => {
    const pending = store.reports.filter((r) => r.status === "pending" || r.status === "error");
    if (!pending.length || !navigator.onLine) return null;
    try {
      const out = await api.post<MeKpiSyncOut>("/me/kpi/sync", { reports: pending.map((r) => ({ ...r.data, submitted_at: r.data.submitted_at ?? r.saved_at, device: navigator.userAgent.slice(0, 150) })) });
      const now = new Date().toISOString();
      set({ reports: store.reports.map((r): LocalReport => {
        const res = out.results.find((x) => x.client_id === r.client_id);
        if (!res) return r;
        return res.status === "error" ? { ...r, status: "error", error: res.message ?? "Rejected" } : { ...r, status: "sent", sent_at: now, server_id: res.id ?? r.server_id, error: undefined };
      }) });
      return out;
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) throw e;
      return null; // no network or server down: stay pending
    }
  })().finally(() => { syncing = null; });
  return syncing;
}

/** Sync automatically when the network returns, when the Android app comes back to the front and when the tab becomes visible. */
export function installAutoSync() {
  const run = () => { void syncNow(); };
  const visible = () => { if (document.visibilityState === "visible") run(); };
  window.addEventListener("online", run);
  window.addEventListener("slphc:resume", run);
  document.addEventListener("visibilitychange", visible);
  return () => { window.removeEventListener("online", run); window.removeEventListener("slphc:resume", run); document.removeEventListener("visibilitychange", visible); };
}
