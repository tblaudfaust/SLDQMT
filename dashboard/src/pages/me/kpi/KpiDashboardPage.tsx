import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import clsx from "clsx";
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AlertTriangle, Download, ShieldAlert, Users } from "lucide-react";
import { ApiError, api, download, fmtDate, qs } from "../../../api/client";
import type { MeKpiCount, MeKpiGroup, MeKpiSummary } from "../../../api/types";
import { useAuth } from "../../../auth/AuthContext";
import { Card, Empty, ErrorBox, KpiTile, Spinner } from "../../../components/ui";

const NAVY = "#1F4E79", GREEN = "#15803d", AMBER = "#d97706", RED = "#b91c1c", SKY = "#38bdf8";
const PHASES = [["MT", "Master trainers' practice"], ["TOT", "ToT practice"], ["L", "Listing"], ["E", "Enumeration"]];
const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${v}%`);
const tone = (v: number | null | undefined, good: number, warn: number, invert = false): "navy" | "green" | "amber" | "red" => {
  if (v === null || v === undefined) return "navy";
  const x = invert ? -v : v;
  return x >= (invert ? -good : good) ? "green" : x >= (invert ? -warn : warn) ? "amber" : "red";
};
const colorFor = (v: number | null, good: number, warn: number) => (v === null ? "#94a3b8" : v >= good ? GREEN : v >= warn ? AMBER : RED);

/** KPI dashboard of the M&E field tool: by district, phase, week and officer, with the list that needs attention. */
export default function KpiDashboardPage() {
  const { can } = useAuth();
  const [f, setF] = useState({ phase: "", district_id: "", week: "", date_from: "", date_to: "" });
  const query = qs(f);
  const res = useQuery({ queryKey: ["me-kpi", "summary", query], queryFn: () => api.get<MeKpiSummary>(`/me/kpi/summary${query}`) });
  const all = useQuery({ queryKey: ["me-kpi", "summary", "all"], queryFn: () => api.get<MeKpiSummary>("/me/kpi/summary") });
  const [error, setError] = useState<unknown>(null);
  if (res.isLoading) return <Spinner />;
  if (res.error || !res.data) return <ErrorBox error={res.error} />;
  const d = res.data;
  const lists = all.data ?? d;
  const filtered = Object.values(f).some(Boolean);
  const exportFile = async (format: "xlsx" | "pdf") => { setError(null); try { await download(`/me/kpi/export${qs({ ...f, format })}`, `me-kpi.${format}`); } catch (e) { setError(e); } };
  const distRows = d.by_district.map((g) => ({ name: g.label, Coverage: g.coverage_pct ?? 0, Synced: g.synced_pct ?? 0, Tablets: g.tablets_pct ?? 0, reports: g.reports }));
  const weekRows = d.by_week.map((g) => ({ name: g.label, "Coverage %": g.coverage_pct ?? 0, "Synced %": g.synced_pct ?? 0, "Error rate %": g.error_pct ?? 0, "On schedule %": g.on_schedule_pct ?? 0 }));
  const community = [["Community informed", d.informed_pct], ["Households aware (all or most)", d.aware_pct], ["Respondents trust enumerators", d.trust_pct], ["Leaders support the team", d.support_pct], ["Feedback channel exists", d.channel_pct], ["Teams on schedule", d.on_schedule_pct]] as [string, number | null][];

  const CountBars = ({ rows, color }: { rows: MeKpiCount[]; color: string }) => {
    const data = rows.filter((r) => r.count).sort((a, b) => b.count - a.count);
    return data.length === 0 ? <Empty text="Nothing reported" /> : (
      <div style={{ height: 30 + 30 * data.length }}>
        <ResponsiveContainer>
          <BarChart data={data} layout="vertical" margin={{ left: 10, right: 40 }}>
            <XAxis type="number" hide /><YAxis type="category" dataKey="label" width={150} tick={{ fontSize: 12 }} />
            <Tooltip formatter={(v: number, _n, p) => [`${v} reports (${p.payload.pct}%)`, ""]} />
            <Bar dataKey="count" fill={color} isAnimationActive={false} label={{ position: "right", fontSize: 11, formatter: (v: number) => `${v}` }} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  };
  const GroupTable = ({ rows, first }: { rows: MeKpiGroup[]; first: string }) => (
    <div className="overflow-x-auto">
      <table className="table">
        <thead><tr><th>{first}</th><th className="text-right">Reports</th><th className="text-right">SAs</th><th className="text-right">Coverage</th><th className="text-right">Synced</th><th className="text-right">Error rate</th><th className="text-right">Tablets</th><th className="text-right">Informed</th><th className="text-right">Leaders support</th><th className="text-right">On schedule</th><th className="text-right">Overall</th><th className="text-right">Safety</th><th className="text-right">Escalations</th></tr></thead>
        <tbody>
          {rows.map((g) => (
            <tr key={g.key} className={clsx((g.safety_concerns || g.escalations) && "bg-amber-50/60")}>
              <td className="font-medium">{g.label}</td><td className="text-right">{g.reports}</td><td className="text-right">{g.sas}</td>
              <td className="text-right">{pct(g.coverage_pct)}</td><td className={clsx("text-right", g.synced_pct !== null && g.synced_pct < 80 && "font-semibold text-red-700")}>{pct(g.synced_pct)}</td>
              <td className={clsx("text-right", g.error_pct !== null && g.error_pct > 5 && "font-semibold text-red-700")}>{pct(g.error_pct)}</td><td className="text-right">{pct(g.tablets_pct)}</td>
              <td className="text-right">{pct(g.informed_pct)}</td><td className="text-right">{pct(g.support_pct)}</td><td className="text-right">{pct(g.on_schedule_pct)}</td>
              <td className="text-right">{g.overall ?? "—"}</td><td className={clsx("text-right", g.safety_concerns && "font-semibold text-red-700")}>{g.safety_concerns}</td><td className={clsx("text-right", g.escalations && "font-semibold text-amber-800")}>{g.escalations}</td>
            </tr>
          ))}
          {rows.length === 0 && <tr><td colSpan={13}><Empty /></td></tr>}
        </tbody>
      </table>
    </div>
  );

  return (
    <div className="max-w-7xl">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link to="/me/kpi" className="text-sm text-navy">← M&amp;E Field Tool</Link>
          <h1 className="text-2xl font-bold">KPI dashboard</h1>
          <p className="text-sm text-slate-500">Scope: <b>{d.scope}</b> · {d.reports} reports from {d.sas} SAs / teams in {d.districts} district{d.districts === 1 ? "" : "s"}{d.last_date ? ` · last report ${fmtDate(d.last_date)}` : ""}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Link to="/me/kpi/reports" className="btn-outline">All reports</Link>
          {can("me_kpi.export") && <button className="btn-outline" onClick={() => exportFile("xlsx")}><Download size={16} /> Excel</button>}
          {can("me_kpi.export") && <button className="btn-outline" onClick={() => exportFile("pdf")}><Download size={16} /> PDF</button>}
        </div>
      </div>
      <ErrorBox error={error instanceof ApiError ? error.message : error} />
      <Card className="mb-4">
        <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-5">
          <select className="input" value={f.phase} onChange={(e) => setF({ ...f, phase: e.target.value })}><option value="">All phases</option>{PHASES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
          <select className="input" value={f.district_id} onChange={(e) => setF({ ...f, district_id: e.target.value })}><option value="">All districts</option>{lists.by_district.filter((g) => g.key !== "0").map((g) => <option key={g.key} value={g.key}>{g.label} ({g.reports})</option>)}</select>
          <select className="input" value={f.week} onChange={(e) => setF({ ...f, week: e.target.value })}><option value="">All weeks</option>{lists.by_week.map((g) => <option key={g.key} value={g.key}>{g.label} ({g.reports})</option>)}</select>
          <input className="input" type="date" value={f.date_from} onChange={(e) => setF({ ...f, date_from: e.target.value })} title="From" />
          <input className="input" type="date" value={f.date_to} onChange={(e) => setF({ ...f, date_to: e.target.value })} title="To" />
        </div>
        {filtered && <div className="mt-2 text-xs text-sky-900">Every figure and export follows these filters. <button className="font-semibold underline" onClick={() => setF({ phase: "", district_id: "", week: "", date_from: "", date_to: "" })}>Clear</button></div>}
      </Card>

      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
        <KpiTile label="Reports" value={d.reports} sub={`${d.officers} officer${d.officers === 1 ? "" : "s"}`} />
        <KpiTile label="Coverage" value={pct(d.coverage_pct)} tone={tone(d.coverage_pct, 80, 50)} sub="households done ÷ expected" />
        <KpiTile label="Synced to HQ" value={pct(d.synced_pct)} tone={tone(d.synced_pct, 95, 80)} sub="cases synced ÷ completed" />
        <KpiTile label="Error rate" value={pct(d.error_pct)} tone={d.error_pct === null ? "navy" : d.error_pct <= 5 ? "green" : d.error_pct <= 10 ? "amber" : "red"} sub="households with errors ÷ reviewed" />
        <KpiTile label="Tablets working" value={pct(d.tablets_pct)} tone={tone(d.tablets_pct, 95, 90)} sub="working ÷ issued" />
        <KpiTile label="On schedule" value={pct(d.on_schedule_pct)} tone={tone(d.on_schedule_pct, 90, 70)} sub="teams on the calendar" />
        <KpiTile label="Safety concerns" value={d.safety_concerns} tone={d.safety_concerns ? "red" : "navy"} sub={`${d.escalations} escalation${d.escalations === 1 ? "" : "s"} requested`} />
        <KpiTile label="Overall rating" value={d.overall ?? "—"} tone={d.overall === null ? "navy" : d.overall >= 3 ? "green" : d.overall >= 2 ? "amber" : "red"} sub="1 poor · 4 very good" />
      </div>

      {d.reports === 0 ? <Card><Empty text="No report for these filters yet." /></Card> : (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card title="Needs attention" className="lg:col-span-2">
            {d.attention.length === 0 ? <div className="flex items-center gap-2 py-3 text-sm text-emerald-800"><ShieldAlert size={16} /> Nothing flagged: no safety concern, escalation, sync or schedule problem in these reports.</div> : (
              <ul className="divide-y divide-slate-100">
                {d.attention.map((a) => (
                  <li key={a.report_id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
                    <div><AlertTriangle size={14} className="mr-1 inline text-amber-600" /><b>{a.district ?? "No district"}</b>{a.sa ? ` · ${a.sa}` : ""} · {fmtDate(a.report_date)} · {PHASES.find(([v]) => v === a.phase)?.[1] ?? a.phase}{a.officer ? ` · ${a.officer}` : ""}<div className="text-xs text-red-700">{a.reasons.join(" · ")}</div></div>
                    <Link to={`/me/kpi/reports?open=${a.report_id}`} className="text-xs text-navy underline">Open</Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <Card title="Coverage, sync and tablets by district (%)">
            <div style={{ height: 60 + 44 * Math.max(distRows.length, 2) }}>
              <ResponsiveContainer>
                <BarChart data={distRows} layout="vertical" margin={{ left: 10, right: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" domain={[0, 100]} unit="%" tick={{ fontSize: 12 }} /><YAxis type="category" dataKey="name" width={120} tick={{ fontSize: 12 }} />
                  <Tooltip /><Legend />
                  <Bar dataKey="Coverage" fill={NAVY} isAnimationActive={false} /><Bar dataKey="Synced" fill={GREEN} isAnimationActive={false} /><Bar dataKey="Tablets" fill={SKY} isAnimationActive={false} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
          <Card title="Community engagement and entry">
            <ul className="space-y-2">
              {community.map(([label, v]) => (
                <li key={label}>
                  <div className="flex justify-between text-sm"><span>{label}</span><span className="font-semibold">{pct(v)}</span></div>
                  <div className="h-2.5 rounded-full bg-slate-100"><div className="h-2.5 rounded-full" style={{ width: `${v ?? 0}%`, background: colorFor(v, 80, 60) }} /></div>
                </li>
              ))}
            </ul>
            <p className="mt-2 text-xs text-slate-500">Share of reports answering Yes (or All / Most for awareness).</p>
          </Card>
          <Card title="Week by week (%)" className="lg:col-span-2">
            {weekRows.length === 0 ? <Empty text="No reporting week recorded yet (field practice reports carry no week)." /> : (
              <div style={{ height: 260 }}>
                <ResponsiveContainer>
                  <LineChart data={weekRows} margin={{ left: 0, right: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="name" tick={{ fontSize: 12 }} /><YAxis domain={[0, 100]} unit="%" tick={{ fontSize: 12 }} />
                    <Tooltip /><Legend />
                    <Line type="monotone" dataKey="Coverage %" stroke={NAVY} strokeWidth={3} isAnimationActive={false} />
                    <Line type="monotone" dataKey="Synced %" stroke={GREEN} isAnimationActive={false} />
                    <Line type="monotone" dataKey="Error rate %" stroke={RED} isAnimationActive={false} />
                    <Line type="monotone" dataKey="On schedule %" stroke={AMBER} isAnimationActive={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </Card>
          <Card title="Delays and blockers (KPI 6)"><CountBars rows={d.blockers} color={AMBER} /></Card>
          <Card title="Types of error observed (KPI 7)"><CountBars rows={d.error_types} color={RED} /></Card>
          <Card title="Risks that could interrupt enumeration (KPI 11)"><CountBars rows={d.risks} color={NAVY} /></Card>
          <Card title="Communication channels that reached the community (KPI 1)"><CountBars rows={d.channels} color={GREEN} /></Card>
          <Card title="Overall state of the SAs (Section B)">
            <div style={{ height: 150 }}>
              <ResponsiveContainer>
                <BarChart data={d.overall_counts} margin={{ left: 0, right: 10 }}>
                  <XAxis dataKey="label" tick={{ fontSize: 12 }} /><YAxis allowDecimals={false} tick={{ fontSize: 12 }} /><Tooltip />
                  <Bar dataKey="count" isAnimationActive={false}>{d.overall_counts.map((c) => <Cell key={c.code} fill={{ "4": GREEN, "3": "#65a30d", "2": AMBER, "1": RED }[c.code] ?? NAVY} />)}</Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
          <Card title="By phase"><GroupTable rows={d.by_phase} first="Phase" /></Card>
          <Card title="By district" className="lg:col-span-2"><GroupTable rows={d.by_district} first="District" /></Card>
          <Card title="By M&E officer" className="lg:col-span-2" action={<span className="text-xs text-slate-400"><Users size={12} className="mr-1 inline" />{d.officers} officers</span>}><GroupTable rows={d.by_officer} first="Officer" /></Card>
        </div>
      )}
    </div>
  );
}
