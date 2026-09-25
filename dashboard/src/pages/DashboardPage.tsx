import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, fmt, qs } from "../api/client";
import type { AgeingBand, Bucket, OverdueRow, Summary, TrendPoint } from "../api/types";
import FiltersBar from "../components/FiltersBar";
import { Card, Empty, ErrorBox, KpiTile, Spinner } from "../components/ui";
import { filtersToQuery, useFilters } from "../hooks/useFilters";

const NAVY = "#1F4E79";
const GREEN = "#2E7D32";
const AMBER = "#F2B84B";
const RED = "#C62828";

export default function DashboardPage() {
  const [f, update] = useFilters();
  const q = qs(filtersToQuery(f));
  const nav = useNavigate();
  const summary = useQuery({ queryKey: ["summary", q], queryFn: () => api.get<Summary>(`/dashboard/summary${q}`) });
  const byDistrict = useQuery({ queryKey: ["by-district", q], queryFn: () => api.get<Bucket[]>(`/dashboard/by-district${q}`) });
  const byCategory = useQuery({ queryKey: ["by-category", q], queryFn: () => api.get<Bucket[]>(`/dashboard/by-category${q}`) });
  const trend = useQuery({ queryKey: ["trend", q], queryFn: () => api.get<TrendPoint[]>(`/dashboard/trend${q}`) });
  const ageing = useQuery({ queryKey: ["ageing", q], queryFn: () => api.get<AgeingBand[]>(`/dashboard/ageing${q}`) });
  const overdue = useQuery({ queryKey: ["overdue", q], queryFn: () => api.get<OverdueRow[]>(`/dashboard/overdue${q}`) });
  const s = summary.data;

  return (
    <div>
      <header className="mb-4 flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-sm text-slate-500">
            Data as of the latest tablet sync{s?.last_sync_at ? ` · last sync ${fmt(s.last_sync_at)}` : ""}. Monitors who have not synced show on the Field Monitors page.
          </p>
        </div>
      </header>
      <FiltersBar compact />
      <ErrorBox error={summary.error} />
      {s && (
        <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          <KpiTile label="Total errors" value={s.total} onClick={() => nav(`/errors${q}`)} />
          <KpiTile label="Resolved" value={s.resolved} tone="green" onClick={() => { update({ status: "RESOLVED", overdue_only: false }); nav(`/errors${qs({ ...filtersToQuery(f), status: "RESOLVED" })}`); }} />
          <KpiTile label="Unresolved" value={s.unresolved} tone="amber" onClick={() => nav(`/errors${qs({ ...filtersToQuery(f), status: "UNRESOLVED" })}`)} />
          <KpiTile label="Overdue follow-ups" value={s.overdue} tone="red" onClick={() => nav(`/errors${qs({ ...filtersToQuery(f), status: "UNRESOLVED", overdue_only: true })}`)} />
          <KpiTile label="Resolution rate" value={`${s.resolution_rate}%`} tone="green" />
          <KpiTile label="Median days to resolve" value={s.median_days_to_resolve ?? "—"} />
        </div>
      )}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card title="By district (click a bar to filter)">
          {byDistrict.isLoading ? <Spinner /> : byDistrict.data?.length ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={byDistrict.data} onClick={(e) => { const k = (e?.activePayload?.[0]?.payload as Bucket | undefined)?.key; if (typeof k === "number") update({ district_id: [k], team_id: undefined }); }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="label" tick={{ fontSize: 11 }} interval={0} angle={-15} textAnchor="end" height={50} />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Legend />
                <Bar isAnimationActive={false} dataKey="resolved" name="Resolved" stackId="a" fill={GREEN} />
                <Bar isAnimationActive={false} dataKey="unresolved" name="Unresolved" stackId="a" fill={AMBER} />
                <Bar isAnimationActive={false} dataKey="overdue" name="of which overdue" fill={RED} />
              </BarChart>
            </ResponsiveContainer>
          ) : <Empty />}
        </Card>
        <Card title="By error category">
          {byCategory.isLoading ? <Spinner /> : byCategory.data?.length ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={byCategory.data} layout="vertical" margin={{ left: 40 }} onClick={(e) => { const k = (e?.activePayload?.[0]?.payload as Bucket | undefined)?.key; if (typeof k === "number") update({ category_id: k }); }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis type="number" allowDecimals={false} />
                <YAxis type="category" dataKey="label" width={160} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend />
                <Bar isAnimationActive={false} dataKey="resolved" name="Resolved" stackId="a" fill={GREEN} />
                <Bar isAnimationActive={false} dataKey="unresolved" name="Unresolved" stackId="a" fill={AMBER} />
              </BarChart>
            </ResponsiveContainer>
          ) : <Empty />}
        </Card>
        <Card title="Errors received and resolved per day">
          {trend.isLoading ? <Spinner /> : trend.data?.length ? (
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={trend.data}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="period" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Legend />
                <Line isAnimationActive={false} type="monotone" dataKey="received" name="Received" stroke={NAVY} strokeWidth={2} dot={false} />
                <Line isAnimationActive={false} type="monotone" dataKey="resolved" name="Resolved" stroke={GREEN} strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          ) : <Empty />}
        </Card>
        <Card title="Unresolved errors by age">
          {ageing.isLoading ? <Spinner /> : (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={ageing.data ?? []}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="band" />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Bar isAnimationActive={false} dataKey="count" name="Unresolved" fill={AMBER} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>
      </div>
      <Card title={`Overdue follow-ups (${overdue.data?.length ?? 0})`} className="mt-4">
        {overdue.isLoading ? <Spinner /> : overdue.data?.length ? (
          <div className="overflow-x-auto">
            <table className="table">
              <thead><tr><th>Error</th><th>District</th><th>Team</th><th>Category</th><th>Supervisor</th><th>Field Monitor</th><th>Follow-up due</th><th>Hours overdue</th></tr></thead>
              <tbody>
                {overdue.data.slice(0, 25).map((r) => (
                  <tr key={r.id} className="cursor-pointer hover:bg-slate-50" onClick={() => nav(`/errors/${r.id}`)}>
                    <td className="font-medium">{r.display_id}</td><td>{r.district}</td><td>{r.team}</td><td>{r.category}</td><td>{r.supervisor_name}</td><td>{r.monitor}</td><td>{fmt(r.next_follow_up_at)}</td><td className="text-red-700 font-semibold">{r.hours_overdue}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {overdue.data.length > 25 && <p className="mt-2 text-xs text-slate-500">Showing 25 of {overdue.data.length}. Open Errors with the Overdue filter for the full list.</p>}
          </div>
        ) : <Empty text="Nothing overdue" />}
      </Card>
    </div>
  );
}
