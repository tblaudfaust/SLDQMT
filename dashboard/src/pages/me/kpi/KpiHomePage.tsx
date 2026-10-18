import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import clsx from "clsx";
import { AlertCircle, BarChart3, CheckCircle2, ClipboardList, CloudOff, CloudUpload, Database, FilePlus2, ListChecks, Pencil, RefreshCw, Trash2, Wifi, WifiOff } from "lucide-react";
import { useAuth } from "../../../auth/AuthContext";
import { Card, ErrorBox } from "../../../components/ui";
import { installAutoSync, pendingCount, refreshReference, removeLocal, syncNow, useKpiStore, useOnline, type LocalReport } from "./kpiStore";

const STATUS: Record<LocalReport["status"], { label: string; cls: string }> = {
  draft: { label: "Draft", cls: "bg-slate-100 text-slate-700" },
  pending: { label: "Waiting to send", cls: "bg-amber-100 text-amber-800" },
  sent: { label: "Sent", cls: "bg-emerald-100 text-emerald-800" },
  error: { label: "Rejected", cls: "bg-red-100 text-red-800" },
};
const PHASE: Record<string, string> = { MT: "Master trainers' practice", TOT: "ToT practice", L: "Listing", E: "Enumeration" };
const fmt = (iso: string) => new Date(iso).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });

