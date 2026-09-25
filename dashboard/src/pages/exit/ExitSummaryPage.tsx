import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import clsx from "clsx";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, download, qs } from "../../api/client";
import type { ExitSummary, ExitSummaryRow } from "../../api/types";
import { useGeoScope } from "../../components/AnalyticsMenu";
import { Card, ErrorBox, Field, KpiTile, Spinner } from "../../components/ui";

// Same validated palette as the DQM analytics page.
const C = { blue: "#2a78d6", aqua: "#1baf7a", orange: "#eb6834", yellow: "#eda100", ramp1: "#86b6ef", ramp2: "#2a78d6", ramp3: "#104281", none: "#e1e0d9", grid: "#e1e0d9", axis: "#898781", surface: "#ffffff" };
const axisProps = { tick: { fontSize: 11, fill: C.axis }, axisLine: false, tickLine: false } as const;
const tooltipStyle = { contentStyle: { fontSize: 12, borderRadius: 6, border: `1px solid ${C.grid}` }, cursor: { fill: "rgba(0,0,0,0.04)" } } as const;
const bar = { maxBarSize: 24, isAnimationActive: false, stroke: C.surface, strokeWidth: 2 } as const;
const pct = (a: number, b: number) => (b ? `${Math.round((a / b) * 100)}%` : "—");

function Meter({ value, max, tone = C.blue, label }: { value: number; max: number; tone?: string; label?: string }) {
  const w = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0;
  return <div className="flex items-center gap-2"><div className="h-2 w-24 rounded-full" style={{ background: C.none }}><div className="h-2 rounded-full" style={{ width: `${w}%`, background: tone }} /></div><span className="text-xs tabular-nums text-slate-600">{label ?? `${w}%`}</span></div>;
}

function DecisionBar({ r }: { r: ExitSummaryRow }) {
  const parts = [[r.cleared_payment, C.aqua], [r.cleared_redeployment, C.blue], [r.conditional, C.yellow], [r.not_cleared, C.orange]] as const;
  const total = parts.reduce((n, [v]) => n + v, 0);
  if (!total) return <span className="text-xs text-slate-400">none</span>;
  return <div className="flex items-center gap-2"><div className="flex w-24 overflow-hidden rounded-full" style={{ gap: 1 }}>{parts.map(([v, color], i) => v ? <div key={i} style={{ width: `${(v / total) * 100}%`, background: color, height: 8 }} /> : null)}</div><span className="text-xs tabular-nums text-slate-600">{r.cleared_payment} · {r.cleared_redeployment} · {r.conditional} · <span className={r.not_cleared ? "font-semibold text-red-700" : ""}>{r.not_cleared}</span></span></div>;
}

