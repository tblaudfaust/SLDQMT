import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import clsx from "clsx";
import { api, fmt, fmtDate, qs } from "../../api/client";
import type { CheckoutListRow, District, ExitOptions, Named } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { Card, Empty, ErrorBox, Field, Spinner } from "../../components/ui";

export const STATUS_LABEL: Record<string, string> = { DRAFT: "Draft", SUBMITTED: "Submitted", NATIONAL_SIGNED: "Countersigned", CLEARED: "Cleared" };
export const DECISION_SHORT: Record<string, string> = { CLEARED_PAYMENT: "Cleared: payment", CLEARED_REDEPLOYMENT: "Cleared: redeploy", CONDITIONAL: "Conditional", NOT_CLEARED: "Not cleared" };

export function CheckoutStatusPill({ status, decision }: { status: string; decision?: string | null }) {
  const cls = status === "CLEARED" ? (decision === "NOT_CLEARED" ? "bg-red-100 text-red-800" : decision === "CONDITIONAL" ? "bg-amber/30 text-amber-900" : "bg-green-100 text-green-800") : status === "NATIONAL_SIGNED" ? "bg-navy-light text-navy-dark" : status === "SUBMITTED" ? "bg-blue-50 text-blue-800" : "bg-slate-100 text-slate-700";
  const label = status === "CLEARED" && decision ? DECISION_SHORT[decision] : STATUS_LABEL[status] ?? status;
  return <span className={clsx("inline-block whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-semibold", cls)}>{label}</span>;
}

export default function ExitCheckoutsPage() {
  const { user } = useAuth();
  const nav = useNavigate();
  const [params, setParams] = useSearchParams();
  const set = (k: string, v: string) => { const n = new URLSearchParams(params); if (v) n.set(k, v); else n.delete(k); setParams(n, { replace: true }); };
  const filters = { district_id: params.get("district_id") || undefined, region_id: params.get("region_id") || undefined, role: params.get("role") || undefined, status: params.get("status") || undefined, decision: params.get("decision") || undefined, search: params.get("search") || undefined, deleted: params.get("deleted") === "true" };
  const q = qs(filters);
  const rows = useQuery({ queryKey: ["exit-checkouts", q], queryFn: () => api.get<CheckoutListRow[]>(`/exit-checkouts${q}`) });
  const options = useQuery({ queryKey: ["exit-options"], queryFn: () => api.get<ExitOptions>("/exit-checkouts/options") });
  const districts = useQuery({ queryKey: ["ref", "districts"], queryFn: () => api.get<District[]>("/admin/reference/districts"), staleTime: 300_000 });
  const regions = useQuery({ queryKey: ["ref", "regions"], queryFn: () => api.get<Named[]>("/admin/reference/regions"), staleTime: 300_000 });
  const isDistrict = user?.role === "DISTRICT_DQM";
  const isNational = user?.role === "NATIONAL_DQM" || user?.role === "ADMIN";
  const summaryLevel = isNational ? "national" : user?.role === "REGIONAL" ? "region" : "district";
  const counts = { total: rows.data?.length ?? 0, awaiting: rows.data?.filter((r) => r.status === "SUBMITTED" || r.status === "NATIONAL_SIGNED").length ?? 0, cleared: rows.data?.filter((r) => r.status === "CLEARED").length ?? 0 };

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Field exit protocol</h1>
          <p className="text-sm text-slate-500">Data Quality Manager check-out form for supervisors and enumerators: one per field staff member leaving the field. District DQM certifies, National DQM countersigns and records the Director's clearance decision.</p>
        </div>
        <div className="flex gap-2">
          <Link to={`/dqm/exit/summary/${summaryLevel}`} className="btn-outline">Summary and charts</Link>
          {options.data?.can_create && <Link to="/dqm/exit/new" className="btn-primary">New check-out</Link>}
        </div>
      </div>
      <div className="card mb-4 grid grid-cols-2 gap-3 md:grid-cols-6">
        {!isDistrict && (
          <Field label="Region"><select className="input" value={filters.region_id ?? ""} onChange={(e) => set("region_id", e.target.value)}><option value="">All</option>{regions.data?.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}</select></Field>
        )}
        {!isDistrict && (
          <Field label="District"><select className="input" value={filters.district_id ?? ""} onChange={(e) => set("district_id", e.target.value)}><option value="">All</option>{districts.data?.filter((d) => !filters.region_id || String(d.region_id) === filters.region_id).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select></Field>
        )}
        <Field label="Role"><select className="input" value={filters.role ?? ""} onChange={(e) => set("role", e.target.value)}><option value="">All</option><option value="ENUMERATOR">Enumerator</option><option value="SUPERVISOR">Supervisor</option></select></Field>
        <Field label="Status"><select className="input" value={filters.status ?? ""} onChange={(e) => set("status", e.target.value)}><option value="">All</option>{Object.entries(STATUS_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field>
        <Field label="Decision"><select className="input" value={filters.decision ?? ""} onChange={(e) => set("decision", e.target.value)}><option value="">All</option>{Object.entries(DECISION_SHORT).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field>
        <Field label="Search"><input className="input" placeholder="name, login ID, SA/EA" defaultValue={filters.search ?? ""} onKeyDown={(e) => { if (e.key === "Enter") set("search", (e.target as HTMLInputElement).value); }} /></Field>
        {options.data?.can_delete && <label className="flex items-end gap-1 pb-2 text-sm text-slate-600"><input type="checkbox" checked={filters.deleted} onChange={(e) => set("deleted", e.target.checked ? "true" : "")} /> Show deleted</label>}
      </div>
      <Card title={filters.deleted ? `${counts.total} deleted check-outs` : `${counts.total} check-outs · ${counts.awaiting} awaiting national action · ${counts.cleared} cleared`}>
        <ErrorBox error={rows.error} />
        {rows.isLoading ? <Spinner /> : rows.data?.length ? (
          <div className="overflow-x-auto">
            <table className="table">
              <thead><tr><th>Field staff</th><th>Role</th><th>District</th><th>Team</th><th>Status</th><th>Checklist "No"</th><th>Items not returned</th><th>Deadline</th><th>Submitted</th><th>Updated</th></tr></thead>
              <tbody>
                {rows.data.map((r) => (
                  <tr key={r.id} className="cursor-pointer hover:bg-slate-50" onClick={() => nav(`/dqm/exit/${r.id}`)}>
                    <td className="font-medium">{r.staff_name}<div className="text-xs text-slate-400">{r.login_id}</div></td>
                    <td>{r.role === "SUPERVISOR" ? "Supervisor" : "Enumerator"}</td>
                    <td>{r.district}<div className="text-xs text-slate-400">{r.region}</div></td>
                    <td className="text-xs">{r.team}</td>
                    <td><CheckoutStatusPill status={r.status} decision={r.decision} /></td>
                    <td className={clsx("tabular-nums", r.checklist_no && "font-semibold text-red-700")}>{r.checklist_no}</td>
                    <td className={clsx("tabular-nums", r.items_missing && "font-semibold text-amber-800")}>{r.items_missing}</td>
                    <td className={clsx("whitespace-nowrap", r.deadline && new Date(r.deadline) < new Date() && r.decision !== "CLEARED_PAYMENT" && r.decision !== "CLEARED_REDEPLOYMENT" && "text-red-700")}>{fmtDate(r.deadline)}</td>
                    <td className="whitespace-nowrap">{fmt(r.submitted_at)}</td>
                    <td className="whitespace-nowrap">{fmt(r.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <Empty text="No check-outs yet" />}
      </Card>
    </div>
  );
}
