import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import clsx from "clsx";
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, download, fmtDate, qs } from "../../api/client";
import type { District, Named } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { Card, ErrorBox, Field, KpiTile, Spinner } from "../../components/ui";

// Validated palette (dataviz reference instance, light surface).
const C = {
  blue: "#2a78d6", aqua: "#1baf7a", orange: "#eb6834",
  bandLow: "#86b6ef", bandMid: "#2a78d6", bandHigh: "#104281",
  none: "#e1e0d9", draft: "#cde2fb", submitted: "#5598e7", received: "#104281",
  grid: "#e1e0d9", axis: "#898781", surface: "#ffffff",
};

interface TrendPoint { date: string; reports: number; teams_reviewed: number; teams_certified: number; reint_received: number; reint_certified: number; reint_pending: number; low: number; medium: number; high: number; outlier: number; gps: number; sync: number; issues_open: number; issues_resolved: number }
interface UnitPoint extends Omit<TrendPoint, "date"> { key: number; label: string; submitted: number; received: number; days_covered: number; lessons: number }
interface DistrictPoint extends UnitPoint { region_id: number; region: string; expected: number; latest_date: string | null }
interface Analytics { level: string; unit_label: string; title: string; date_from: string; date_to: string; days: string[]; trend: TrendPoint[]; units: UnitPoint[]; districts: DistrictPoint[]; compliance: { key: number; label: string; cells: string[] }[]; totals: UnitPoint; expected_reports: number; submitted_reports: number }

const shortDay = (iso: string) => { const d = new Date(iso + "T00:00:00Z"); return `${d.getUTCDate()} ${d.toLocaleString("en-GB", { month: "short", timeZone: "UTC" })}`; };
const pct = (a: number, b: number) => (b ? `${Math.round((a / b) * 100)}%` : "—");

const axisProps = { tick: { fontSize: 11, fill: C.axis }, axisLine: false, tickLine: false } as const;
const gridProps = { stroke: C.grid, strokeDasharray: undefined, vertical: false } as const;
const tooltipStyle = { contentStyle: { fontSize: 12, borderRadius: 6, border: `1px solid ${C.grid}` }, cursor: { fill: "rgba(0,0,0,0.04)" } } as const;
const bar = { maxBarSize: 24, isAnimationActive: false, stroke: C.surface, strokeWidth: 2 } as const;

function ChartCard({ title, sub, children, height = 260 }: { title: string; sub?: string; children: React.ReactElement; height?: number }) {
  return (
    <Card title={title}>
      {sub && <p className="-mt-2 mb-2 text-xs text-slate-500">{sub}</p>}
      <ResponsiveContainer width="100%" height={height}>{children}</ResponsiveContainer>
    </Card>
  );
}

/** Inline meter: value over max, one hue, value text stays in ink. */
function Meter({ value, max, tone = C.blue, label }: { value: number; max: number; tone?: string; label?: string }) {
  const w = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0;
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-24 rounded-full" style={{ background: C.none }}>
        <div className="h-2 rounded-full" style={{ width: `${w}%`, background: tone }} />
      </div>
      <span className="text-xs tabular-nums text-slate-600">{label ?? `${w}%`}</span>
    </div>
  );
}

/** Tiny stacked bar of discrepancy cases by band. */
function BandBar({ low, medium, high }: { low: number; medium: number; high: number }) {
  const total = low + medium + high;
  if (!total) return <span className="text-xs text-slate-400">none</span>;
  const seg = (n: number, color: string) => (n ? <div style={{ width: `${(n / total) * 100}%`, background: color, height: 8 }} /> : null);
  return (
    <div className="flex items-center gap-2">
      <div className="flex w-24 overflow-hidden rounded-full" style={{ gap: 1, background: C.surface }}>{seg(low, C.bandLow)}{seg(medium, C.bandMid)}{seg(high, C.bandHigh)}</div>
      <span className="text-xs tabular-nums text-slate-600">{low} · {medium} · <span className={high ? "font-semibold text-red-700" : ""}>{high}</span></span>
    </div>
  );
}

