import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import clsx from "clsx";
import { api, fmt, fmtDate, qs } from "../../api/client";
import type { District, DqmOptions, DqmReportListRow, Named } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { Card, Empty, ErrorBox, Field, Spinner } from "../../components/ui";

export function StatusPill({ status }: { status: string }) {
  const cls = status === "RECEIVED" ? "bg-green-100 text-green-800" : status === "SUBMITTED" ? "bg-navy-light text-navy-dark" : "bg-slate-100 text-slate-700";
  return <span className={clsx("inline-block rounded-full px-2 py-0.5 text-xs font-semibold", cls)}>{status.charAt(0) + status.slice(1).toLowerCase()}</span>;
}

export default function DqmReportsPage() {
  const { user } = useAuth();
  const nav = useNavigate();
  const [params, setParams] = useSearchParams();
  const set = (k: string, v: string) => { const n = new URLSearchParams(params); if (v) n.set(k, v); else n.delete(k); setParams(n, { replace: true }); };
  const filters = { district_id: params.get("district_id") || undefined, region_id: params.get("region_id") || undefined, status: params.get("status") || undefined, date_from: params.get("date_from") || undefined, date_to: params.get("date_to") || undefined, deleted: params.get("deleted") === "true" };
  const q = qs(filters);
  const rows = useQuery({ queryKey: ["dqm-reports", q], queryFn: () => api.get<DqmReportListRow[]>(`/dqm-reports${q}`) });
  const options = useQuery({ queryKey: ["dqm-options"], queryFn: () => api.get<DqmOptions>("/dqm-reports/options") });
  const districts = useQuery({ queryKey: ["ref", "districts"], queryFn: () => api.get<District[]>("/admin/reference/districts"), staleTime: 300_000 });
  const regions = useQuery({ queryKey: ["ref", "regions"], queryFn: () => api.get<Named[]>("/admin/reference/regions"), staleTime: 300_000 });
  const isDistrict = user?.role === "DISTRICT_DQM";
  const canNational = user?.role === "NATIONAL_DQM" || user?.role === "ADMIN";
  const canRegional = canNational || user?.role === "REGIONAL";
  const today = new Date().toISOString().slice(0, 10);
  const todayDone = rows.data?.some((r) => r.report_date === today && r.status !== "DRAFT");

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">DQM reports 2026 SLPHC Data Quality Management Daily Reporting Tool</h1>
          <p className="text-sm text-slate-500">One report per district per day, submitted to the National Data Quality Manager.</p>
        </div>
        <div className="flex gap-2">
          <Link to={canNational ? "/dqm/analytics/national" : canRegional ? "/dqm/analytics/region" : "/dqm/analytics/district"} className="btn-outline">Charts</Link>
          {canRegional && <Link to="/dqm/summary/region" className="btn-outline">Regional summary</Link>}
          {canNational && <Link to="/dqm/summary/national" className="btn-outline">National summary</Link>}
          {options.data?.can_create && <Link to="/dqm/reports/new" className="btn-primary">New daily report</Link>}
        </div>
      </div>
      {isDistrict && !rows.isLoading && (
        <div className={clsx("mb-4 rounded-md border p-3 text-sm", todayDone ? "border-green-200 bg-green-50 text-green-800" : "border-amber/60 bg-amber/10 text-amber-900")}>
          {todayDone ? `Today's report (${fmtDate(today)}) has been submitted.` : `Today's report (${fmtDate(today)}) has not been submitted yet.`}
        </div>
      )}
      <div className="card mb-4 grid grid-cols-2 gap-3 md:grid-cols-5">
        {!isDistrict && (
          <Field label="Region">
            <select className="input" value={filters.region_id ?? ""} onChange={(e) => set("region_id", e.target.value)}>
              <option value="">All</option>
              {regions.data?.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
            </select>
          </Field>
        )}
        {!isDistrict && (
          <Field label="District">
            <select className="input" value={filters.district_id ?? ""} onChange={(e) => set("district_id", e.target.value)}>
              <option value="">All</option>
              {districts.data?.filter((d) => !filters.region_id || String(d.region_id) === filters.region_id).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          </Field>
        )}
        <Field label="Status">
          <select className="input" value={filters.status ?? ""} onChange={(e) => set("status", e.target.value)}>
            <option value="">All</option>
            <option value="DRAFT">Draft</option>
            <option value="SUBMITTED">Submitted</option>
            <option value="RECEIVED">Received</option>
          </select>
        </Field>
        <Field label="From"><input type="date" className="input" value={filters.date_from ?? ""} onChange={(e) => set("date_from", e.target.value)} /></Field>
        <Field label="To"><input type="date" className="input" value={filters.date_to ?? ""} onChange={(e) => set("date_to", e.target.value)} /></Field>
        {options.data?.can_delete && <label className="flex items-end gap-1 pb-2 text-sm text-slate-600"><input type="checkbox" checked={filters.deleted} onChange={(e) => set("deleted", e.target.checked ? "true" : "")} /> Show deleted</label>}
      </div>
      <Card title={`${rows.data?.length ?? 0} ${filters.deleted ? "deleted " : ""}reports`}>
        <ErrorBox error={rows.error} />
        {rows.isLoading ? <Spinner /> : rows.data?.length ? (
          <div className="overflow-x-auto">
            <table className="table">
              <thead><tr><th>Date</th><th>District</th><th>Region</th><th>Period</th><th>Status</th><th>Teams reviewed</th><th>Certified</th><th>Reint. received</th><th>Reint. certified</th><th>High-discrepancy</th><th>Open issues</th><th>Prepared by</th><th>Submitted</th><th>Received</th></tr></thead>
              <tbody>
                {rows.data.map((r) => (
                  <tr key={r.id} className="cursor-pointer hover:bg-slate-50" onClick={() => nav(`/dqm/reports/${r.id}`)}>
                    <td className="whitespace-nowrap font-medium">{fmtDate(r.report_date)}</td><td>{r.district}</td><td>{r.region}</td>
                    <td>{r.period.charAt(0) + r.period.slice(1).toLowerCase()} day {r.day_number}</td>
                    <td><StatusPill status={r.status} /></td>
                    <td>{r.teams_reviewed ?? ""}</td><td>{r.teams_certified ?? ""}</td><td>{r.reinterviews_received ?? ""}</td><td>{r.reinterviews_certified ?? ""}</td>
                    <td className={r.high_errors ? "font-semibold text-red-700" : ""}>{r.high_errors}</td>
                    <td className={r.open_issues ? "font-semibold text-amber-800" : ""}>{r.open_issues}</td>
                    <td>{r.prepared_name}</td><td className="whitespace-nowrap">{fmt(r.submitted_at)}</td><td className="whitespace-nowrap">{fmt(r.received_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <Empty text="No reports yet" />}
      </Card>
    </div>
  );
}
