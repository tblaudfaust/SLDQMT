import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";
import clsx from "clsx";
import { Printer } from "lucide-react";
import { api, fmtDate, qs } from "../../../api/client";
import type { MeKpiReport, MeKpiSummary } from "../../../api/types";
import { Empty, ErrorBox, Spinner } from "../../../components/ui";
import { HeatCell, KPIS, PHASES, Panel, Progress, Scorecard, pct, phaseLabel, phaseShort, ratingLabel, status, statusBg } from "./kpiUi";

/** Printable M&E report for one district (or the whole scope): scorecards, SA table, flagged visits,
 *  community engagement and what the officers wrote about strengths, weaknesses, safety and escalations. */
export default function KpiDistrictReportPage() {
  const [params, setParams] = useSearchParams();
  const district_id = params.get("district_id") ?? "";
  const phase = params.get("phase") ?? "";
  const f = { district_id, phase };
  const all = useQuery({ queryKey: ["me-kpi", "summary", "all"], queryFn: () => api.get<MeKpiSummary>("/me/kpi/summary") });
  const sm = useQuery({ queryKey: ["me-kpi", "summary", qs(f)], queryFn: () => api.get<MeKpiSummary>(`/me/kpi/summary${qs(f)}`) });
  const rows = useQuery({ queryKey: ["me-kpi", "reports", qs(f)], queryFn: () => api.get<MeKpiReport[]>(`/me/kpi/reports${qs(f)}`) });
  const set = (k: string, v: string) => { const p = new URLSearchParams(params); if (v) p.set(k, v); else p.delete(k); setParams(p, { replace: true }); };
  const d = sm.data;
  const reports = rows.data ?? [];
  const districtName = all.data?.by_district.find((g) => g.key === district_id)?.label ?? (district_id ? `District ${district_id}` : d?.scope ?? "");

  // one line per SA / practice team: the latest report, and how many visits
  const sas = useMemo(() => {
    const m = new Map<string, { key: string; code: string; name: string; chiefdom: string | null; visits: number; latest: MeKpiReport; phases: Set<string> }>();
    for (const r of [...reports].sort((a, b) => a.report_date.localeCompare(b.report_date))) {
      const key = r.sa_code ? `sa:${r.sa_code}` : `pt:${r.practice_team ?? "?"}`;
      const cur = m.get(key);
      if (cur) { cur.visits += 1; cur.latest = r; cur.phases.add(r.phase); } else m.set(key, { key, code: r.sa_code ?? "", name: r.sa_code ? r.sa_name ?? "" : r.practice_team ?? "", chiefdom: r.chiefdom, visits: 1, latest: r, phases: new Set([r.phase]) });
    }
    return [...m.values()].sort((a, b) => (a.code || a.name).localeCompare(b.code || b.name));
  }, [reports]);
  const texts = (code: string) => {
    const seen = new Map<string, number>();
    for (const r of reports) { const t = r.answers[code]; if (typeof t === "string" && t.trim() && !/^none( raised)?$/i.test(t.trim())) seen.set(t.trim(), (seen.get(t.trim()) ?? 0) + 1); }
    return [...seen.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8);
  };
  if (sm.isLoading || rows.isLoading) return <Spinner />;
  if (sm.error || !d) return <ErrorBox error={sm.error} />;
  const generated = new Date().toLocaleString("en-GB", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
  const period = reports.length ? `${fmtDate(reports[reports.length - 1].report_date)} – ${fmtDate(reports[0].report_date)}` : "—";

  return (
    <div className="max-w-6xl print-area">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 no-print">
        <div>
          <Link to="/me/kpi/dashboard" className="inline-flex items-center gap-1 text-lg font-bold text-navy hover:underline">← Dashboard</Link>
          <p className="text-sm text-slate-500">Choose the district and, if needed, the phase; then print or save as PDF.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select className="input" value={district_id} onChange={(e) => set("district_id", e.target.value)}><option value="">Whole scope</option>{(all.data?.by_district ?? []).filter((g) => g.key !== "0").map((g) => <option key={g.key} value={g.key}>{g.label} ({g.reports})</option>)}</select>
          <select className="input" value={phase} onChange={(e) => set("phase", e.target.value)}><option value="">All phases</option>{PHASES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
          <button className="btn-primary" onClick={() => window.print()}><Printer size={16} /> Print / save PDF</button>
        </div>
      </div>

      {/* ---- report head ---- */}
      <div className="mb-4 flex items-center gap-4 border-b-4 border-navy pb-3">
        <img src="/statsl-logo.png" alt="" className="h-16 w-16" />
        <div className="flex-1">
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">Statistics Sierra Leone · 2026 Population and Housing Census · Monitoring &amp; Evaluation</div>
          <h1 className="text-2xl font-extrabold text-navy">M&amp;E field report · {districtName || "all districts"}{phase ? ` · ${phaseLabel(phase)}` : ""}</h1>
          <div className="text-sm text-slate-600">Period {period} · {d.reports} report{d.reports === 1 ? "" : "s"} from {d.sas} SA{d.sas === 1 ? "" : "s"} / teams by {d.officers} officer{d.officers === 1 ? "" : "s"} · generated {generated}</div>
        </div>
      </div>

      {d.reports === 0 ? <Panel title="No data"><Empty text="No report for this district yet." /></Panel> : (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 2xl:grid-cols-6">
            <Scorecard value={pct(d.coverage_pct)} raw={d.coverage_pct} {...KPIS.coverage} />
            <Scorecard value={pct(d.synced_pct)} raw={d.synced_pct} {...KPIS.synced} />
            <Scorecard value={pct(d.error_pct, 1)} raw={d.error_pct} {...KPIS.error} />
            <Scorecard value={pct(d.tablets_pct)} raw={d.tablets_pct} {...KPIS.tablets} />
            <Scorecard value={pct(d.on_schedule_pct)} raw={d.on_schedule_pct} {...KPIS.schedule} />
            <Scorecard label="Overall state" value={d.overall === null ? "—" : `${d.overall}/4`} raw={d.overall === null ? null : d.overall * 25} good={75} warn={50} help={ratingLabel(d.overall)} />
          </div>

          <Panel title="Summary" subtitle="Headline figures of the period">
            <div className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
              <div>Households done ÷ expected: <b>{pct(d.coverage_pct)}</b>; cases synced to HQ: <b>{pct(d.synced_pct)}</b>; error rate at review: <b>{pct(d.error_pct, 1)}</b>.</div>
              <div>Tablets working: <b>{pct(d.tablets_pct)}</b>; teams on schedule: <b>{pct(d.on_schedule_pct)}</b>; re-interviews completed: <b>{pct(d.reinterview_pct)}</b>.</div>
              <div>Community informed <b>{pct(d.informed_pct)}</b>, aware <b>{pct(d.aware_pct)}</b>, trust <b>{pct(d.trust_pct)}</b>, leaders' support <b>{pct(d.support_pct)}</b>.</div>
              <div><b className={d.safety_concerns ? "text-red-700" : ""}>{d.safety_concerns}</b> safety concern{d.safety_concerns === 1 ? "" : "s"}, <b className={d.escalations ? "text-amber-800" : ""}>{d.escalations}</b> escalation{d.escalations === 1 ? "" : "s"}, {d.follow_ups} follow-up visit{d.follow_ups === 1 ? "" : "s"} planned; {d.attention.length} report{d.attention.length === 1 ? "" : "s"} need attention.</div>
            </div>
          </Panel>

          <Panel title="Supervisory areas and practice teams" subtitle="Latest visit of each SA / team in the period">
            <div className="overflow-x-auto">
              <table className="table text-sm">
                <thead><tr><th>SA / team</th><th>Chiefdom</th><th>Phases</th><th className="text-right">Visits</th><th>Last visit</th><th>Respondent</th><th className="text-right">Coverage</th><th className="text-right">Synced</th><th className="text-right">Error</th><th className="text-right">Tablets</th><th>Overall</th><th>Flags</th></tr></thead>
                <tbody>
                  {sas.map((s) => {
                    const m = s.latest.metrics;
                    return (
                      <tr key={s.key}>
                        <td className="min-w-[200px] font-semibold">{s.code || s.name}{s.code && s.name ? <span className="block max-w-[260px] truncate text-[11px] font-normal text-slate-500" title={s.name}>{s.name}</span> : null}</td>
                        <td>{s.chiefdom ?? "—"}</td><td className="whitespace-nowrap text-xs">{[...s.phases].map(phaseShort).join(", ")}</td><td className="text-right tabular-nums">{s.visits}</td>
                        <td className="whitespace-nowrap">{fmtDate(s.latest.report_date)}{s.latest.week ? <span className="text-xs text-slate-400"> · wk {s.latest.week}</span> : ""}</td>
                        <td className="whitespace-nowrap">{s.latest.respondent_name ?? "—"}<span className="block text-[11px] text-slate-400">{s.latest.respondent_role_label ?? ""}{s.latest.collection_mode_label ? ` · ${s.latest.collection_mode_label.toLowerCase()}` : ""}</span></td>
                        <HeatCell v={m.coverage_pct} {...KPIS.coverage} /><HeatCell v={m.synced_pct} {...KPIS.synced} /><HeatCell v={m.error_pct} {...KPIS.error} /><HeatCell v={m.tablets_pct} {...KPIS.tablets} />
                        <td><span className={clsx("rounded-full px-2 py-0.5 text-xs font-semibold", statusBg[status(m.overall === null ? null : m.overall * 25, 75, 50)])}>{m.overall ? ["", "Poor", "Weak", "Good", "Very good"][m.overall] : "—"}</span></td>
                        <td className="text-xs">{m.safety_concern && <span className="mr-1 rounded-full bg-red-100 px-2 py-0.5 font-semibold text-red-800">Safety</span>}{m.escalation && <span className="mr-1 rounded-full bg-amber-100 px-2 py-0.5 font-semibold text-amber-800">Escalate</span>}{m.follow_up && <span className="rounded-full bg-sky-100 px-2 py-0.5 font-semibold text-sky-800">Follow-up</span>}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Panel>

          <div className="grid gap-4 md:grid-cols-2">
            <Panel title="Community engagement and entry" subtitle="Share of reports answering Yes">
              <ul className="space-y-3">
                <Progress label="Community informed" v={d.informed_pct} good={85} warn={60} />
                <Progress label="Households aware (all or most)" v={d.aware_pct} good={85} warn={60} />
                <Progress label="Respondents trust the enumerators" v={d.trust_pct} good={90} warn={70} />
                <Progress label="Leaders support participation" v={d.support_pct} good={85} warn={60} />
                <Progress label="A channel to ask or complain exists" v={d.channel_pct} good={80} warn={60} />
              </ul>
            </Panel>
            <Panel title="Needs attention" subtitle="Visits flagged by the dashboard rules">
              {d.attention.length === 0 ? <p className="text-sm text-emerald-800">Nothing flagged.</p> : (
                <ul className="space-y-1.5 text-sm">
                  {d.attention.slice(0, 12).map((a) => <li key={a.report_id} className="rounded-md bg-amber-50 px-2 py-1"><b>{a.sa ?? a.district ?? "—"}</b> · {fmtDate(a.report_date)} · {phaseLabel(a.phase)}<span className="block text-xs text-red-800">{a.reasons.join(" · ")}</span></li>)}
                  {d.attention.length > 12 && <li className="text-xs text-slate-500">… and {d.attention.length - 12} more on the dashboard.</li>}
                </ul>
              )}
            </Panel>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <TextList title="Strengths observed" subtitle="KPI 11 · most frequent remarks" items={texts("k11_1")} tone="green" />
            <TextList title="Weaknesses and bottlenecks" subtitle="KPI 11" items={texts("k11_2")} tone="amber" />
            <TextList title="Safety and security concerns" subtitle="KPI 11 · also in the Census Incident Log" items={texts("k11_4")} tone="red" />
            <TextList title="Issues escalated" subtitle="Section B · issue · to whom · by when" items={texts("b2")} tone="navy" />
            <TextList title="Hard-to-reach areas" subtitle="KPI 5" items={texts("k5_4")} tone="navy" />
            <TextList title="Syncing challenges" subtitle="KPI 10" items={texts("k10_5")} tone="amber" />
          </div>

          <Panel title="M&E officers" subtitle="Who reported in this period">
            <div className="overflow-x-auto">
              <table className="table text-sm">
                <thead><tr><th>Officer</th><th className="text-right">Reports</th><th className="text-right">SAs</th><th className="text-right">Coverage</th><th className="text-right">Synced</th><th className="text-right">Error rate</th><th className="text-right">Overall</th></tr></thead>
                <tbody>{d.by_officer.map((g) => <tr key={g.key}><td className="font-semibold">{g.label}</td><td className="text-right">{g.reports}</td><td className="text-right">{g.sas}</td><HeatCell v={g.coverage_pct} {...KPIS.coverage} /><HeatCell v={g.synced_pct} {...KPIS.synced} /><HeatCell v={g.error_pct} {...KPIS.error} /><td className="text-right font-semibold">{g.overall ?? "—"}</td></tr>)}</tbody>
              </table>
            </div>
          </Panel>
          <p className="text-[11px] text-slate-400">Targets: coverage ≥ 80 %, synced ≥ 95 %, error rate ≤ 5 %, tablets ≥ 95 %, on schedule ≥ 90 %. Figures are averages of the M&amp;E officers' reports in the period; one report per SA visit.</p>
        </div>
      )}
    </div>
  );
}

function TextList({ title, subtitle, items, tone }: { title: string; subtitle: string; items: [string, number][]; tone: "green" | "amber" | "red" | "navy" }) {
  const dot = { green: "bg-emerald-500", amber: "bg-amber-500", red: "bg-red-600", navy: "bg-navy" }[tone];
  return (
    <Panel title={title} subtitle={subtitle}>
      {items.length === 0 ? <p className="text-sm text-slate-400">None reported.</p> : (
        <ul className="space-y-1 text-sm">{items.map(([t, n]) => <li key={t} className="flex items-start gap-2"><span className={clsx("mt-1.5 h-2 w-2 shrink-0 rounded-full", dot)} /><span>{t}{n > 1 && <span className="text-xs text-slate-400"> ×{n}</span>}</span></li>)}</ul>
      )}
    </Panel>
  );
}