function RegionCards({ a, filters }: { a: Analytics; filters: { date_from?: string; date_to?: string } }) {
  const nav = useNavigate();
  return (
    <Card title="Regions at a glance" className="mb-4">
      <p className="-mt-2 mb-3 text-xs text-slate-500">Click a region to open its page. Reporting is submitted reports over district-days in the period; teams are the latest cumulative figures.</p>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5">
        {a.units.map((u) => {
          const ds = a.districts.filter((d) => d.region_id === u.key);
          const expected = ds.reduce((n, d) => n + d.expected, 0);
          const reportedToday = ds.filter((d) => d.latest_date === a.date_to && d.submitted > 0).length;
          return (
            <button key={u.key} onClick={() => nav(`/dqm/analytics/region${qs({ region_id: u.key, date_from: filters.date_from, date_to: filters.date_to })}`)} className="rounded-lg border border-slate-200 bg-white p-3 text-left hover:shadow transition">
              <div className="mb-2 flex items-baseline justify-between">
                <span className="font-semibold">{u.label}</span>
                <span className="text-xs text-slate-500">{ds.length} districts</span>
              </div>
              <dl className="space-y-1.5 text-xs">
                <div><dt className="text-slate-500">Reporting</dt><dd><Meter value={u.submitted} max={expected} label={`${u.submitted} / ${expected}`} /></dd></div>
                <div><dt className="text-slate-500">Reported on {shortDay(a.date_to)}</dt><dd className="font-medium">{reportedToday} of {ds.length} districts</dd></div>
                <div><dt className="text-slate-500">Teams certified</dt><dd><Meter value={u.teams_certified} max={u.teams_reviewed} tone={C.aqua} label={`${u.teams_certified} / ${u.teams_reviewed}`} /></dd></div>
                <div><dt className="text-slate-500">Re-interviews certified</dt><dd><Meter value={u.reint_certified} max={u.reint_received} tone={C.aqua} label={pct(u.reint_certified, u.reint_received)} /></dd></div>
                <div className="flex justify-between pt-1"><span className="text-slate-500">High-discrepancy</span><span className={clsx("font-semibold", u.high && "text-red-700")}>{u.high}</span></div>
                <div className="flex justify-between"><span className="text-slate-500">Open issues</span><span className={clsx("font-semibold", u.issues_open && "text-amber-800")}>{u.issues_open}</span></div>
              </dl>
            </button>
          );
        })}
      </div>
    </Card>
  );
}

