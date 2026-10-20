import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import clsx from "clsx";
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AlertTriangle, ArrowDownUp, Download, FileText, Printer, ShieldAlert, ShieldCheck, Users } from "lucide-react";
import { ApiError, api, download, fmtDate, qs } from "../../../api/client";
import type { MeKpiGroup, MeKpiSummary } from "../../../api/types";
import { useAuth } from "../../../auth/AuthContext";
import { Empty, ErrorBox, Spinner } from "../../../components/ui";
import { AMBER, Bars, CountCard, GREEN, HeatCell, KPIS, LIME, NAVY, PHASES, Panel, Progress, RED, SKY, Scorecard, pct, phaseLabel, ratingLabel } from "./kpiUi";

type SortKey = keyof Pick<MeKpiGroup, "label" | "reports" | "coverage_pct" | "synced_pct" | "error_pct" | "tablets_pct" | "on_schedule_pct" | "informed_pct" | "support_pct" | "overall" | "safety_concerns" | "escalations">;
const emptyFilters = { phase: "", district_id: "", week: "", date_from: "", date_to: "" };

/** KPI dashboard of the M&E field tool: scorecards against targets, a district heat table, trends by week and phase,
 *  community engagement, blockers and risks, the reports that need attention and the officers' output. */
export default function KpiDashboardPage() {
  const { can } = useAuth();
  const [f, setF] = useState(emptyFilters);
  const query = qs(f);
  const res = useQuery({ queryKey: ["me-kpi", "summary", query], queryFn: () => api.get<MeKpiSummary>(`/me/kpi/summary${query}`) });
  const all = useQuery({ queryKey: ["me-kpi", "summary", "all"], queryFn: () => api.get<MeKpiSummary>("/me/kpi/summary") });
  const [error, setError] = useState<unknown>(null);
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "label", dir: 1 });
  const d = res.data;
  const districts = useMemo(() => {
    const rows = (d?.by_district ?? []).filter((g) => g.key !== "0");
    const v = (g: MeKpiGroup) => g[sort.key];
    return [...rows].sort((a, b) => { const x = v(a), y = v(b); if (x === y) return 0; if (x === null || x === undefined) return 1; if (y === null || y === undefined) return -1; return (x < y ? -1 : 1) * sort.dir; });
  }, [d, sort]);
  if (res.isLoading) return <Spinner />;
  if (res.error || !d) return <ErrorBox error={res.error} />;
  const lists = all.data ?? d;
  const filtered = Object.values(f).some(Boolean);
  const exportFile = async (format: "xlsx" | "pdf") => { setError(null); try { await download(`/me/kpi/export${qs({ ...f, format })}`, `me-kpi.${format}`); } catch (e) { setError(e); } };
  const toggleSort = (key: SortKey) => setSort((s) => ({ key, dir: s.key === key ? (s.dir === 1 ? -1 : 1) : key === "label" ? 1 : -1 }));
  const distRows = districts.map((g) => ({ name: g.label, Coverage: g.coverage_pct ?? 0, Synced: g.synced_pct ?? 0, Tablets: g.tablets_pct ?? 0 }));
  const weekRows = d.by_week.map((g) => ({ name: g.label, "Coverage %": g.coverage_pct ?? 0, "Synced %": g.synced_pct ?? 0, "Error rate %": g.error_pct ?? 0, "On schedule %": g.on_schedule_pct ?? 0 }));
  const phaseRows = d.by_phase.map((g) => ({ name: phaseLabel(g.key), Coverage: g.coverage_pct ?? 0, Synced: g.synced_pct ?? 0, "Error rate": g.error_pct ?? 0, Tablets: g.tablets_pct ?? 0 }));
  const SortTh = ({ k, children, right = true }: { k: SortKey; children: React.ReactNode; right?: boolean }) => (
    <th className={clsx("cursor-pointer select-none whitespace-nowrap", right && "text-right")} onClick={() => toggleSort(k)}>{children}{sort.key === k && <ArrowDownUp size={11} className="ml-1 inline text-slate-400" />}</th>
  );

  return (
    <div className="max-w-7xl">
      {/* ---- header band ---- */}
      <div className="mb-4 rounded-2xl bg-gradient-to-r from-navy to-[#2f6fa8] p-5 text-white shadow">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <Link to="/me/kpi" className="inline-flex items-center gap-1 text-sm font-bold text-sky-100 hover:underline no-print">← M&amp;E Field Tool</Link>
            <h1 className="text-2xl font-extrabold">M&amp;E KPI dashboard</h1>
            <p className="mt-1 text-sm text-sky-100">
              Scope <b className="text-white">{d.scope}</b> · {d.reports} report{d.reports === 1 ? "" : "s"} · {d.sas} SA{d.sas === 1 ? "" : "s"} / teams · {d.districts} district{d.districts === 1 ? "" : "s"} · {d.officers} officer{d.officers === 1 ? "" : "s"}{d.last_date ? ` · last report ${fmtDate(d.last_date)}` : ""}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2 no-print">
            <Link to="/me/kpi/reports" className="rounded-lg bg-white/15 px-3 py-2 text-sm font-semibold hover:bg-white/25"><FileText size={15} className="mr-1 inline" />All reports</Link>
            <Link to={`/me/kpi/district-report${f.district_id ? `?district_id=${f.district_id}` : ""}`} className="rounded-lg bg-white/15 px-3 py-2 text-sm font-semibold hover:bg-white/25"><Printer size={15} className="mr-1 inline" />District report</Link>
            {can("me_kpi.export") && <button className="rounded-lg bg-white px-3 py-2 text-sm font-semibold text-navy hover:bg-sky-50" onClick={() => exportFile("xlsx")}><Download size={15} className="mr-1 inline" />Excel</button>}
            {can("me_kpi.export") && <button className="rounded-lg bg-white px-3 py-2 text-sm font-semibold text-navy hover:bg-sky-50" onClick={() => exportFile("pdf")}><Download size={15} className="mr-1 inline" />PDF</button>}
          </div>
        </div>
        <div className="mt-4 grid gap-2 sm:grid-cols-3 lg:grid-cols-6 no-print">
          <select className="input text-slate-800" value={f.phase} onChange={(e) => setF({ ...f, phase: e.target.value })}><option value="">All phases</option>{PHASES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
          <select className="input text-slate-800" value={f.district_id} onChange={(e) => setF({ ...f, district_id: e.target.value })}><option value="">All districts</option>{lists.by_district.filter((g) => g.key !== "0").map((g) => <option key={g.key} value={g.key}>{g.label} ({g.reports})</option>)}</select>
          <select className="input text-slate-800" value={f.week} onChange={(e) => setF({ ...f, week: e.target.value })}><option value="">All weeks</option>{lists.by_week.map((g) => <option key={g.key} value={g.key}>{g.label} ({g.reports})</option>)}</select>
          <input className="input text-slate-800" type="date" value={f.date_from} onChange={(e) => setF({ ...f, date_from: e.target.value })} title="From" />
          <input className="input text-slate-800" type="date" value={f.date_to} onChange={(e) => setF({ ...f, date_to: e.target.value })} title="To" />
          <button className={clsx("rounded-lg px-3 py-2 text-sm font-semibold", filtered ? "bg-amber-400 text-amber-950" : "bg-white/10 text-sky-100")} onClick={() => setF(emptyFilters)} disabled={!filtered}>{filtered ? "Clear filters" : "No filter"}</button>
        </div>
      </div>
      <ErrorBox error={error instanceof ApiError ? error.message : error} />

      {/* ---- scorecards ---- */}
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Scorecard value={pct(d.coverage_pct)} raw={d.coverage_pct} {...KPIS.coverage} />
        <Scorecard value={pct(d.synced_pct)} raw={d.synced_pct} {...KPIS.synced} />
        <Scorecard value={pct(d.error_pct, 1)} raw={d.error_pct} {...KPIS.error} />
        <Scorecard value={pct(d.tablets_pct)} raw={d.tablets_pct} {...KPIS.tablets} />
        <Scorecard value={pct(d.on_schedule_pct)} raw={d.on_schedule_pct} {...KPIS.schedule} />
        <Scorecard label="Re-interviews done" value={pct(d.reinterview_pct)} raw={d.reinterview_pct} good={90} warn={60} help="Completed ÷ selected by the supervisor" />
      </div>
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <CountCard label="Overall state" value={d.overall === null ? "—" : `${d.overall} / 4`} sub={ratingLabel(d.overall)} tone={d.overall === null ? "navy" : d.overall >= 3 ? "green" : d.overall >= 2 ? "amber" : "red"} icon={<ShieldCheck size={16} />} />
        <CountCard label="Safety concerns" value={d.safety_concerns} sub="reports with a safety / security concern" tone={d.safety_concerns ? "red" : "navy"} icon={<ShieldAlert size={16} />} />
        <CountCard label="Escalations" value={d.escalations} sub={`${d.follow_ups} follow-up visit${d.follow_ups === 1 ? "" : "s"} planned`} tone={d.escalations ? "amber" : "navy"} icon={<AlertTriangle size={16} />} />
        <CountCard label="Needs attention" value={d.attention.length} sub={`of ${d.reports} reports flagged by the rules below`} tone={d.attention.length ? "amber" : "green"} icon={<Users size={16} />} />
      </div>

      {d.reports === 0 ? <Panel title="No data"><Empty text="No report for these filters yet." /></Panel> : (
        <div className="grid gap-4 lg:grid-cols-2">
          {/* ---- district heat table ---- */}
          <Panel title="District scorecard" subtitle="Average of the reports in each district · click a heading to sort, a district to filter" className="lg:col-span-2">
            <div className="overflow-x-auto">
              <table className="table text-sm">
                <thead><tr>
                  <SortTh k="label" right={false}>District</SortTh><SortTh k="reports">Reports</SortTh><SortTh k="coverage_pct">Coverage</SortTh><SortTh k="synced_pct">Synced</SortTh><SortTh k="error_pct">Error rate</SortTh><SortTh k="tablets_pct">Tablets</SortTh><SortTh k="on_schedule_pct">On schedule</SortTh><SortTh k="informed_pct">Informed</SortTh><SortTh k="support_pct">Leaders</SortTh><SortTh k="overall">Overall</SortTh><SortTh k="safety_concerns">Safety</SortTh><SortTh k="escalations">Escal.</SortTh>
                </tr></thead>
                <tbody>
                  {districts.map((g) => (
                    <tr key={g.key} className="cursor-pointer hover:bg-sky-50" onClick={() => setF({ ...f, district_id: f.district_id === g.key ? "" : g.key })}>
                      <td className={clsx("font-semibold", f.district_id === g.key && "text-navy underline")}>{g.label}<span className="block whitespace-nowrap text-[11px] font-normal text-slate-400">{g.sas} SA{g.sas === 1 ? "" : "s"} · {g.officers} officer{g.officers === 1 ? "" : "s"}</span></td>
                      <td className="text-right tabular-nums">{g.reports}</td>
                      <HeatCell v={g.coverage_pct} {...KPIS.coverage} /><HeatCell v={g.synced_pct} {...KPIS.synced} /><HeatCell v={g.error_pct} {...KPIS.error} /><HeatCell v={g.tablets_pct} {...KPIS.tablets} /><HeatCell v={g.on_schedule_pct} {...KPIS.schedule} /><HeatCell v={g.informed_pct} {...KPIS.informed} /><HeatCell v={g.support_pct} {...KPIS.support} />
                      <td className="text-right font-semibold tabular-nums" style={{ color: g.overall === null ? undefined : g.overall >= 3 ? GREEN : g.overall >= 2 ? AMBER : RED }}>{g.overall ?? "—"}</td>
                      <td className={clsx("text-right tabular-nums", g.safety_concerns && "font-bold text-red-700")}>{g.safety_concerns || "·"}</td>
                      <td className={clsx("text-right tabular-nums", g.escalations && "font-bold text-amber-800")}>{g.escalations || "·"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-slate-500"><span><i className="mr-1 inline-block h-2.5 w-2.5 rounded-sm bg-emerald-100 align-middle" />on target</span><span><i className="mr-1 inline-block h-2.5 w-2.5 rounded-sm bg-amber-100 align-middle" />watch</span><span><i className="mr-1 inline-block h-2.5 w-2.5 rounded-sm bg-red-100 align-middle" />off target</span><span>Targets: coverage ≥ 80 %, synced ≥ 95 %, error rate ≤ 5 %, tablets ≥ 95 %, on schedule ≥ 90 %, informed / leaders ≥ 85 %</span></div>
          </Panel>

          {/* ---- attention ---- */}
          <Panel title="Needs attention" subtitle="Low sync, high error rate, tablets down, behind schedule, safety, distrust, escalation or a weak rating" className="lg:col-span-2">
            {d.attention.length === 0 ? <div className="flex items-center gap-2 py-3 text-sm text-emerald-800"><ShieldCheck size={16} /> Nothing flagged in these reports.</div> : (
              <ul className="grid gap-2 md:grid-cols-2">
                {d.attention.map((a) => (
                  <li key={a.report_id} className="flex items-start justify-between gap-2 rounded-lg border border-amber-100 bg-amber-50/50 px-3 py-2 text-sm">
                    <div>
                      <div className="font-semibold text-slate-800"><AlertTriangle size={14} className="mr-1 inline text-amber-600" />{a.district ?? "No district"}{a.sa ? ` · ${a.sa}` : ""}<span className="font-normal text-slate-500"> · {fmtDate(a.report_date)} · {phaseLabel(a.phase)}{a.officer ? ` · ${a.officer}` : ""}</span></div>
                      <div className="mt-1 flex flex-wrap gap-1">{a.reasons.map((r) => <span key={r} className={clsx("rounded-full px-2 py-0.5 text-[11px] font-semibold", /safety/i.test(r) ? "bg-red-100 text-red-800" : "bg-white text-amber-900 ring-1 ring-amber-200")}>{r}</span>)}</div>
                    </div>
                    <Link to={`/me/kpi/reports?open=${a.report_id}`} className="shrink-0 text-xs font-semibold text-navy underline no-print">Open</Link>
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          {/* ---- charts ---- */}
          <Panel title="Coverage, sync and tablets by district" subtitle="Percent · sorted like the scorecard">
            <div style={{ height: 60 + 40 * Math.max(distRows.length, 2) }}>
              <ResponsiveContainer>
                <BarChart data={distRows} layout="vertical" margin={{ left: 10, right: 20 }} barGap={2}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" domain={[0, 100]} unit="%" tick={{ fontSize: 12 }} /><YAxis type="category" dataKey="name" width={110} tick={{ fontSize: 12 }} />
                  <Tooltip formatter={(v: number) => `${v}%`} /><Legend />
                  <Bar dataKey="Coverage" fill={NAVY} isAnimationActive={false} radius={[0, 3, 3, 0]} /><Bar dataKey="Synced" fill={GREEN} isAnimationActive={false} radius={[0, 3, 3, 0]} /><Bar dataKey="Tablets" fill={SKY} isAnimationActive={false} radius={[0, 3, 3, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Panel>
          <div className="grid gap-4">
            <Panel title="Week by week" subtitle="Listing and enumeration reports carry a reporting week">
              {weekRows.length === 0 ? <Empty text="No reporting week yet." /> : (
                <div style={{ height: 230 }}>
                  <ResponsiveContainer>
                    <LineChart data={weekRows} margin={{ left: 0, right: 10 }}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} />
                      <XAxis dataKey="name" tick={{ fontSize: 12 }} /><YAxis domain={[0, 100]} unit="%" tick={{ fontSize: 12 }} />
                      <Tooltip formatter={(v: number) => `${v}%`} /><Legend />
                      <Line type="monotone" dataKey="Coverage %" stroke={NAVY} strokeWidth={3} dot={{ r: 4 }} isAnimationActive={false} />
                      <Line type="monotone" dataKey="Synced %" stroke={GREEN} strokeWidth={2} isAnimationActive={false} />
                      <Line type="monotone" dataKey="Error rate %" stroke={RED} strokeWidth={2} isAnimationActive={false} />
                      <Line type="monotone" dataKey="On schedule %" stroke={AMBER} strokeWidth={2} isAnimationActive={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}
            </Panel>
            <Panel title="By census phase" subtitle="Field practice versus listing and enumeration">
              <div style={{ height: 220 }}>
                <ResponsiveContainer>
                  <BarChart data={phaseRows} margin={{ left: 0, right: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="name" tick={{ fontSize: 11 }} /><YAxis domain={[0, 100]} unit="%" tick={{ fontSize: 12 }} />
                    <Tooltip formatter={(v: number) => `${v}%`} /><Legend />
                    <Bar dataKey="Coverage" fill={NAVY} isAnimationActive={false} /><Bar dataKey="Synced" fill={GREEN} isAnimationActive={false} /><Bar dataKey="Tablets" fill={SKY} isAnimationActive={false} /><Bar dataKey="Error rate" fill={RED} isAnimationActive={false} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Panel>
          </div>

          <Panel title="Community engagement and entry" subtitle="Share of reports answering Yes (All or Most for awareness)">
            <ul className="space-y-3">
              <Progress label="Community informed about purpose, dates and process" v={d.informed_pct} good={85} warn={60} />
              <Progress label="Households aware of the census (all or most)" v={d.aware_pct} good={85} warn={60} />
              <Progress label="Respondents trust the enumerators" v={d.trust_pct} good={90} warn={70} />
              <Progress label="Community leaders support participation" v={d.support_pct} good={85} warn={60} />
              <Progress label="A channel exists to ask or complain" v={d.channel_pct} good={80} warn={60} />
              <Progress label="Teams on schedule" v={d.on_schedule_pct} good={90} warn={70} />
            </ul>
          </Panel>
          <Panel title="Overall state of the SAs" subtitle="Section B rating by the M&E officer">
            <div style={{ height: 200 }}>
              <ResponsiveContainer>
                <BarChart data={d.overall_counts} margin={{ left: 0, right: 10 }}>
                  <XAxis dataKey="label" tick={{ fontSize: 12 }} /><YAxis allowDecimals={false} tick={{ fontSize: 12 }} /><Tooltip formatter={(v: number, _n, p) => [`${v} reports (${p.payload.pct ?? 0}%)`, ""]} />
                  <Bar dataKey="count" isAnimationActive={false} radius={[4, 4, 0, 0]} label={{ position: "top", fontSize: 11 }}>{d.overall_counts.map((c) => <Cell key={c.code} fill={{ "4": GREEN, "3": LIME, "2": AMBER, "1": RED }[c.code] ?? NAVY} />)}</Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Panel>

          <Panel title="Delays and blockers" subtitle="KPI 6 · data submission"><Bars rows={d.blockers} color={AMBER} /></Panel>
          <Panel title="Types of error observed" subtitle="KPI 7 · data quality"><Bars rows={d.error_types} color={RED} /></Panel>
          <Panel title="Risks that could interrupt enumeration" subtitle="KPI 11"><Bars rows={d.risks} color={NAVY} /></Panel>
          <Panel title="Channels that reached the community" subtitle="KPI 1"><Bars rows={d.channels} color={GREEN} /></Panel>

          <Panel title="By M&E officer" subtitle="Reports sent and the averages of each officer's visits" className="lg:col-span-2" action={<span className="text-xs text-slate-400"><Users size={12} className="mr-1 inline" />{d.officers} officers</span>}>
            <div className="overflow-x-auto">
              <table className="table text-sm">
                <thead><tr><th>Officer</th><th className="text-right">Reports</th><th className="text-right">SAs</th><th className="text-right">Coverage</th><th className="text-right">Synced</th><th className="text-right">Error rate</th><th className="text-right">Tablets</th><th className="text-right">On schedule</th><th className="text-right">Overall</th><th className="text-right">Safety</th><th className="text-right">Escal.</th></tr></thead>
                <tbody>
                  {d.by_officer.map((g) => (
                    <tr key={g.key}>
                      <td className="font-semibold">{g.label}</td><td className="text-right tabular-nums">{g.reports}</td><td className="text-right tabular-nums">{g.sas}</td>
                      <HeatCell v={g.coverage_pct} {...KPIS.coverage} /><HeatCell v={g.synced_pct} {...KPIS.synced} /><HeatCell v={g.error_pct} {...KPIS.error} /><HeatCell v={g.tablets_pct} {...KPIS.tablets} /><HeatCell v={g.on_schedule_pct} {...KPIS.schedule} />
                      <td className="text-right font-semibold tabular-nums">{g.overall ?? "—"}</td><td className={clsx("text-right", g.safety_concerns && "font-bold text-red-700")}>{g.safety_concerns || "·"}</td><td className={clsx("text-right", g.escalations && "font-bold text-amber-800")}>{g.escalations || "·"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </div>
      )}
    </div>
  );
}
