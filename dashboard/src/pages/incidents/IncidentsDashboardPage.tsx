import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import clsx from "clsx";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AlertTriangle, ArrowUpRight, Clock, Download, Flame, Inbox, ShieldAlert, Siren } from "lucide-react";
import { ApiError, api, download, fmtDate, qs } from "../../api/client";
import type { Incident, IncidentDashboard } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { Card, Empty, ErrorBox, Spinner } from "../../components/ui";
import { CAT_COLOR, SEV, STATUS_COLOR, SeverityPill, StatusPill, ago, hours } from "./incidentUi";

/** The Census Incident Log dashboard: what needs action now, the trend, and where and why incidents happen. */
export default function IncidentsDashboardPage() {
  const { can } = useAuth();
  const [f, setF] = useState({ district_id: "", severity: "", phase: "", date_from: "", date_to: "" });
  const query = qs(f);
  const q = useQuery({ queryKey: ["incidents", "dashboard", query], queryFn: () => api.get<IncidentDashboard>(`/incidents/dashboard${query}`), refetchInterval: 60_000 });
  const all = useQuery({ queryKey: ["incidents", "dashboard", ""], queryFn: () => api.get<IncidentDashboard>("/incidents/dashboard") });
  const [error, setError] = useState<unknown>(null);
  if (q.isLoading) return <Spinner />;
  if (q.error || !q.data) return <ErrorBox error={q.error} />;
  const d = q.data;
  const districts = (all.data ?? d).by_district;
  const exportFile = async (format: "xlsx" | "pdf") => { setError(null); try { await download(`/incidents/export${qs({ ...f, format })}`, `incidents.${format}`); } catch (err) { setError(err); } };
  const sevData = d.by_severity.filter((x) => x.count);
  const statusData = d.by_status.filter((x) => x.count);
  const catData = d.by_category.filter((x) => x.total).sort((a, b) => b.total - a.total);
  const distData = d.by_district.filter((x) => x.total).sort((a, b) => b.open - a.open || b.total - a.total);
  const trend = d.trend.map((t) => ({ ...t, name: new Date(t.day + "T00:00:00").toLocaleDateString("en-GB", { day: "2-digit", month: "short" }) }));
  const filtered = Object.values(f).some(Boolean);

  return (
    <div className="max-w-7xl">
      <div className="mb-4 overflow-hidden rounded-2xl bg-gradient-to-br from-navy via-[#245a8c] to-[#7f1d1d] px-6 py-5 text-white shadow">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-xs uppercase tracking-[0.3em] text-sky-100/80">2026 Population and Housing Census</div>
            <h1 className="mt-1 text-2xl font-bold">Census Incident Log</h1>
            <p className="text-sm text-sky-100/90">Scope: <b>{d.scope}</b> · refreshed every minute · {d.reported_today} reported today, {d.reported_7_days} in the last 7 days, {d.resolved_7_days} resolved in the last 7 days</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {can("incidents.report") && <Link to="/incidents/register?new=1" className="inline-flex items-center gap-2 rounded-xl bg-white px-4 py-2 text-sm font-semibold text-navy shadow hover:bg-sky-50"><Siren size={16} /> Report an incident</Link>}
            {can("incidents.export") && <button className="inline-flex items-center gap-2 rounded-xl bg-white/15 px-4 py-2 text-sm font-semibold text-white hover:bg-white/25" onClick={() => exportFile("xlsx")}><Download size={16} /> Excel</button>}
            {can("incidents.export") && <button className="inline-flex items-center gap-2 rounded-xl bg-white/15 px-4 py-2 text-sm font-semibold text-white hover:bg-white/25" onClick={() => exportFile("pdf")}><Download size={16} /> PDF brief</button>}
          </div>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <Big icon={<Inbox size={18} />} label="Open incidents" value={d.open} sub={`${d.total} in total`} />
          <Big icon={<AlertTriangle size={18} />} label="New, not acknowledged" value={d.new_unacknowledged} tone={d.new_unacknowledged ? "red" : "ok"} sub="needs a first response" />
          <Big icon={<Flame size={18} />} label="Critical open" value={d.critical_open} tone={d.critical_open ? "red" : "ok"} sub="stops work or endangers people" />
          <Big icon={<Clock size={18} />} label="Overdue" value={d.overdue} tone={d.overdue ? "amber" : "ok"} sub={`${d.due_today} due today`} />
          <Big icon={<ShieldAlert size={18} />} label="Unknown SA code" value={d.unrecognised_sa} tone={d.unrecognised_sa ? "amber" : "ok"} sub="district to be set" />
          <Big icon={<ArrowUpRight size={18} />} label="Time to resolve" value={hours(d.hours_to_resolve_median)} sub={`median · acknowledge ${hours(d.hours_to_acknowledge_median)}`} />
        </div>
      </div>
      <ErrorBox error={error instanceof ApiError ? error.message : error} />

      <Card className="mb-4">
        <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-5">
          <select className="input" value={f.district_id} onChange={(e) => setF({ ...f, district_id: e.target.value })}><option value="">All districts</option>{districts.map((x) => <option key={x.district_id} value={x.district_id}>{x.district} ({x.total})</option>)}</select>
          <select className="input" value={f.severity} onChange={(e) => setF({ ...f, severity: e.target.value })}><option value="">All severities</option>{Object.entries(SEV).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}</select>
          <select className="input" value={f.phase} onChange={(e) => setF({ ...f, phase: e.target.value })}><option value="">All phases</option>{d.by_phase.map((x) => <option key={x.code} value={x.code}>{x.label}</option>)}</select>
          <input className="input" type="date" value={f.date_from} onChange={(e) => setF({ ...f, date_from: e.target.value })} title="Reported from" />
          <input className="input" type="date" value={f.date_to} onChange={(e) => setF({ ...f, date_to: e.target.value })} title="Reported to" />
        </div>
        {filtered && <div className="mt-2 text-xs text-sky-900">Every figure and export follows these filters. <button className="font-semibold underline" onClick={() => setF({ district_id: "", severity: "", phase: "", date_from: "", date_to: "" })}>Clear</button></div>}
      </Card>

      {d.total === 0 ? <Card><Empty text="No incident recorded yet. Supervisors report on the public page with their SA code; staff with accounts use Report an incident." /></Card> : (
        <div className="grid gap-4 lg:grid-cols-3">
          <Card title="Needs action now" className="lg:col-span-2" action={<Link to="/incidents/register?status=OPEN" className="text-xs text-navy underline">Open the register</Link>}>
            {d.needs_action.length === 0 ? <Empty text="Nothing waiting: no new, critical or overdue incident" /> : (
              <ul className="divide-y divide-slate-100">
                {d.needs_action.map((x) => <NeedsRow key={x.id} x={x} />)}
              </ul>
            )}
          </Card>
          <Card title="By severity">
            <Donut data={sevData.map((x) => ({ name: x.label, value: x.count, color: SEV[x.code as keyof typeof SEV]?.color ?? "#94a3b8" }))} center={`${d.open} open`} />
            <div className="mt-2 grid grid-cols-3 gap-2 text-center text-xs">{d.by_severity.map((x) => <div key={x.code}><div className="text-lg font-bold" style={{ color: SEV[x.code as keyof typeof SEV]?.color }}>{x.count}</div><div className="text-slate-500">{x.label}</div></div>)}</div>
          </Card>
          <Card title="Reported and resolved · last 30 days" className="lg:col-span-2">
            <div style={{ height: 240 }}>
              <ResponsiveContainer>
                <AreaChart data={trend} margin={{ left: 0, right: 10 }}>
                  <defs>
                    <linearGradient id="gOpen" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#b91c1c" stopOpacity={0.35} /><stop offset="95%" stopColor="#b91c1c" stopOpacity={0.02} /></linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} interval={4} /><YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                  <Tooltip /><Legend />
                  <Area type="monotone" dataKey="open_end_of_day" name="Open at end of day" stroke="#b91c1c" fill="url(#gOpen)" isAnimationActive={false} />
                  <Bar dataKey="reported" name="Reported" fill="#1F4E79" isAnimationActive={false} />
                  <Bar dataKey="resolved" name="Resolved" fill="#15803d" isAnimationActive={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Card>
          <Card title="By status">
            <Donut data={statusData.map((x) => ({ name: x.label, value: x.count, color: STATUS_COLOR[x.code] }))} center={`${d.total} total`} />
          </Card>
          <Card title="What is going wrong · by category" className="lg:col-span-2">
            {catData.length === 0 ? <Empty /> : (
              <div style={{ height: 40 + 32 * catData.length }}>
                <ResponsiveContainer>
                  <BarChart data={catData} layout="vertical" margin={{ left: 10, right: 30 }}>
                    <XAxis type="number" allowDecimals={false} hide /><YAxis type="category" dataKey="label" width={190} tick={{ fontSize: 12 }} />
                    <Tooltip formatter={(v: number, name: string) => [v, name]} />
                    <Legend />
                    <Bar dataKey="critical" name="Critical" stackId="a" fill="#b91c1c" isAnimationActive={false} />
                    <Bar dataKey="major" name="Major" stackId="a" fill="#d97706" isAnimationActive={false} />
                    <Bar dataKey="minor" name="Minor" stackId="a" fill="#0ea5e9" isAnimationActive={false} radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
            <div className="mt-2 flex flex-wrap gap-2 text-xs">
              {catData.map((c) => {
                const up = c.last_7_days - c.previous_7_days;
                return <span key={c.category} className="rounded-full bg-slate-100 px-2 py-0.5" style={{ borderLeft: `3px solid ${CAT_COLOR[c.category]}` }}>{c.label}: {c.open} open{up !== 0 && <span className={up > 0 ? "text-red-700" : "text-emerald-700"}> · {up > 0 ? "▲" : "▼"} {Math.abs(up)} vs previous week</span>}</span>;
              })}
            </div>
          </Card>
          <Card title="Most frequent sub-categories">
            {d.by_subcategory.length === 0 ? <Empty /> : <ul className="text-sm">{d.by_subcategory.slice(0, 10).map((x) => <li key={x.code} className="flex justify-between border-t border-slate-100 py-1"><span className="truncate pr-2">{x.label}</span><b>{x.count}</b></li>)}</ul>}
          </Card>
          <Card title="Where · by district" className="lg:col-span-3">
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
              {d.by_district.map((r) => {
                const tone = r.critical_open ? "border-red-500 bg-red-50" : r.overdue ? "border-amber-500 bg-amber-50" : r.open ? "border-navy bg-sky-50" : "border-slate-200 bg-white";
                return (
                  <Link key={r.district_id} to={`/incidents/register?district_id=${r.district_id}&status=OPEN`} className={clsx("rounded-xl border-l-4 p-3 shadow-sm transition hover:shadow", tone)}>
                    <div className="flex items-start justify-between"><div><div className="font-semibold text-slate-800">{r.district}</div><div className="text-xs text-slate-500">{r.region}</div></div><div className="text-2xl font-bold text-navy">{r.open}</div></div>
                    <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-600">
                      <span className={r.new ? "font-semibold text-red-700" : ""}>{r.new} new</span><span className={r.critical_open ? "font-semibold text-red-700" : ""}>{r.critical_open} critical</span><span className={r.overdue ? "font-semibold text-amber-700" : ""}>{r.overdue} overdue</span><span>{r.resolved} resolved</span>
                      {r.per_100_eas !== null && <span className="text-slate-400">{r.per_100_eas} per 100 EAs</span>}{r.median_hours_to_resolve !== null && <span className="text-slate-400">median {hours(r.median_hours_to_resolve)}</span>}
                    </div>
                  </Link>
                );
              })}
            </div>
            {distData.length > 1 && (
              <div className="mt-4" style={{ height: 200 }}>
                <ResponsiveContainer>
                  <BarChart data={distData} margin={{ left: 0, right: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="district" tick={{ fontSize: 11 }} interval={0} angle={-20} textAnchor="end" height={50} /><YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                    <Tooltip /><Legend />
                    <Bar dataKey="open" name="Open" fill="#1F4E79" isAnimationActive={false} />
                    <Bar dataKey="overdue" name="Overdue" fill="#d97706" isAnimationActive={false} />
                    <Bar dataKey="resolved" name="Resolved" fill="#15803d" isAnimationActive={false} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </Card>
          <Card title="Owners">
            {d.by_owner.length === 0 ? <Empty /> : (
              <table className="table text-sm"><thead><tr><th>Owner</th><th className="text-right">Open</th><th className="text-right">Overdue</th><th className="text-right">Resolved</th></tr></thead>
                <tbody>{d.by_owner.slice(0, 10).map((o) => <tr key={o.owner_id ?? "none"}><td className={o.owner_id ? "" : "text-red-700"}>{o.owner}</td><td className="text-right">{o.open}</td><td className={clsx("text-right", o.overdue && "font-semibold text-amber-700")}>{o.overdue}</td><td className="text-right">{o.resolved}</td></tr>)}</tbody></table>
            )}
          </Card>
          <Card title="Supervisory areas with most incidents">
            {d.top_sas.length === 0 ? <Empty /> : (
              <table className="table text-sm"><thead><tr><th>SA code</th><th>District</th><th className="text-right">Incidents</th><th className="text-right">Open</th><th className="text-right">Critical</th></tr></thead>
                <tbody>{d.top_sas.map((s) => <tr key={s.sa_code ?? s.team_code ?? ""}><td className="font-mono">{s.sa_code ?? s.team_code}</td><td>{s.district ?? ""}</td><td className="text-right">{s.incidents}</td><td className="text-right">{s.open}</td><td className={clsx("text-right", s.critical && "font-semibold text-red-700")}>{s.critical}</td></tr>)}</tbody></table>
            )}
          </Card>
          <div className="grid gap-4"><MiniBars title="By census phase" rows={d.by_phase} /><MiniBars title="Who reports" rows={d.by_reporter_role} /><MiniBars title="Handled at" rows={d.by_level} /></div>
          <Card title="Latest incidents" className="lg:col-span-3">
            <div className="overflow-x-auto"><table className="table">
              <thead><tr><th>Number</th><th>Severity</th><th>Status</th><th>District</th><th>Category</th><th>Title</th><th>Reported</th><th>Owner</th></tr></thead>
              <tbody>{d.recent.map((x) => <tr key={x.id}><td><Link to={`/incidents/register?open=${x.id}`} className="font-mono text-navy hover:underline">{x.number}</Link></td><td><SeverityPill severity={x.severity} /></td><td><StatusPill status={x.status} label={x.status_label} /></td><td>{x.district ?? <span className="text-amber-700">not set</span>}</td><td>{x.category_label}</td><td className="max-w-xs truncate" title={x.title}>{x.title}</td><td className="whitespace-nowrap text-slate-500" title={fmtDate(x.reported_at)}>{ago(x.reported_at)}</td><td>{x.owner_name ?? <span className="text-red-700">unassigned</span>}</td></tr>)}</tbody>
            </table></div>
          </Card>
        </div>
      )}
    </div>
  );
}

function Big({ icon, label, value, sub, tone = "navy" }: { icon: React.ReactNode; label: string; value: number | string; sub?: string; tone?: "navy" | "red" | "amber" | "ok" }) {
  const cls = { navy: "bg-white/10", red: "bg-red-500/40 ring-1 ring-red-200/60", amber: "bg-amber-400/30 ring-1 ring-amber-200/60", ok: "bg-emerald-500/25" }[tone];
  return (
    <div className={clsx("rounded-xl p-3 backdrop-blur-sm", cls)}>
      <div className="flex items-center gap-2 text-xs font-medium text-sky-50/90">{icon} {label}</div>
      <div className="mt-1 text-3xl font-bold leading-none">{value}</div>
      {sub && <div className="mt-1 text-[11px] text-sky-50/75">{sub}</div>}
    </div>
  );
}

function Donut({ data, center }: { data: { name: string; value: number; color: string }[]; center: string }) {
  if (!data.length) return <Empty />;
  return (
    <div className="relative" style={{ height: 190 }}>
      <ResponsiveContainer>
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={2} isAnimationActive={false}>{data.map((x) => <Cell key={x.name} fill={x.color} />)}</Pie>
          <Tooltip />
        </PieChart>
      </ResponsiveContainer>
      <div className="pointer-events-none absolute inset-0 flex items-center justify-center text-center text-sm font-semibold text-slate-700">{center}</div>
    </div>
  );
}

function MiniBars({ title, rows }: { title: string; rows: { code: string; label: string; count: number; pct: number }[] }) {
  const max = Math.max(1, ...rows.map((r) => r.count));
  return (
    <Card title={title}>
      {rows.every((r) => !r.count) ? <Empty /> : rows.filter((r) => r.count).map((r) => (
        <div key={r.code} className="mb-1.5">
          <div className="flex justify-between text-xs"><span>{r.label}</span><span className="text-slate-500">{r.count} · {r.pct}%</span></div>
          <div className="h-2 rounded-full bg-slate-100"><div className="h-2 rounded-full bg-navy" style={{ width: `${(100 * r.count) / max}%` }} /></div>
        </div>
      ))}
    </Card>
  );
}

function NeedsRow({ x }: { x: Incident }) {
  const why = x.status === "NEW" ? `New · ${ago(x.reported_at)}` : x.overdue ? `Overdue since ${fmtDate(x.due_at)}` : "Critical, open";
  return (
    <li className="flex items-start gap-3 py-2">
      <span className={clsx("mt-1 h-3 w-3 shrink-0 rounded-full", SEV[x.severity].dot)} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2"><Link to={`/incidents/register?open=${x.id}`} className="font-mono text-sm font-semibold text-navy hover:underline">{x.number}</Link><StatusPill status={x.status} label={x.status_label} /><span className="text-xs text-slate-500">{x.district ?? "district not set"}{x.sa_code ? ` · SA ${x.sa_code}` : ""}</span></div>
        <div className="truncate text-sm text-slate-800" title={x.title}>{x.title}</div>
        <div className="text-xs text-slate-500">{x.category_label}{x.subcategory_label ? ` · ${x.subcategory_label}` : ""} · owner {x.owner_name ?? <span className="text-red-700">unassigned</span>}</div>
      </div>
      <div className={clsx("shrink-0 text-right text-xs font-semibold", x.status === "NEW" || x.overdue ? "text-red-700" : "text-amber-700")}>{why}</div>
    </li>
  );
}