function DistrictTable({ a, filters, showRegion }: { a: Analytics; filters: { date_from?: string; date_to?: string }; showRegion: boolean }) {
  const nav = useNavigate();
  const [sort, setSort] = useState<"high" | "reporting" | "name" | "certified">("high");
  const rows = [...a.districts].sort((x, y) => {
    if (sort === "name") return x.label.localeCompare(y.label);
    if (sort === "reporting") return x.submitted / Math.max(1, x.expected) - y.submitted / Math.max(1, y.expected) || x.label.localeCompare(y.label);
    if (sort === "certified") return y.teams_certified / Math.max(1, y.teams_reviewed) - x.teams_certified / Math.max(1, x.teams_reviewed);
    return y.high - x.high || y.issues_open - x.issues_open || x.label.localeCompare(y.label);
  });
  const th = (key: typeof sort, label: string) => <th className={clsx("cursor-pointer select-none", sort === key && "text-navy")} onClick={() => setSort(key)}>{label}{sort === key ? " ▾" : ""}</th>;
  return (
    <Card title="Districts at a glance" className="mb-4">
      <p className="-mt-2 mb-3 text-xs text-slate-500">Click a column heading to sort, a row to open the district. Discrepancy cases are shown as low · medium · high.</p>
      <div className="overflow-x-auto">
        <table className="table">
          <thead><tr>{th("name", "District")}{showRegion && <th>Region</th>}{th("reporting", "Reporting (submitted / expected)")}{th("certified", "Teams certified / reviewed")}<th>Re-interviews certified</th>{th("high", "Discrepancy cases")}<th>Open issues</th><th>Latest report</th></tr></thead>
          <tbody>
            {rows.map((d) => (
              <tr key={d.key} className="cursor-pointer hover:bg-slate-50" onClick={() => nav(`/dqm/analytics/district${qs({ district_id: d.key, date_from: filters.date_from, date_to: filters.date_to })}`)}>
                <td className="font-medium">{d.label}</td>
                {showRegion && <td className="text-slate-600">{d.region}</td>}
                <td><Meter value={d.submitted} max={d.expected} label={`${d.submitted} / ${d.expected}`} /></td>
                <td><Meter value={d.teams_certified} max={d.teams_reviewed} tone={C.aqua} label={`${d.teams_certified} / ${d.teams_reviewed}`} /></td>
                <td><Meter value={d.reint_certified} max={d.reint_received} tone={C.aqua} label={pct(d.reint_certified, d.reint_received)} /></td>
                <td><BandBar low={d.low} medium={d.medium} high={d.high} /></td>
                <td className={clsx("tabular-nums", d.issues_open && "font-semibold text-amber-800")}>{d.issues_open}</td>
                <td className="whitespace-nowrap text-slate-600">{d.latest_date ? fmtDate(d.latest_date) : <span className="text-red-700">none</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function Heatmap({ a }: { a: Analytics }) {
  const color: Record<string, string> = { NONE: C.none, DRAFT: C.draft, SUBMITTED: C.submitted, RECEIVED: C.received };
  const label: Record<string, string> = { NONE: "No report", DRAFT: "Draft only", SUBMITTED: "Submitted", RECEIVED: "Received by NDQM" };
  return (
    <Card title="Reporting compliance by district and day">
      <p className="-mt-2 mb-3 text-xs text-slate-500">Each cell is one district-day. {a.submitted_reports} of {a.expected_reports} expected reports submitted ({pct(a.submitted_reports, a.expected_reports)}).</p>
      <div className="overflow-x-auto">
        <table className="text-xs" style={{ borderCollapse: "separate", borderSpacing: 2 }}>
          <thead>
            <tr><th className="pr-2 text-left font-medium text-slate-500" />{a.days.map((d) => <th key={d} className="font-normal text-slate-500" style={{ minWidth: 22 }}>{a.days.length <= 31 ? new Date(d + "T00:00:00Z").getUTCDate() : ""}</th>)}</tr>
          </thead>
          <tbody>
            {a.compliance.map((row) => (
              <tr key={row.key}>
                <td className="whitespace-nowrap pr-2 text-slate-700">{row.label}</td>
                {row.cells.map((c, i) => <td key={i} title={`${row.label} · ${fmtDate(a.days[i])}: ${label[c]}`} style={{ background: color[c], width: 22, height: 18, borderRadius: 3 }} />)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-3 flex flex-wrap gap-4 text-xs text-slate-600">
        {Object.entries(label).map(([k, v]) => <span key={k} className="flex items-center gap-1"><span style={{ background: color[k], width: 12, height: 12, borderRadius: 3, display: "inline-block" }} /> {v}</span>)}
      </div>
    </Card>
  );
}

export default function DqmAnalyticsPage() {
  const { level = "district" } = useParams();
  const nav = useNavigate();
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const set = (patch: Record<string, string | undefined>) => { const n = new URLSearchParams(params); for (const [k, v] of Object.entries(patch)) { if (v) n.set(k, v); else n.delete(k); } setParams(n, { replace: true }); };
  const [tables, setTables] = useState(false);
  const filters = { level, district_id: params.get("district_id") || undefined, region_id: params.get("region_id") || undefined, date_from: params.get("date_from") || undefined, date_to: params.get("date_to") || undefined };
  const q = qs(filters);
  const isDistrictUser = user?.role === "DISTRICT_DQM";
  const isNational = user?.role === "NATIONAL_DQM" || user?.role === "ADMIN";
  const isRegional = user?.role === "REGIONAL";
  const districts = useQuery({ queryKey: ["ref", "districts"], queryFn: () => api.get<District[]>("/admin/reference/districts"), staleTime: 300_000 });
  const regions = useQuery({ queryKey: ["ref", "regions"], queryFn: () => api.get<Named[]>("/admin/reference/regions"), staleTime: 300_000 });
  const needsRegion = level === "region" && isNational && !filters.region_id;
  const needsDistrict = level === "district" && !isDistrictUser && !filters.district_id;
  const a = useQuery({ queryKey: ["dqm-analytics", q], queryFn: () => api.get<Analytics>(`/dqm-reports/analytics${q}`), enabled: !needsRegion && !needsDistrict });
  const d = a.data;
  const preset = (days: number) => { const to = new Date(); const from = new Date(); from.setUTCDate(to.getUTCDate() - days + 1); set({ date_from: from.toISOString().slice(0, 10), date_to: to.toISOString().slice(0, 10) }); };
  const trend = d?.trend.map((t) => ({ ...t, day: shortDay(t.date) })) ?? [];
  const multi = level !== "district";
  const scopedDistricts = districts.data?.filter((x) => !user?.district_ids || user.district_ids.includes(x.id)) ?? [];

  const levelTab = (lv: string, label: string) => (
    <button key={lv} className={clsx("rounded-md px-3 py-1.5 text-sm", level === lv ? "bg-navy text-white" : "bg-white text-slate-700 border border-slate-300 hover:bg-slate-50")} onClick={() => nav(`/dqm/analytics/${lv}${qs({ date_from: filters.date_from, date_to: filters.date_to, region_id: filters.region_id })}`)}>{label}</button>
  );

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <nav className="flex flex-wrap items-center gap-1 text-sm text-navy">
            <Link to="/dqm/analytics">DQM analytics</Link>
            {isNational && level !== "national" && <><span className="text-slate-400">›</span><Link to="/dqm/analytics/national">National</Link></>}
            {(level === "district" || level === "region") && (isNational || isRegional) && (() => {
              const rid = level === "region" ? Number(filters.region_id) : districts.data?.find((x) => x.id === Number(filters.district_id))?.region_id;
              const reg = regions.data?.find((r) => r.id === rid);
              return reg ? <><span className="text-slate-400">›</span>{level === "district" ? <Link to={`/dqm/analytics/region?region_id=${reg.id}`}>{reg.name} region</Link> : <span className="text-slate-700">{reg.name} region</span>}</> : null;
            })()}
            {level === "district" && d && <><span className="text-slate-400">›</span><span className="text-slate-700">{d.title}</span></>}
          </nav>
          <h1 className="text-2xl font-bold">DQM analytics{d ? ` · ${d.title}` : ""}</h1>
          <p className="text-sm text-slate-500">Charts built from the daily DQM reports{d ? `, ${fmtDate(d.date_from)} to ${fmtDate(d.date_to)}` : ""}. Teams reviewed and certified are cumulative per district.</p>
        </div>
        <div className="flex gap-2">
          {levelTab("district", "District")}
          {(isRegional || isNational) && levelTab("region", "Regional")}
          {isNational && levelTab("national", "National")}
        </div>
      </div>

      <div className="card mb-4 flex flex-wrap items-end gap-3">
        {level === "region" && isNational && (
          <Field label="Region"><select className="input" value={filters.region_id ?? ""} onChange={(e) => set({ region_id: e.target.value })}><option value="">Select…</option>{regions.data?.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}</select></Field>
        )}
        {level === "district" && !isDistrictUser && (
          <Field label="District"><select className="input" value={filters.district_id ?? ""} onChange={(e) => set({ district_id: e.target.value })}><option value="">Select…</option>{scopedDistricts.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></Field>
        )}
        <Field label="Period">
          <div className="flex gap-1">
            {[7, 14, 30].map((n) => <button key={n} className="btn-outline" onClick={() => preset(n)}>Last {n} days</button>)}
          </div>
        </Field>
        <Field label="From"><input type="date" className="input" value={filters.date_from ?? ""} onChange={(e) => set({ date_from: e.target.value })} /></Field>
        <Field label="To"><input type="date" className="input" value={filters.date_to ?? ""} onChange={(e) => set({ date_to: e.target.value })} /></Field>
        <label className="ml-auto flex items-center gap-2 text-sm"><input type="checkbox" checked={tables} onChange={(e) => setTables(e.target.checked)} /> Show data tables</label>
        {d && level !== "district" && <button className="btn-outline" onClick={() => download(`/dqm-reports/summary/export${qs({ level, region_id: filters.region_id, date_from: d.date_from, date_to: d.date_to, format: "xlsx" })}`, "summary.xlsx")}>Excel</button>}
      </div>

      <ErrorBox error={a.error} />
      {needsRegion ? <p className="text-sm text-slate-500">Choose a region.</p> : needsDistrict ? <p className="text-sm text-slate-500">Choose a district.</p> : a.isLoading ? <Spinner /> : d && (
        <>
          <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
            <KpiTile label="Reports submitted" value={`${d.submitted_reports} / ${d.expected_reports}`} sub={`${pct(d.submitted_reports, d.expected_reports)} of district-days`} tone={d.submitted_reports === d.expected_reports ? "green" : "amber"} />
            <KpiTile label="Teams certified" value={d.totals.teams_certified} sub={`${pct(d.totals.teams_certified, d.totals.teams_reviewed)} of ${d.totals.teams_reviewed} reviewed`} tone="green" />
            <KpiTile label="Re-interviews certified" value={d.totals.reint_certified} sub={`${pct(d.totals.reint_certified, d.totals.reint_received)} of ${d.totals.reint_received} received`} tone="green" />
            <KpiTile label="Re-interviews pending" value={d.totals.reint_pending} tone="amber" />
            <KpiTile label="High-discrepancy cases" value={d.totals.high} sub={`${d.totals.medium} medium · ${d.totals.low} low`} tone="red" />
            <KpiTile label="Open system issues" value={d.totals.issues_open} sub={`${d.totals.issues_resolved} resolved`} tone="amber" />
          </div>

          {level === "national" && <RegionCards a={d} filters={filters} />}
          {multi && <DistrictTable a={d} filters={filters} showRegion={level === "national"} />}

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <ChartCard title="Teams reviewed and certified over time" sub="Cumulative figures as reported each day">
              <LineChart data={trend} margin={{ top: 8, right: 16, left: -8, bottom: 0 }}>
                <CartesianGrid {...gridProps} />
                <XAxis dataKey="day" {...axisProps} />
                <YAxis {...axisProps} allowDecimals={false} />
                <Tooltip {...tooltipStyle} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                <Line type="monotone" dataKey="teams_reviewed" name="Teams reviewed" stroke={C.blue} strokeWidth={2} dot={{ r: 4, fill: C.blue, stroke: C.surface, strokeWidth: 2 }} isAnimationActive={false} />
                <Line type="monotone" dataKey="teams_certified" name="Teams certified" stroke={C.aqua} strokeWidth={2} dot={{ r: 4, fill: C.aqua, stroke: C.surface, strokeWidth: 2 }} isAnimationActive={false} />
              </LineChart>
            </ChartCard>
            <ChartCard title="Re-interviews received and certified per day">
              <BarChart data={trend} margin={{ top: 8, right: 16, left: -8, bottom: 0 }} barGap={2}>
                <CartesianGrid {...gridProps} />
                <XAxis dataKey="day" {...axisProps} />
                <YAxis {...axisProps} allowDecimals={false} />
                <Tooltip {...tooltipStyle} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="reint_received" name="Received for review" fill={C.blue} radius={[4, 4, 0, 0]} {...bar} />
                <Bar dataKey="reint_certified" name="Certified" fill={C.aqua} radius={[4, 4, 0, 0]} {...bar} />
              </BarChart>
            </ChartCard>
            <ChartCard title="Discrepancy cases per day by band" sub="Re-interview discrepancy: low under 5%, medium 5 to 10%, high over 10%">
              <BarChart data={trend} margin={{ top: 8, right: 16, left: -8, bottom: 0 }}>
                <CartesianGrid {...gridProps} />
                <XAxis dataKey="day" {...axisProps} />
                <YAxis {...axisProps} allowDecimals={false} />
                <Tooltip {...tooltipStyle} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="low" name="Low" stackId="b" fill={C.bandLow} {...bar} />
                <Bar dataKey="medium" name="Medium" stackId="b" fill={C.bandMid} {...bar} />
                <Bar dataKey="high" name="High" stackId="b" fill={C.bandHigh} radius={[4, 4, 0, 0]} {...bar} />
              </BarChart>
            </ChartCard>
            <ChartCard title="GIS, CAPI and synchronisation issues per day">
              <BarChart data={trend} margin={{ top: 8, right: 16, left: -8, bottom: 0 }}>
                <CartesianGrid {...gridProps} />
                <XAxis dataKey="day" {...axisProps} />
                <YAxis {...axisProps} allowDecimals={false} />
                <Tooltip {...tooltipStyle} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="outlier" name="Response outliers" stackId="i" fill={C.blue} {...bar} />
                <Bar dataKey="gps" name="GPS / coordinates" stackId="i" fill={C.orange} {...bar} />
                <Bar dataKey="sync" name="Synchronisation" stackId="i" fill={C.aqua} radius={[4, 4, 0, 0]} {...bar} />
              </BarChart>
            </ChartCard>

            {multi && (
              <>
                <ChartCard title={`Teams reviewed and certified by ${d.unit_label.toLowerCase()}`} sub="Latest cumulative figure per district" height={Math.max(220, 40 * d.units.length + 60)}>
                  <BarChart data={d.units} layout="vertical" margin={{ top: 8, right: 24, left: 8, bottom: 0 }} barGap={2}>
                    <CartesianGrid stroke={C.grid} horizontal={false} />
                    <XAxis type="number" {...axisProps} allowDecimals={false} />
                    <YAxis type="category" dataKey="label" width={120} {...axisProps} />
                    <Tooltip {...tooltipStyle} />
                    <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                    <Bar dataKey="teams_reviewed" name="Reviewed" fill={C.blue} radius={[0, 4, 4, 0]} {...bar} />
                    <Bar dataKey="teams_certified" name="Certified" fill={C.aqua} radius={[0, 4, 4, 0]} {...bar} />
                  </BarChart>
                </ChartCard>
                <ChartCard title={`Re-interviews by ${d.unit_label.toLowerCase()}`} sub="Summed over the period" height={Math.max(220, 40 * d.units.length + 60)}>
                  <BarChart data={d.units} layout="vertical" margin={{ top: 8, right: 24, left: 8, bottom: 0 }} barGap={2}>
                    <CartesianGrid stroke={C.grid} horizontal={false} />
                    <XAxis type="number" {...axisProps} allowDecimals={false} />
                    <YAxis type="category" dataKey="label" width={120} {...axisProps} />
                    <Tooltip {...tooltipStyle} />
                    <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                    <Bar dataKey="reint_received" name="Received for review" fill={C.blue} radius={[0, 4, 4, 0]} {...bar} />
                    <Bar dataKey="reint_certified" name="Certified" fill={C.aqua} radius={[0, 4, 4, 0]} {...bar} />
                  </BarChart>
                </ChartCard>
                <ChartCard title={`Discrepancy cases by ${d.unit_label.toLowerCase()} and band`} height={Math.max(220, 32 * d.units.length + 60)}>
                  <BarChart data={d.units} layout="vertical" margin={{ top: 8, right: 24, left: 8, bottom: 0 }}>
                    <CartesianGrid stroke={C.grid} horizontal={false} />
                    <XAxis type="number" {...axisProps} allowDecimals={false} />
                    <YAxis type="category" dataKey="label" width={120} {...axisProps} />
                    <Tooltip {...tooltipStyle} />
                    <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                    <Bar dataKey="low" name="Low" stackId="b" fill={C.bandLow} {...bar} />
                    <Bar dataKey="medium" name="Medium" stackId="b" fill={C.bandMid} {...bar} />
                    <Bar dataKey="high" name="High" stackId="b" fill={C.bandHigh} radius={[0, 4, 4, 0]} {...bar} />
                  </BarChart>
                </ChartCard>
                <ChartCard title={`System issues by ${d.unit_label.toLowerCase()} and type`} height={Math.max(220, 32 * d.units.length + 60)}>
                  <BarChart data={d.units} layout="vertical" margin={{ top: 8, right: 24, left: 8, bottom: 0 }}>
                    <CartesianGrid stroke={C.grid} horizontal={false} />
                    <XAxis type="number" {...axisProps} allowDecimals={false} />
                    <YAxis type="category" dataKey="label" width={120} {...axisProps} />
                    <Tooltip {...tooltipStyle} />
                    <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                    <Bar dataKey="outlier" name="Response outliers" stackId="i" fill={C.blue} {...bar} />
                    <Bar dataKey="gps" name="GPS / coordinates" stackId="i" fill={C.orange} {...bar} />
                    <Bar dataKey="sync" name="Synchronisation" stackId="i" fill={C.aqua} radius={[0, 4, 4, 0]} {...bar} />
                  </BarChart>
                </ChartCard>
              </>
            )}
          </div>

          <div className="mt-4"><Heatmap a={d} /></div>

          {tables && (
            <div className="mt-4 grid grid-cols-1 gap-4">
              <Card title="Per day">
                <div className="overflow-x-auto"><table className="table">
                  <thead><tr><th>Day</th><th>Reports</th><th>Teams reviewed</th><th>Teams certified</th><th>Reint. received</th><th>Reint. certified</th><th>Pending</th><th>Low</th><th>Medium</th><th>High</th><th>Outliers</th><th>GPS</th><th>Sync</th><th>Open</th><th>Resolved</th></tr></thead>
                  <tbody>{d.trend.map((t) => <tr key={t.date}><td>{fmtDate(t.date)}</td><td>{t.reports}</td><td>{t.teams_reviewed}</td><td>{t.teams_certified}</td><td>{t.reint_received}</td><td>{t.reint_certified}</td><td>{t.reint_pending}</td><td>{t.low}</td><td>{t.medium}</td><td>{t.high}</td><td>{t.outlier}</td><td>{t.gps}</td><td>{t.sync}</td><td>{t.issues_open}</td><td>{t.issues_resolved}</td></tr>)}</tbody>
                </table></div>
              </Card>
              <Card title={`Per ${d.unit_label.toLowerCase()}`}>
                <div className="overflow-x-auto"><table className="table">
                  <thead><tr><th>{d.unit_label}</th><th>Reports</th><th>Submitted</th><th>Received</th><th>Days</th><th>Teams reviewed</th><th>Teams certified</th><th>Reint. received</th><th>Reint. certified</th><th>Pending</th><th>Low</th><th>Medium</th><th>High</th><th>Outliers</th><th>GPS</th><th>Sync</th><th>Open</th><th>Lessons</th></tr></thead>
                  <tbody>{[...d.units, d.totals].map((u) => <tr key={u.key} className={u.key === 0 ? "bg-slate-100 font-semibold" : ""}><td>{u.label}</td><td>{u.reports}</td><td>{u.submitted}</td><td>{u.received}</td><td>{u.days_covered}</td><td>{u.teams_reviewed}</td><td>{u.teams_certified}</td><td>{u.reint_received}</td><td>{u.reint_certified}</td><td>{u.reint_pending}</td><td>{u.low}</td><td>{u.medium}</td><td>{u.high}</td><td>{u.outlier}</td><td>{u.gps}</td><td>{u.sync}</td><td>{u.issues_open}</td><td>{u.lessons}</td></tr>)}</tbody>
                </table></div>
              </Card>
            </div>
          )}
        </>
      )}
    </div>
  );
}