export default function ExitSummaryPage() {
  const { level = "district" } = useParams();
  const nav = useNavigate();
  const { regions, districts, isNational, isRegional, isDistrict } = useGeoScope();
  const [params, setParams] = useSearchParams();
  const set = (k: string, v: string) => { const n = new URLSearchParams(params); if (v) n.set(k, v); else n.delete(k); setParams(n, { replace: true }); };
  const filters = { level, district_id: params.get("district_id") || undefined, region_id: params.get("region_id") || undefined };
  const q = qs(filters);
  const needsRegion = level === "region" && isNational && !filters.region_id;
  const needsDistrict = level === "district" && !isDistrict && !filters.district_id;
  const s = useQuery({ queryKey: ["exit-summary", q], queryFn: () => api.get<ExitSummary>(`/exit-checkouts/summary${q}`), enabled: !needsRegion && !needsDistrict });
  const d = s.data;
  const multi = level !== "district";
  const levelTab = (lv: string, label: string) => <button key={lv} className={clsx("rounded-md px-3 py-1.5 text-sm", level === lv ? "bg-navy text-white" : "bg-white text-slate-700 border border-slate-300 hover:bg-slate-50")} onClick={() => nav(`/dqm/exit/summary/${lv}${qs({ region_id: filters.region_id })}`)}>{label}</button>;
  const checklistData = d ? d.checklist_labels.map((t, i) => ({ name: `${i + 1}. ${t.length > 48 ? t.slice(0, 46) + "…" : t}`, count: d.totals.checklist_no[i] })) : [];
  const itemData = d ? d.item_labels.map((t, i) => ({ name: t.length > 40 ? t.slice(0, 38) + "…" : t, count: d.totals.items_missing[i] })) : [];
  const unitRows = d ? (multi ? d.rows : d.districts) : [];

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <nav className="flex flex-wrap items-center gap-1 text-sm text-navy">
            <Link to="/dqm/exit">Field exit protocol</Link>
            {isNational && level !== "national" && <><span className="text-slate-400">›</span><Link to="/dqm/exit/summary/national">National</Link></>}
            {(level === "district" || level === "region") && (isNational || isRegional) && (() => {
              const rid = level === "region" ? Number(filters.region_id) : districts.find((x) => x.id === Number(filters.district_id))?.region_id;
              const reg = regions.find((r) => r.id === rid);
              return reg ? <><span className="text-slate-400">›</span>{level === "district" ? <Link to={`/dqm/exit/summary/region?region_id=${reg.id}`}>{reg.name} region</Link> : <span className="text-slate-700">{reg.name} region</span>}</> : null;
            })()}
            {level === "district" && d && <><span className="text-slate-400">›</span><span className="text-slate-700">{d.title}</span></>}
          </nav>
          <h1 className="text-2xl font-bold">Field exit protocol{d ? ` · ${d.title}` : ""}</h1>
          <p className="text-sm text-slate-500">Check-out progress, clearance decisions, checklist failures and unreturned items{d?.expected_staff != null ? `, against ${d.expected_staff.toLocaleString()} field staff in the roster` : ""}.</p>
        </div>
        <div className="flex gap-2">
          {levelTab("district", "District")}
          {(isRegional || isNational) && levelTab("region", "Regional")}
          {isNational && levelTab("national", "National")}
          {d && <button className="btn-outline" onClick={() => download(`/exit-checkouts/summary/export${qs({ ...filters, format: "xlsx" })}`, "exit-summary.xlsx")}>Excel</button>}
        </div>
      </div>
      {(level === "region" && isNational) || (level === "district" && !isDistrict) ? (
        <div className="card mb-4 flex flex-wrap gap-3">
          {level === "region" && isNational && <Field label="Region"><select className="input" value={filters.region_id ?? ""} onChange={(e) => set("region_id", e.target.value)}><option value="">Select…</option>{regions.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}</select></Field>}
          {level === "district" && !isDistrict && <Field label="District"><select className="input" value={filters.district_id ?? ""} onChange={(e) => set("district_id", e.target.value)}><option value="">Select…</option>{districts.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></Field>}
        </div>
      ) : null}
      <ErrorBox error={s.error} />
      {needsRegion ? <p className="text-sm text-slate-500">Choose a region.</p> : needsDistrict ? <p className="text-sm text-slate-500">Choose a district.</p> : s.isLoading ? <Spinner /> : d && (
        <>
          <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
            <KpiTile label="Staff checked out" value={d.totals.total} sub={d.expected_staff != null ? `${pct(d.totals.total, d.expected_staff)} of ${d.expected_staff.toLocaleString()} in roster` : `${d.totals.supervisors} supervisors · ${d.totals.enumerators} enumerators`} />
            <KpiTile label="Awaiting national action" value={d.totals.submitted + d.totals.national_signed} sub={`${d.totals.submitted} to countersign · ${d.totals.national_signed} to clear`} tone="amber" />
            <KpiTile label="Cleared" value={d.totals.cleared_payment + d.totals.cleared_redeployment} sub={`${d.totals.cleared_payment} payment · ${d.totals.cleared_redeployment} redeployment`} tone="green" />
            <KpiTile label="Conditional" value={d.totals.conditional} sub={`${d.totals.overdue_conditions} past deadline`} tone="amber" />
            <KpiTile label="Not cleared" value={d.totals.not_cleared} tone="red" />
            <KpiTile label="Items not returned" value={d.totals.items_missing.reduce((a, b) => a + b, 0)} sub={`${d.totals.checklist_no.reduce((a, b) => a + b, 0)} checklist failures`} tone="red" />
          </div>

          {multi && (
            <Card title={`${d.unit_label}s at a glance`} className="mb-4">
              <p className="-mt-2 mb-3 text-xs text-slate-500">Click a row to drill down. Decisions are shown as payment · redeployment · conditional · not cleared.</p>
              <div className="overflow-x-auto">
                <table className="table">
                  <thead><tr><th>{d.unit_label}</th><th>Checked out</th><th>Supervisors</th><th>Enumerators</th><th>Awaiting</th><th>Decisions</th><th>Checklist failures</th><th>Items not returned</th><th>Past deadline</th></tr></thead>
                  <tbody>
                    {unitRows.map((r) => (
                      <tr key={r.key} className="cursor-pointer hover:bg-slate-50" onClick={() => nav(level === "national" ? `/dqm/exit/summary/region?region_id=${r.key}` : `/dqm/exit/summary/district?district_id=${r.key}`)}>
                        <td className="font-medium">{r.label}</td>
                        <td><Meter value={r.cleared} max={r.total} label={`${r.cleared} / ${r.total} cleared`} tone={C.aqua} /></td>
                        <td className="tabular-nums">{r.supervisors}</td><td className="tabular-nums">{r.enumerators}</td>
                        <td className={clsx("tabular-nums", (r.submitted + r.national_signed) && "font-semibold text-amber-800")}>{r.submitted + r.national_signed}</td>
                        <td><DecisionBar r={r} /></td>
                        <td className={clsx("tabular-nums", r.checklist_no.some(Boolean) && "text-red-700")}>{r.checklist_no.reduce((a, b) => a + b, 0)}</td>
                        <td className={clsx("tabular-nums", r.items_missing.some(Boolean) && "text-amber-800")}>{r.items_missing.reduce((a, b) => a + b, 0)}</td>
                        <td className={clsx("tabular-nums", r.overdue_conditions && "font-semibold text-red-700")}>{r.overdue_conditions}</td>
                      </tr>
                    ))}
                    {level === "national" && d.districts.length > 0 && (
                      <tr className="bg-slate-100 font-semibold"><td>Total</td><td>{d.totals.cleared} / {d.totals.total}</td><td>{d.totals.supervisors}</td><td>{d.totals.enumerators}</td><td>{d.totals.submitted + d.totals.national_signed}</td><td><DecisionBar r={d.totals} /></td><td>{d.totals.checklist_no.reduce((a, b) => a + b, 0)}</td><td>{d.totals.items_missing.reduce((a, b) => a + b, 0)}</td><td>{d.totals.overdue_conditions}</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <Card title="Clearance decisions" >
              <p className="-mt-2 mb-2 text-xs text-slate-500">{multi ? `By ${d.unit_label.toLowerCase()}` : "For this district"}</p>
              <ResponsiveContainer width="100%" height={Math.max(200, 36 * Math.max(1, unitRows.length) + 60)}>
                <BarChart data={multi ? unitRows : [d.totals]} layout="vertical" margin={{ top: 8, right: 24, left: 8, bottom: 0 }}>
                  <CartesianGrid stroke={C.grid} horizontal={false} />
                  <XAxis type="number" {...axisProps} allowDecimals={false} />
                  <YAxis type="category" dataKey="label" width={120} {...axisProps} />
                  <Tooltip {...tooltipStyle} />
                  <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="cleared_payment" name="Cleared: payment" stackId="d" fill={C.aqua} {...bar} />
                  <Bar dataKey="cleared_redeployment" name="Cleared: redeployment" stackId="d" fill={C.blue} {...bar} />
                  <Bar dataKey="conditional" name="Conditional" stackId="d" fill={C.yellow} {...bar} />
                  <Bar dataKey="not_cleared" name="Not cleared" stackId="d" fill={C.orange} {...bar} />
                  <Bar dataKey="submitted" name="Awaiting countersign" stackId="d" fill={C.ramp1} {...bar} />
                  <Bar dataKey="national_signed" name="Awaiting decision" stackId="d" fill={C.none} radius={[0, 4, 4, 0]} {...bar} />
                </BarChart>
              </ResponsiveContainer>
            </Card>
            <Card title="Staff checked out by role">
              <p className="-mt-2 mb-2 text-xs text-slate-500">{multi ? `By ${d.unit_label.toLowerCase()}` : "For this district"}</p>
              <ResponsiveContainer width="100%" height={Math.max(200, 36 * Math.max(1, unitRows.length) + 60)}>
                <BarChart data={multi ? unitRows : [d.totals]} layout="vertical" margin={{ top: 8, right: 24, left: 8, bottom: 0 }} barGap={2}>
                  <CartesianGrid stroke={C.grid} horizontal={false} />
                  <XAxis type="number" {...axisProps} allowDecimals={false} />
                  <YAxis type="category" dataKey="label" width={120} {...axisProps} />
                  <Tooltip {...tooltipStyle} />
                  <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="supervisors" name="Supervisors" fill={C.blue} radius={[0, 4, 4, 0]} {...bar} />
                  <Bar dataKey="enumerators" name="Enumerators" fill={C.aqua} radius={[0, 4, 4, 0]} {...bar} />
                </BarChart>
              </ResponsiveContainer>
            </Card>
            <Card title="Checklist requirements answered No">
              <p className="-mt-2 mb-2 text-xs text-slate-500">How often each of the 12 clearance requirements was not met</p>
              <ResponsiveContainer width="100%" height={12 * 30 + 40}>
                <BarChart data={checklistData} layout="vertical" margin={{ top: 4, right: 24, left: 8, bottom: 0 }}>
                  <CartesianGrid stroke={C.grid} horizontal={false} />
                  <XAxis type="number" {...axisProps} allowDecimals={false} />
                  <YAxis type="category" dataKey="name" width={300} {...axisProps} />
                  <Tooltip {...tooltipStyle} />
                  <Bar dataKey="count" name="Answered No" fill={C.ramp3} radius={[0, 4, 4, 0]} {...bar} />
                </BarChart>
              </ResponsiveContainer>
            </Card>
            <Card title="Items not returned">
              <p className="-mt-2 mb-2 text-xs text-slate-500">Tablet, accessories and sync confirmations still outstanding</p>
              <ResponsiveContainer width="100%" height={7 * 34 + 40}>
                <BarChart data={itemData} layout="vertical" margin={{ top: 4, right: 24, left: 8, bottom: 0 }}>
                  <CartesianGrid stroke={C.grid} horizontal={false} />
                  <XAxis type="number" {...axisProps} allowDecimals={false} />
                  <YAxis type="category" dataKey="name" width={260} {...axisProps} />
                  <Tooltip {...tooltipStyle} />
                  <Bar dataKey="count" name="Not returned" fill={C.orange} radius={[0, 4, 4, 0]} {...bar} />
                </BarChart>
              </ResponsiveContainer>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