/** The M&E field tool's front page: start a report, see what is waiting to be sent, open the dashboard. Works offline. */
export default function KpiHomePage() {
  const { user, can } = useAuth();
  const online = useOnline();
  const store = useKpiStore();
  const nav = useNavigate();
  const loc = useLocation();
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>((loc.state as { notice?: string } | null)?.notice ?? null);
  const [error, setError] = useState<unknown>(null);
  const [fromCache, setFromCache] = useState(false);
  const pending = pendingCount();

  useEffect(() => {
    if (!user) return;
    refreshReference(user.id).then((r) => setFromCache(r.fromCache)).catch(setError);
    void syncNow().catch(setError);
    return installAutoSync();
  }, [user]);

  const send = async () => {
    setBusy(true); setError(null);
    try {
      const out = await syncNow();
      setNotice(out ? `${out.created + out.updated} report${out.created + out.updated === 1 ? "" : "s"} sent${out.errors ? `, ${out.errors} rejected (see below)` : ""}.` : online ? "Nothing waiting to be sent." : "No network: the reports stay on this device and go when you are back online.");
    } catch (e) { setError(e); } finally { setBusy(false); }
  };
  const refresh = async () => {
    if (!user) return;
    setBusy(true); setError(null);
    try { const r = await refreshReference(user.id, true); setFromCache(r.fromCache); setNotice(r.fromCache ? "No network: the saved GIS data stays in use." : `GIS data refreshed: ${r.geo?.districts.length ?? 0} district(s), ${r.geo?.teams.length ?? 0} SAs.`); } catch (e) { setError(e); } finally { setBusy(false); }
  };
  const reports = store.reports;
  const sentToday = reports.filter((r) => r.status === "sent" && r.sent_at && r.sent_at.slice(0, 10) === new Date().toISOString().slice(0, 10)).length;

  return (
    <div className="max-w-5xl">
      <div className="mb-4 overflow-hidden rounded-2xl bg-gradient-to-br from-navy via-[#245a8c] to-[#1b7f6b] px-6 py-5 text-white shadow">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-xs uppercase tracking-[0.3em] text-sky-100/80">2026 Population and Housing Census</div>
            <h1 className="mt-1 text-2xl font-bold">M&amp;E Field Tool</h1>
            <p className="text-sm text-sky-100/90">KPIs for monitoring and evaluation: field practice, listing and enumeration. Fill it in the field, with or without network; reports are sent when you are connected.</p>
          </div>
          <div className={clsx("flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-semibold", online ? "bg-emerald-500/25" : "bg-amber-500/30")}>
            {online ? <Wifi size={16} /> : <WifiOff size={16} />} {online ? "Online" : "Offline · saving on this device"}
          </div>
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <Link to="/me/kpi/new" className="flex items-center gap-3 rounded-xl bg-white px-4 py-4 text-navy shadow hover:bg-sky-50"><FilePlus2 size={26} /><div><div className="text-base font-bold">Start a new report</div><div className="text-xs text-slate-500">one SA or practice team</div></div></Link>
          <button onClick={send} disabled={busy} className={clsx("flex items-center gap-3 rounded-xl px-4 py-4 text-left shadow", pending ? "bg-amber-400 text-amber-950 hover:bg-amber-300" : "bg-white/15 text-white hover:bg-white/25")}>
            {pending ? <CloudUpload size={26} /> : <CheckCircle2 size={26} />}<div><div className="text-base font-bold">{pending ? `Send ${pending} waiting` : "All reports sent"}</div><div className="text-xs opacity-80">{pending ? (online ? "tap to send now" : "sends when back online") : `${sentToday} sent today from this device`}</div></div>
          </button>
          {can("me_kpi.view") && <Link to="/me/kpi/dashboard" className="flex items-center gap-3 rounded-xl bg-white/15 px-4 py-4 text-white shadow hover:bg-white/25"><BarChart3 size={26} /><div><div className="text-base font-bold">Dashboard</div><div className="text-xs opacity-80">KPIs by district and week</div></div></Link>}
        </div>
      </div>
      {notice && <div className="mb-3 flex items-center justify-between rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-900"><span>{notice}</span><button className="text-xs underline" onClick={() => setNotice(null)}>Close</button></div>}
      <ErrorBox error={error} />

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2" title="Reports on this device" action={<Link to="/me/kpi/reports" className="text-sm text-navy underline"><ListChecks size={14} className="mr-1 inline" />All reports</Link>}>
          {reports.length === 0 ? (
            <div className="py-8 text-center text-sm text-slate-400">No report yet on this device. Tap <b>Start a new report</b>.</div>
          ) : (
            <ul className="divide-y divide-slate-100">
              {reports.map((r) => (
                <li key={r.client_id} className="flex flex-wrap items-center justify-between gap-2 py-2.5 text-sm">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2"><span className={clsx("rounded-full px-2 py-0.5 text-xs font-semibold", STATUS[r.status].cls)}>{STATUS[r.status].label}</span><span className="font-medium">{PHASE[r.data.phase] ?? r.data.phase}</span><span className="text-slate-500">{r.data.report_date}</span></div>
                    <div className="truncate text-xs text-slate-500">{r.summary}{r.data.respondent_name ? ` · ${r.data.respondent_name}` : ""} · saved {fmt(r.saved_at)}{r.sent_at ? ` · sent ${fmt(r.sent_at)}` : ""}</div>
                    {r.error && <div className="mt-0.5 flex items-center gap-1 text-xs text-red-700"><AlertCircle size={12} /> {r.error}</div>}
                  </div>
                  <div className="flex shrink-0 gap-2">
                    <button className="btn-outline py-1 text-xs" onClick={() => nav(`/me/kpi/report/${r.client_id}`)}><Pencil size={14} /> {r.status === "draft" ? "Continue" : "Edit"}</button>
                    {r.status !== "pending" && <button className="btn-outline py-1 text-xs text-red-700" onClick={() => { if (confirm(r.status === "sent" ? "Remove this copy from the device? The report stays on the server." : "Discard this report? It was never sent.")) removeLocal(r.client_id); }}><Trash2 size={14} /></button>}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <div className="space-y-4">
          <Card title="GIS data on this device">
            <div className="flex items-start gap-3 text-sm">
              <Database size={22} className="shrink-0 text-navy" />
              <div>
                {store.geo ? (
                  <>
                    <div><b>{store.geo.districts.length}</b> district{store.geo.districts.length === 1 ? "" : "s"} · <b>{store.geo.chiefdoms.length}</b> chiefdoms · <b>{store.geo.teams.length}</b> SAs</div>
                    <div className="text-xs text-slate-500">{store.geo.districts.map((d) => d.name).slice(0, 6).join(", ")}{store.geo.districts.length > 6 ? "…" : ""}</div>
                    <div className="mt-1 text-xs text-slate-500">Updated {store.geo_at ? fmt(store.geo_at) : "—"}{fromCache ? " (saved copy)" : ""}</div>
                  </>
                ) : <div className="text-slate-500">Not loaded yet. Connect once so the districts, chiefdoms, sections and SAs are saved on this device.</div>}
                <button className="btn-outline mt-2 py-1 text-xs" onClick={refresh} disabled={busy || !online}><RefreshCw size={14} /> Refresh</button>
              </div>
            </div>
          </Card>
          <Card title="How it works">
            <ul className="space-y-2 text-sm text-slate-600">
              <li className="flex gap-2"><ClipboardList size={16} className="mt-0.5 shrink-0 text-navy" /> One report per SA (or practice team): each practice day, weekly in listing and enumeration.</li>
              <li className="flex gap-2"><CloudOff size={16} className="mt-0.5 shrink-0 text-navy" /> No network? Everything is saved here and sent automatically later. Open the app at least once online so it can work offline.</li>
              <li className="flex gap-2"><CloudUpload size={16} className="mt-0.5 shrink-0 text-navy" /> A sent report can still be corrected: edit and send again.</li>
            </ul>
          </Card>
        </div>
      </div>
    </div>
  );
}
