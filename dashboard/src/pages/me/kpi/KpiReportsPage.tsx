import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import clsx from "clsx";
import { Pencil, Trash2, X } from "lucide-react";
import { ApiError, api, fmtDate, qs } from "../../../api/client";
import type { MeKpiItem, MeKpiReport, MeKpiReportIn, MeKpiSpec, MeKpiSummary } from "../../../api/types";
import { useAuth } from "../../../auth/AuthContext";
import { Card, Empty, ErrorBox, Spinner } from "../../../components/ui";
import { saveDraft, useKpiStore } from "./kpiStore";

const PHASES = [["MT", "Master trainers' practice"], ["TOT", "ToT practice"], ["TOE", "ToE practice"], ["L", "Listing"], ["E", "Enumeration"]];
const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${v}%`);

function answerText(it: MeKpiItem, v: unknown): string {
  if (v === undefined || v === null || v === "") return "";
  if (it.type === "multi") { const m = Object.fromEntries((it.options ?? []).map((o) => [o.value, o.label])); return (v as string[]).map((x) => m[x] ?? x).join(", "); }
  if (it.options) return it.options.find((o) => o.value === String(v))?.label ?? String(v);
  if (it.type === "numbers") { const o = v as Record<string, number>; return (it.fields ?? []).filter((f) => o[f.key] !== undefined).map((f) => `${f.label}: ${o[f.key]}`).join(" · "); }
  return String(v);
}

/** Every KPI report in scope, with the full answers; the M&E account can edit and remove. */
export default function KpiReportsPage() {
  const { can, user } = useAuth();
  const qc = useQueryClient();
  const nav = useNavigate();
  const [params] = useSearchParams();
  const store = useKpiStore();
  const [f, setF] = useState({ phase: "", district_id: "", week: "", date_from: "", date_to: "", mine: false });
  const query = qs(f);
  const rows = useQuery({ queryKey: ["me-kpi", "reports", query], queryFn: () => api.get<MeKpiReport[]>(`/me/kpi/reports${query}`) });
  const lists = useQuery({ queryKey: ["me-kpi", "summary", "all"], queryFn: () => api.get<MeKpiSummary>("/me/kpi/summary") });
  const spec = useQuery({ queryKey: ["me-kpi", "form"], queryFn: () => api.get<MeKpiSpec>("/me/kpi/form"), initialData: store.spec ?? undefined });
  const [open, setOpen] = useState<number | null>(params.get("open") ? Number(params.get("open")) : null);
  const [error, setError] = useState<unknown>(null);
  const remove = useMutation({ mutationFn: (x: MeKpiReport) => api.delete(`/me/kpi/reports/${x.id}`), onSuccess: () => { qc.invalidateQueries({ queryKey: ["me-kpi"] }); setOpen(null); }, onError: setError });
  useEffect(() => { if (params.get("open")) setOpen(Number(params.get("open"))); }, [params]);
  const data = rows.data ?? [];
  const current = data.find((x) => x.id === open) ?? null;
  const edit = (x: MeKpiReport) => {
    // bring the server copy onto this device as a draft with the same client_id, so sending it updates the report
    saveDraft({ client_id: x.client_id, phase: x.phase as MeKpiReportIn["phase"], report_date: x.report_date, week: x.week, district_id: x.district_id, chiefdom: x.chiefdom, section: x.section, team_id: x.team_id, sa_code: x.sa_code, ea_codes: x.ea_codes ?? [], practice_team: x.practice_team, respondent_name: x.respondent_name, respondent_role: x.respondent_role, collection_mode: x.collection_mode as MeKpiReportIn["collection_mode"], eas_urban: x.eas_urban, eas_rural: x.eas_rural, enumerators: x.enumerators, capi_version: x.capi_version, lat: x.lat, lng: x.lng, answers: x.answers }, store.geo);
    nav(`/me/kpi/report/${x.client_id}`);
  };

  return (
    <div className="max-w-7xl">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div><Link to="/me/kpi" className="inline-flex items-center gap-1 text-lg font-bold text-navy hover:underline">← M&amp;E Field Tool</Link><h1 className="text-2xl font-bold">KPI reports</h1><p className="text-sm text-slate-500">Every report sent from the field in your area. Click a row for the full answers.</p></div>
        <Link to="/me/kpi/dashboard" className="btn-outline">Dashboard</Link>
      </div>
      <ErrorBox error={error instanceof ApiError ? error.message : error} />
      <Card className="mb-4">
        <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-6">
          <select className="input" value={f.phase} onChange={(e) => setF({ ...f, phase: e.target.value })}><option value="">All phases</option>{PHASES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
          <select className="input" value={f.district_id} onChange={(e) => setF({ ...f, district_id: e.target.value })}><option value="">All districts</option>{(lists.data?.by_district ?? []).filter((g) => g.key !== "0").map((g) => <option key={g.key} value={g.key}>{g.label} ({g.reports})</option>)}</select>
          <select className="input" value={f.week} onChange={(e) => setF({ ...f, week: e.target.value })}><option value="">All weeks</option>{(lists.data?.by_week ?? []).map((g) => <option key={g.key} value={g.key}>{g.label} ({g.reports})</option>)}</select>
          <input className="input" type="date" value={f.date_from} onChange={(e) => setF({ ...f, date_from: e.target.value })} title="From" />
          <input className="input" type="date" value={f.date_to} onChange={(e) => setF({ ...f, date_to: e.target.value })} title="To" />
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.mine} onChange={(e) => setF({ ...f, mine: e.target.checked })} /> My reports only</label>
        </div>
      </Card>
      <Card>
        {rows.isLoading ? <Spinner /> : (
          <div className="overflow-x-auto">
            <table className="table">
              <thead><tr><th>Date</th><th>Phase</th><th>District</th><th>SA / team</th><th>Respondent</th><th>Officer</th><th className="text-right">Coverage</th><th className="text-right">Synced</th><th className="text-right">Errors</th><th className="text-right">Tablets</th><th>Overall</th><th>Flags</th></tr></thead>
              <tbody>
                {data.map((x) => (
                  <tr key={x.id} className={clsx("cursor-pointer hover:bg-slate-50", open === x.id && "bg-sky-50")} onClick={() => setOpen(open === x.id ? null : x.id)}>
                    <td className="whitespace-nowrap">{fmtDate(x.report_date)}{x.week ? <span className="text-xs text-slate-400"> · wk {x.week}</span> : ""}</td><td>{x.phase_label}</td><td>{x.district ?? "—"}</td>
                    <td>{x.sa_code ? <><b>{x.sa_code}</b>{x.sa_name ? <span className="text-xs text-slate-500"> {x.sa_name}</span> : ""}</> : x.practice_team ?? "—"}</td>
                    <td>{x.respondent_name ?? "—"}{x.respondent_role_label ? <span className="block text-xs text-slate-400">{x.respondent_role_label}</span> : ""}</td><td>{x.officer ?? "—"}</td>
                    <td className="text-right">{pct(x.metrics.coverage_pct)}</td><td className={clsx("text-right", x.metrics.synced_pct !== null && x.metrics.synced_pct < 80 && "font-semibold text-red-700")}>{pct(x.metrics.synced_pct)}</td>
                    <td className={clsx("text-right", x.metrics.error_pct !== null && x.metrics.error_pct > 5 && "font-semibold text-red-700")}>{pct(x.metrics.error_pct)}</td><td className="text-right">{pct(x.metrics.tablets_pct)}</td>
                    <td>{x.metrics.overall ? ["", "Poor", "Weak", "Good", "Very good"][x.metrics.overall] : "—"}</td>
                    <td className="text-xs">{x.metrics.safety_concern && <span className="mr-1 rounded-full bg-red-100 px-2 py-0.5 font-semibold text-red-800">Safety</span>}{x.metrics.escalation && <span className="mr-1 rounded-full bg-amber-100 px-2 py-0.5 font-semibold text-amber-800">Escalate</span>}{x.metrics.follow_up && <span className="rounded-full bg-sky-100 px-2 py-0.5 font-semibold text-sky-800">Follow-up</span>}</td>
                  </tr>
                ))}
                {data.length === 0 && <tr><td colSpan={12}><Empty text="No report for these filters." /></td></tr>}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {current && spec.data && (
        <div className="fixed inset-0 z-40 flex justify-end bg-black/40" onClick={() => setOpen(null)}>
          <div className="h-full w-full max-w-2xl overflow-y-auto bg-white shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <div className="sticky top-0 z-10 border-b border-slate-200 bg-white px-5 py-3">
              <div className="flex items-start justify-between gap-3">
                <div><div className="text-xs uppercase tracking-wide text-slate-400">{current.phase_label}{current.week ? ` · week ${current.week}` : ""}</div><h2 className="text-lg font-semibold">{current.district ?? "No district"}{current.sa_code ? ` · ${current.sa_code}` : current.practice_team ? ` · ${current.practice_team}` : ""} · {fmtDate(current.report_date)}</h2>
                  <div className="text-xs text-slate-500">{current.ea_codes.length ? `EAs ${current.ea_codes.join(", ")} · ` : ""}{current.chiefdom ? `${current.chiefdom} · ` : ""}{current.section ? `${current.section} · ` : ""}{current.respondent_name ?? ""}{current.respondent_role_label ? ` (${current.respondent_role_label})` : ""}{current.collection_mode_label ? ` · ${current.collection_mode_label.toLowerCase()}` : ""} · officer {current.officer ?? "—"} · sent {new Date(current.submitted_at).toLocaleString("en-GB")}{current.edited_by_name ? ` · edited by ${current.edited_by_name}` : ""}</div></div>
                <button className="text-slate-500 hover:text-slate-800" onClick={() => setOpen(null)}><X size={20} /></button>
              </div>
              {(can("me_kpi.manage") || current.user_id === user?.id) && (
                <div className="mt-3 flex gap-2">
                  <button className="btn-outline" onClick={() => edit(current)}><Pencil size={16} /> Edit and re-send</button>
                  {can("me_kpi.manage") && <button className="btn-outline text-red-700" onClick={() => { if (confirm("Remove this report?")) remove.mutate(current); }}><Trash2 size={16} /> Remove</button>}
                </div>
              )}
            </div>
            <div className="space-y-4 px-5 py-4 text-sm">
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                {[["Coverage", pct(current.metrics.coverage_pct)], ["Synced", pct(current.metrics.synced_pct)], ["Error rate", pct(current.metrics.error_pct)], ["Tablets", pct(current.metrics.tablets_pct)]].map(([l, v]) => <div key={l} className="rounded-md bg-slate-50 px-3 py-2"><div className="text-xs text-slate-500">{l}</div><div className="text-lg font-bold text-navy">{v}</div></div>)}
              </div>
              <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-slate-600 sm:grid-cols-3">
                <div>EAs: {current.eas_urban ?? "—"} urban · {current.eas_rural ?? "—"} rural</div><div>Enumerators: {current.enumerators ?? "—"}</div><div>CAPI version: {current.capi_version ?? "—"}</div>
                {current.lat && <div>GPS: {current.lat}, {current.lng}</div>}
              </div>
              {spec.data.sections.filter((s) => !s.phases || s.phases.includes(current.phase)).map((s) => {
                const items = s.items.filter((it) => (!it.phases || it.phases.includes(current.phase)) && current.answers[it.code] !== undefined);
                if (!items.length) return null;
                return (
                  <div key={s.code}>
                    <h3 className="mb-1 text-xs font-bold uppercase tracking-wide text-slate-500">{s.title}</h3>
                    <dl className="divide-y divide-slate-100 rounded-md border border-slate-200">
                      {items.map((it) => <div key={it.code} className="grid grid-cols-5 gap-2 px-3 py-1.5"><dt className="col-span-3 text-slate-600">{it.text}</dt><dd className="col-span-2 font-medium">{answerText(it, current.answers[it.code])}{current.answers[it.code + "_detail"] ? <span className="block text-xs font-normal text-slate-500">{String(current.answers[it.code + "_detail"])}</span> : null}</dd></div>)}
                    </dl>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
