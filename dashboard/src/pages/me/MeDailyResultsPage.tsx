import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Fragment, useState } from "react";
import { Link, useParams } from "react-router-dom";
import clsx from "clsx";
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Copy, Download, ExternalLink, Pencil, QrCode, Trash2 } from "lucide-react";
import { ApiError, api, download, fmt, fmtDate, qs } from "../../api/client";
import type { MeDailyAgendaItem, MeDailyCount, MeDailyGroup, MeDailyLog, MeDailyReport, MeDailySummary } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { Card, Empty, ErrorBox, KpiTile, Spinner } from "../../components/ui";
import QrDialog from "../../components/QrDialog";
import { DailyReportForm, toPayload, validate, type DailySpec, type DailyValues } from "../public/DailyReportForm";
import { PHASE_LABEL, dailyLink } from "./MeDailyPage";

const C = { navy: "#1F4E79", green: "#15803d", lime: "#65a30d", amber: "#d97706", orange: "#ea580c", red: "#b91c1c", sky: "#38bdf8", slate: "#94a3b8" };
const SCORE_COLOR: Record<string, string> = { "5": C.green, "4": C.lime, "3": C.amber, "2": C.orange, "1": C.red };
const STATUS = { OPEN: "bg-red-100 text-red-800", IN_PROGRESS: "bg-amber-100 text-amber-800", RESOLVED: "bg-emerald-100 text-emerald-800" } as const;
const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${v}%`);
const num = (v: number | null | undefined, d = 2) => (v === null || v === undefined ? "—" : v.toFixed(d));
const delta = (v: number | null | undefined) => (v === null || v === undefined ? "—" : v > 0 ? `+${v}` : String(v));
type Tab = "overview" | "day" | "class" | "district" | "facilitator" | "topics" | "reports" | "issues" | "escalations";

/** One training's Daily Facilitator Reports: every indicator by day, class, district, facilitator and topic, with the logs. */
export default function MeDailyResultsPage() {
  const { id } = useParams();
  const { can } = useAuth();
  const qc = useQueryClient();
  const [f, setF] = useState({ district: "", class_hall: "", facilitator: "", phase: "", date_from: "", date_to: "" });
  const query = qs(f);
  const res = useQuery({ queryKey: ["me-daily", "summary", id, query], queryFn: () => api.get<MeDailySummary>(`/me/daily/rounds/${id}/summary${query}`) });
  const all = useQuery({ queryKey: ["me-daily", "summary", id, "all"], queryFn: () => api.get<MeDailySummary>(`/me/daily/rounds/${id}/summary`) });
  const spec = useQuery({ queryKey: ["me-daily", "form"], queryFn: () => api.get<DailySpec>("/me/daily/form") });
  const agenda = useQuery({ queryKey: ["me-daily", "agenda", id], queryFn: () => api.get<MeDailyAgendaItem[]>(`/me/daily/rounds/${id}/agenda`) });
  const [tab, setTab] = useState<Tab>("overview");
  const [open, setOpen] = useState<number | null>(null);
  const [edit, setEdit] = useState<MeDailyReport | null>(null);
  const [qr, setQr] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const invalidate = () => qc.invalidateQueries({ queryKey: ["me-daily"] });
  const remove = useMutation({ mutationFn: (r: MeDailyReport) => api.delete(`/me/daily/rounds/${id}/reports/${r.id}`), onSuccess: invalidate, onError: setError });
  const setStatus = useMutation({ mutationFn: (x: { report_id: number; index: number; status: string }) => api.patch(`/me/daily/rounds/${id}/reports/${x.report_id}/escalation`, { index: x.index, status: x.status }), onSuccess: invalidate, onError: setError });
  if (res.isLoading) return <Spinner />;
  if (res.error || !res.data) return <ErrorBox error={res.error} />;
  const d = res.data;
  const r = d.round;
  const lists = all.data ?? d;
  const filtered = Object.values(f).some(Boolean);
  const exportFile = async (format: "xlsx" | "pdf") => {
    setError(null);
    try { await download(`/me/daily/rounds/${id}/export${qs({ ...f, format })}`, `daily-${id}.${format}`); } catch (err) { setError(err); }
  };
  const dayRows = d.by_day.map((g) => ({ name: g.label, "Delivered %": g.delivered_pct ?? 0, Overall: g.overall ?? 0, "Pass rate %": g.pass_rate ?? 0, Content: g.q_content, Engagement: g.q_engagement, Time: g.q_time, Illustrations: g.q_illustrations }));
  const qualityRows = (["content", "engagement", "time", "illustrations"] as const).map((k) => ({ name: { content: "Content accuracy and clarity", engagement: "Participant engagement", time: "Time management", illustrations: "Illustrations and practice" }[k], mean: d.quality[k] ?? 0, ...Object.fromEntries(d.quality_distribution[k].map((c) => [c.code, c.count])) }));

  return (
    <div className="max-w-7xl">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link to="/me/daily" className="text-sm text-navy">← Daily Evaluation</Link>
          <h1 className="text-2xl font-bold">{r.title}</h1>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
            <span className="rounded-full bg-violet-100 px-2 py-0.5 font-semibold text-violet-800">{PHASE_LABEL[r.phase] ?? r.phase}</span>
            <span className={clsx("rounded-full px-2 py-0.5 font-semibold", r.status === "OPEN" ? "bg-green-100 text-green-800" : "bg-slate-200 text-slate-700")}>{r.status === "OPEN" ? "Open" : "Closed"}</span>
            {(r.period_start || r.period_end) && <span className="text-slate-500">{fmtDate(r.period_start)}{r.period_end ? ` – ${fmtDate(r.period_end)}` : ""}</span>}
            <span className="text-slate-500">Agenda: {r.agenda_items} sessions, {r.agenda_days} days</span>
            <button className="text-navy" onClick={() => navigator.clipboard.writeText(dailyLink(r))}><Copy size={12} className="mr-1 inline" />Copy link</button>
            <a className="text-navy" href={dailyLink(r)} target="_blank" rel="noreferrer"><ExternalLink size={12} className="mr-1 inline" />Open form</a>
            <button className="text-navy" onClick={() => setQr(true)}><QrCode size={12} className="mr-1 inline" />QR code</button>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button className="btn-outline" onClick={() => exportFile("xlsx")}><Download size={16} /> Excel</button>
          <button className="btn-outline" onClick={() => exportFile("pdf")}><Download size={16} /> PDF</button>
        </div>
      </div>
      <ErrorBox error={error instanceof ApiError ? error.message : error} />

      <Card className="mb-4">
        <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-6">
          <select className="input" value={f.district} onChange={(e) => setF({ ...f, district: e.target.value })}><option value="">All districts</option>{lists.by_district.map((g) => <option key={g.key} value={g.key}>{g.label} ({g.reports})</option>)}</select>
          <select className="input" value={f.class_hall} onChange={(e) => setF({ ...f, class_hall: e.target.value })}><option value="">All classes</option>{lists.by_class.map((g) => <option key={g.key} value={g.label}>{g.label} ({g.reports})</option>)}</select>
          <select className="input" value={f.facilitator} onChange={(e) => setF({ ...f, facilitator: e.target.value })}><option value="">All lead facilitators</option>{lists.by_facilitator.map((g) => <option key={g.key} value={g.label}>{g.label} ({g.reports})</option>)}</select>
          <select className="input" value={f.phase} onChange={(e) => setF({ ...f, phase: e.target.value })}><option value="">All phases</option>{lists.by_phase.map((g) => <option key={g.key} value={g.key}>{g.label} ({g.reports})</option>)}</select>
          <input className="input" type="date" value={f.date_from} onChange={(e) => setF({ ...f, date_from: e.target.value })} title="From date" />
          <input className="input" type="date" value={f.date_to} onChange={(e) => setF({ ...f, date_to: e.target.value })} title="To date" />
        </div>
        {filtered && <div className="mt-2 text-xs text-sky-900">Every figure and export on this page follows these filters. <button className="font-semibold underline" onClick={() => setF({ district: "", class_hall: "", facilitator: "", phase: "", date_from: "", date_to: "" })}>Clear</button></div>}
      </Card>

      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
        <KpiTile label="Daily reports" value={d.reports} sub={`${d.classes} classes · ${d.days} days · ${d.facilitators} facilitators`} />
        <KpiTile label="Sessions delivered" value={pct(d.delivered_pct)} tone={d.delivered_pct !== null && d.delivered_pct < 80 ? "amber" : "green"} sub={`${d.delivered} Y · ${d.partly} P · ${d.not_delivered} N of ${d.sessions}`} />
        <KpiTile label="Minutes over / under" value={delta(d.minutes_delta)} tone={d.minutes_delta > 0 ? "amber" : "navy"} sub={`${d.carried_over} topics carried to the next day`} />
        <KpiTile label="Overall class rating" value={num(d.quality.overall)} tone={d.quality.overall !== null && d.quality.overall < 3 ? "red" : d.quality.overall !== null && d.quality.overall < 4 ? "amber" : "green"} sub="mean of 1–5 across the four criteria" />
        <KpiTile label="Scores of 1 or 2" value={d.low_scores} tone={d.low_scores ? "red" : "navy"} sub="reports with a criterion below expectations" />
        <KpiTile label="Quiz pass rate" value={pct(d.pass_rate)} tone={d.pass_rate !== null && d.pass_rate < 70 ? "red" : "green"} sub={`${d.quizzes} quizzes · mean score ${pct(d.mean_score)}`} />
        <KpiTile label="Materials issues" value={d.material_issues} tone={d.issues_by_severity[0]?.count ? "red" : d.material_issues ? "amber" : "navy"} sub={`${d.issues_by_severity[0]?.count ?? 0} high severity`} />
        <KpiTile label="Open escalations" value={d.open_escalations} tone={d.open_escalations ? "amber" : "navy"} sub={`${d.escalations} raised to management / CCIT`} />
      </div>

      <div className="mb-4 flex flex-wrap gap-1 border-b border-slate-200">
        {([["overview", "Overview"], ["day", "By day"], ["class", "By class"], ["district", "By district"], ["facilitator", "By facilitator"], ["topics", `Topics (${d.topics.length})`], ["reports", `Reports (${d.reports})`], ["issues", `Materials issues (${d.material_issues})`], ["escalations", `Escalations (${d.escalations})`]] as [Tab, string][]).map(([t, label]) => (
          <button key={t} onClick={() => setTab(t)} className={clsx("-mb-px border-b-2 px-3 py-2 text-sm font-medium", tab === t ? "border-navy text-navy" : "border-transparent text-slate-500 hover:text-slate-700")}>{label}</button>
        ))}
      </div>

      {tab === "overview" && (d.reports === 0 ? <Card><Empty text="No daily report yet. Share the link or QR code with the lead facilitators." /></Card> : (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card title="Facilitation quality by training day (mean 1–5)" className="lg:col-span-2">
            <div style={{ height: 260 }}>
              <ResponsiveContainer>
                <LineChart data={dayRows} margin={{ left: 0, right: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} /><YAxis domain={[1, 5]} tick={{ fontSize: 12 }} />
                  <Tooltip /><Legend />
                  <Line type="monotone" dataKey="Content" stroke={C.navy} isAnimationActive={false} />
                  <Line type="monotone" dataKey="Engagement" stroke={C.green} isAnimationActive={false} />
                  <Line type="monotone" dataKey="Time" stroke={C.amber} isAnimationActive={false} />
                  <Line type="monotone" dataKey="Illustrations" stroke={C.sky} isAnimationActive={false} />
                  <Line type="monotone" dataKey="Overall" stroke={C.red} strokeWidth={3} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Card>
          <Card title="Content coverage and learning by training day">
            <div style={{ height: 240 }}>
              <ResponsiveContainer>
                <BarChart data={dayRows} margin={{ left: 0, right: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} /><YAxis domain={[0, 100]} unit="%" tick={{ fontSize: 12 }} />
                  <Tooltip /><Legend />
                  <Bar dataKey="Delivered %" fill={C.navy} isAnimationActive={false} />
                  <Bar dataKey="Pass rate %" fill={C.green} isAnimationActive={false} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
          <Card title="Facilitation quality · score distribution per criterion">
            <div style={{ height: 240 }}>
              <ResponsiveContainer>
                <BarChart data={qualityRows} layout="vertical" margin={{ left: 10, right: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" allowDecimals={false} /><YAxis type="category" dataKey="name" width={190} tick={{ fontSize: 12 }} />
                  <Tooltip /><Legend />
                  {["5", "4", "3", "2", "1"].map((s) => <Bar key={s} dataKey={s} name={`Score ${s}`} stackId="a" fill={SCORE_COLOR[s]} isAnimationActive={false} />)}
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
          <Card title="Connectivity, power and logistics (mean 1–5)">
            <div className="grid grid-cols-2 gap-3 text-center sm:grid-cols-4">
              {([["internet", "Internet"], ["power", "Power"], ["food", "Food & beverages"]] as const).map(([k, label]) => (
                <div key={k} className={clsx("rounded-md py-3", (d.logistics[k] ?? 5) < 3 ? "bg-red-50" : "bg-slate-50")}><div className={clsx("text-2xl font-bold", (d.logistics[k] ?? 5) < 3 ? "text-red-700" : "text-navy")}>{num(d.logistics[k])}</div><div className="text-xs text-slate-500">{label}</div></div>
              ))}
              <div className={clsx("rounded-md py-3", d.devices_short ? "bg-amber-50" : "bg-slate-50")}><div className={clsx("text-2xl font-bold", d.devices_short ? "text-amber-700" : "text-navy")}>{d.devices_short}</div><div className="text-xs text-slate-500">devices short (sum)</div></div>
            </div>
          </Card>
          <Card title="Participant performance and learning">
            <div className="grid grid-cols-2 gap-3 text-center sm:grid-cols-4">
              <div className="rounded-md bg-slate-50 py-3"><div className="text-2xl font-bold text-navy">{d.quizzes}</div><div className="text-xs text-slate-500">quizzes administered</div></div>
              <div className="rounded-md bg-slate-50 py-3"><div className="text-2xl font-bold text-navy">{pct(d.mean_score)}</div><div className="text-xs text-slate-500">mean score</div></div>
              <div className="rounded-md bg-slate-50 py-3"><div className="text-2xl font-bold text-green-700">{pct(d.pass_rate)}</div><div className="text-xs text-slate-500">pass rate</div></div>
              <div className="rounded-md bg-slate-50 py-3"><div className="text-2xl font-bold text-navy">{d.practice_minutes_avg ?? "—"}</div><div className="text-xs text-slate-500">practice min (avg) · {d.practice_na} N/A</div></div>
            </div>
            <CountList title="Topics participants found hardest" rows={d.hardest_topics} />
          </Card>
          <CountCard title="Materials and assessment issues · by type" rows={d.issues_by_type} color={C.amber} />
          <CountCard title="Materials and assessment issues · by severity" rows={d.issues_by_severity} color={C.red} />
          <CountCard title="Overall class rating · distribution" rows={d.overall_distribution} color={C.navy} byScore />
          <CountCard title="Escalations by status" rows={d.escalations_by_status} color={C.amber} />
        </div>
      ))}

      {tab === "day" && <GroupTable rows={d.by_day} label="Training day" />}
      {tab === "class" && <GroupTable rows={d.by_class} label="Class / hall" />}
      {tab === "district" && <GroupTable rows={d.by_district} label="District" />}
      {tab === "facilitator" && <GroupTable rows={d.by_facilitator} label="Lead facilitator" />}

      {tab === "topics" && (
        <Card title="Agenda topics across every report">
          {d.topics.length === 0 ? <Empty text="No topic yet: load the agenda or wait for reports" /> : (
            <div className="overflow-x-auto"><table className="table">
              <thead><tr><th>Topic</th><th className="text-right">Agenda day</th><th className="text-right">Sessions</th><th className="text-right">Delivered Y</th><th className="text-right">Partly P</th><th className="text-right">Not delivered N</th><th className="text-right">Minutes over / under</th><th className="text-right">Carried over</th><th className="text-right">Found hardest</th></tr></thead>
              <tbody>{d.topics.map((t) => (
                <tr key={t.topic}><td className="font-medium">{t.topic}</td><td className="text-right">{t.day ?? ""}</td><td className="text-right">{t.planned}</td><td className="text-right">{t.delivered}</td><td className={clsx("text-right", t.partly && "text-amber-700")}>{t.partly}</td><td className={clsx("text-right", t.not_delivered && "font-semibold text-red-700")}>{t.not_delivered}</td><td className="text-right">{delta(t.minutes_delta)}</td><td className={clsx("text-right", t.carried_over && "text-amber-700")}>{t.carried_over}</td><td className={clsx("text-right", t.hardest && "font-semibold text-red-700")}>{t.hardest}</td></tr>
              ))}</tbody>
            </table></div>
          )}
        </Card>
      )}

      {tab === "reports" && (
        <Card title="Every daily report · click a row for all its details">
          {d.latest.length === 0 ? <Empty text="No report matches" /> : (
            <div className="overflow-x-auto">
              <table className="table">
                <thead><tr><th>Date</th><th>Day</th><th>Class / hall</th><th>District</th><th>Lead facilitator</th><th>Sessions Y / P / N</th><th className="text-right">Min ±</th><th className="text-right">Quiz pass</th><th>Quality C · E · T · I</th><th className="text-right">Overall</th><th className="text-right">Issues</th><th className="text-right">Escalations</th>{can("me_daily.manage") && <th />}</tr></thead>
                <tbody>
                  {d.latest.map((x) => (
                    <Fragment key={x.id}>
                      <tr className="cursor-pointer hover:bg-slate-50" onClick={() => setOpen(open === x.id ? null : x.id)}>
                        <td className="whitespace-nowrap">{fmtDate(x.report_date)}</td><td>{x.training_day}</td><td className="font-medium">{x.class_hall}</td><td>{x.district ?? "National / HQ"}</td><td>{x.lead_facilitator}</td>
                        <td className="whitespace-nowrap"><span className="text-emerald-700">{x.sessions_delivered}</span> / <span className="text-amber-700">{x.sessions_partly}</span> / <span className="text-red-700">{x.sessions_not}</span></td>
                        <td className="text-right">{delta(x.minutes_delta)}</td>
                        <td className="text-right">{x.quiz_administered ? pct(x.pass_rate) : <span className="text-slate-400">n/a</span>}</td>
                        <td><span className="flex gap-1">{[x.q_content, x.q_engagement, x.q_time, x.q_illustrations].map((s, i) => <span key={i} className="inline-block h-5 w-5 rounded text-center text-xs font-bold leading-5 text-white" style={{ background: SCORE_COLOR[String(s)] }}>{s}</span>)}</span></td>
                        <td className={clsx("text-right font-semibold", x.overall < 3 ? "text-red-700" : x.overall < 4 ? "text-amber-700" : "text-emerald-700")}>{x.overall.toFixed(2)}</td>
                        <td className="text-right">{x.material_issues.length}</td>
                        <td className={clsx("text-right", x.open_escalations && "font-semibold text-amber-700")}>{x.open_escalations} / {x.escalations.length}</td>
                        {can("me_daily.manage") && <td className="whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
                          <button className="text-navy" title="Edit" onClick={() => setEdit(x)}><Pencil size={14} /></button>
                          <button className="ml-2 text-red-700" title="Delete" onClick={() => { if (confirm(`Delete the report for ${x.class_hall}, day ${x.training_day}, ${fmtDate(x.report_date)}?`)) remove.mutate(x); }}><Trash2 size={14} /></button>
                        </td>}
                      </tr>
                      {open === x.id && <tr><td colSpan={13} className="bg-slate-50"><ReportDetail x={x} canManage={can("me_daily.manage")} onStatus={(index, status) => setStatus.mutate({ report_id: x.id, index, status })} /></td></tr>}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}

      {tab === "issues" && (
        <div className="grid gap-4">
          <LogCard title={`Materials and assessment issues log (${d.issues_log.length})`} rows={d.issues_log} columns={[["item", "Item (manual chapter, quiz, questionnaire ref.)"], ["type", "Type"], ["severity", "Severity"], ["correction", "Proposed correction"]]} highlight={(l) => l.fields.severity === "High"} />
          <LogCard title={`Content carried to the next day (${d.carried_over_log.length})`} rows={d.carried_over_log} columns={[["topic", "Topic"]]} />
          <LogCard title={`Quality evidence · scores of 1, 2 or 5 (${d.evidence_log.length})`} rows={d.evidence_log} columns={[["criterion", "Criterion"], ["score", "Score"], ["evidence", "Evidence / justification"]]} highlight={(l) => Number(l.fields.score) <= 2} />
        </div>
      )}

      {tab === "escalations" && (
        <Card title={`Escalations and decisions needed (${d.escalations_log.length})`}>
          {d.escalations_log.length === 0 ? <Empty text="Nothing raised to management / CCIT" /> : (
            <div className="overflow-x-auto"><table className="table">
              <thead><tr><th>Date</th><th>Day</th><th>Class / hall</th><th>District</th><th>Lead facilitator</th><th>Issue requiring management / CCIT action</th><th>Raised to</th><th>Proposed owner</th><th>Needed by</th><th>Status</th></tr></thead>
              <tbody>{d.escalations_log.map((l, i) => (
                <tr key={i}>
                  <td className="whitespace-nowrap">{fmtDate(l.report_date)}</td><td>{l.training_day}</td><td>{l.class_hall}</td><td>{l.district ?? ""}</td><td>{l.lead_facilitator}</td><td>{l.fields.issue}</td><td>{l.fields.raised_to}</td><td>{l.fields.owner}</td><td>{l.fields.needed_by}</td>
                  <td>{can("me_daily.manage") ? (
                    <select className={clsx("rounded-md border-0 px-2 py-1 text-xs font-semibold", STATUS[(l.fields.status as keyof typeof STATUS) ?? "OPEN"])} value={l.fields.status ?? "OPEN"} onChange={(e) => setStatus.mutate({ report_id: l.report_id, index: Number(l.fields.index), status: e.target.value })}>
                      <option value="OPEN">Open</option><option value="IN_PROGRESS">In progress</option><option value="RESOLVED">Resolved</option>
                    </select>
                  ) : <span className={clsx("rounded-full px-2 py-0.5 text-xs font-semibold", STATUS[(l.fields.status as keyof typeof STATUS) ?? "OPEN"])}>{l.fields.status_label}</span>}</td>
                </tr>
              ))}</tbody>
            </table></div>
          )}
        </Card>
      )}

      {qr && <QrDialog url={dailyLink(r)} title={r.title} subtitle="Daily Facilitator Report · one report per class each day" onClose={() => setQr(false)} />}
      {edit && spec.data && <EditDialog roundId={Number(id)} report={edit} spec={spec.data} agenda={agenda.data ?? []} onClose={() => setEdit(null)} onSaved={() => { setEdit(null); invalidate(); }} />}
    </div>
  );
}

function CountList({ title, rows }: { title: string; rows: MeDailyCount[] }) {
  return (
    <div className="mt-3">
      <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</div>
      {rows.length === 0 ? <p className="text-xs text-slate-400">None named yet</p> : <ul className="text-sm">{rows.slice(0, 8).map((x) => <li key={x.code} className="flex justify-between border-t border-slate-100 py-1"><span>{x.label}</span><span className="font-semibold">{x.count} <span className="font-normal text-slate-400">({x.pct}% of reports)</span></span></li>)}</ul>}
    </div>
  );
}

function CountCard({ title, rows, color, byScore }: { title: string; rows: MeDailyCount[]; color: string; byScore?: boolean }) {
  const data = rows;
  return (
    <Card title={title}>
      {data.every((x) => x.count === 0) ? <Empty text="Nothing reported" /> : (
        <div style={{ height: 40 + 30 * data.length }}>
          <ResponsiveContainer>
            <BarChart data={data} layout="vertical" margin={{ left: 10, right: 50 }}>
              <XAxis type="number" allowDecimals={false} hide /><YAxis type="category" dataKey="label" width={190} tick={{ fontSize: 12 }} />
              <Tooltip formatter={(v: number, _n, p) => [`${v} · ${(p.payload as MeDailyCount).pct}%`, ""]} />
              <Bar dataKey="count" radius={[0, 4, 4, 0]} isAnimationActive={false} label={{ position: "right", fontSize: 12, formatter: (v: number) => (v ? v : "") }}>
                {data.map((x) => <Cell key={x.code} fill={byScore ? SCORE_COLOR[x.code] ?? color : x.code === "RESOLVED" || x.code === "L" ? C.green : x.code === "H" || x.code === "OPEN" ? C.red : color} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  );
}

function GroupTable({ rows, label }: { rows: MeDailyGroup[]; label: string }) {
  const score = (v: number | null) => <td className={clsx("text-right", v !== null && v < 3 && "font-semibold text-red-700", v !== null && v >= 3 && v < 4 && "text-amber-700")}>{num(v)}</td>;
  return (
    <Card title={`By ${label.toLowerCase()}`}>
      {rows.length === 0 ? <Empty text="No report matches" /> : (
        <div className="overflow-x-auto">
          <table className="table">
            <thead><tr><th>{label}</th><th className="text-right">Reports</th><th className="text-right">Sessions</th><th className="text-right">Delivered</th><th className="text-right">Min ±</th><th className="text-right">Carried over</th><th className="text-right">Quizzes</th><th className="text-right">Mean score</th><th className="text-right">Pass rate</th><th className="text-right">Practice min</th><th className="text-right">Content</th><th className="text-right">Engagement</th><th className="text-right">Time</th><th className="text-right">Illustrations</th><th className="text-right">Overall</th><th className="text-right">Scores 1–2</th><th className="text-right">Issues (H)</th><th className="text-right">Internet</th><th className="text-right">Power</th><th className="text-right">Devices short</th><th className="text-right">Food</th><th className="text-right">Escalations (open)</th></tr></thead>
            <tbody>
              {rows.map((g) => (
                <tr key={g.key}>
                  <td className="font-medium">{g.label}</td><td className="text-right">{g.reports}</td><td className="text-right">{g.sessions}</td>
                  <td className={clsx("text-right", g.delivered_pct !== null && g.delivered_pct < 80 && "text-amber-700")}>{g.delivered} <span className="text-slate-400">({pct(g.delivered_pct)})</span></td>
                  <td className="text-right">{delta(g.minutes_delta)}</td><td className="text-right">{g.carried_over}</td><td className="text-right">{g.quizzes}</td><td className="text-right">{pct(g.mean_score)}</td>
                  <td className={clsx("text-right", g.pass_rate !== null && g.pass_rate < 70 && "font-semibold text-red-700")}>{pct(g.pass_rate)}</td><td className="text-right">{g.practice_minutes_avg ?? "—"}</td>
                  {score(g.q_content)}{score(g.q_engagement)}{score(g.q_time)}{score(g.q_illustrations)}{score(g.overall)}
                  <td className={clsx("text-right", g.low_scores && "font-semibold text-red-700")}>{g.low_scores}</td>
                  <td className="text-right">{g.material_issues} <span className={clsx("text-slate-400", g.high_severity && "font-semibold text-red-700")}>({g.high_severity})</span></td>
                  {score(g.internet)}{score(g.power)}<td className={clsx("text-right", g.devices_short && "text-amber-700")}>{g.devices_short}</td>{score(g.food)}
                  <td className={clsx("text-right", g.open_escalations && "font-semibold text-amber-700")}>{g.escalations} ({g.open_escalations})</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function LogCard({ title, rows, columns, highlight }: { title: string; rows: MeDailyLog[]; columns: [string, string][]; highlight?: (l: MeDailyLog) => boolean }) {
  return (
    <Card title={title}>
      {rows.length === 0 ? <Empty text="None recorded" /> : (
        <div className="overflow-x-auto"><table className="table">
          <thead><tr><th>Date</th><th>Day</th><th>Class / hall</th><th>District</th><th>Lead facilitator</th>{columns.map(([k, label]) => <th key={k}>{label}</th>)}</tr></thead>
          <tbody>{rows.map((l, i) => <tr key={i} className={highlight?.(l) ? "bg-red-50" : ""}><td className="whitespace-nowrap">{fmtDate(l.report_date)}</td><td>{l.training_day}</td><td>{l.class_hall}</td><td>{l.district ?? ""}</td><td>{l.lead_facilitator}</td>{columns.map(([k]) => <td key={k}>{l.fields[k] ?? ""}</td>)}</tr>)}</tbody>
        </table></div>
      )}
    </Card>
  );
}

function ReportDetail({ x, canManage, onStatus }: { x: MeDailyReport; canManage: boolean; onStatus: (index: number, status: string) => void }) {
  const row = (label: string, value: React.ReactNode) => <div className="grid grid-cols-[220px_1fr] gap-2 py-1 text-sm"><span className="text-slate-500">{label}</span><span>{value}</span></div>;
  const h = (t: string) => <h3 className="mb-1 mt-3 text-xs font-bold uppercase tracking-wide text-slate-500">{t}</h3>;
  const score = (s: number, ev: string | null) => <span><span className="inline-block h-6 w-6 rounded text-center text-xs font-bold leading-6 text-white" style={{ background: SCORE_COLOR[String(s)] }}>{s}</span>{ev ? <span className="ml-2 text-slate-600">{ev}</span> : null}</span>;
  return (
    <div className="grid gap-4 p-3 lg:grid-cols-2">
      <div>
        <h3 className="mb-1 text-xs font-bold uppercase tracking-wide text-slate-500">A · Identification</h3>
        {row("Phase · platform / venue", `${x.phase_label} · ${x.platform_venue}`)}
        {row("Class / hall · day · date", `${x.class_hall} · day ${x.training_day} · ${fmtDate(x.report_date)}`)}
        {row("Lead facilitator · co-facilitators", `${x.lead_facilitator}${x.co_facilitators ? ` · ${x.co_facilitators}` : ""}`)}
        {row("District", x.district ?? "National / HQ")}
        {h("C · Schedule and content coverage")}
        <table className="table text-xs"><thead><tr><th>Session / topic</th><th>Planned</th><th>Actual</th><th>Delivered</th><th className="text-right">Min ±</th><th>Reason</th></tr></thead>
          <tbody>{x.sessions.map((s, i) => <tr key={i}><td>{s.topic}</td><td className="whitespace-nowrap">{s.planned_start ?? ""}–{s.planned_end ?? ""}</td><td className="whitespace-nowrap">{s.actual_start ?? ""}–{s.actual_end ?? ""}</td><td className={clsx("font-bold", s.delivered === "Y" ? "text-emerald-700" : s.delivered === "P" ? "text-amber-700" : "text-red-700")}>{s.delivered}</td><td className="text-right">{delta(s.delta)}</td><td>{s.reason ?? ""}</td></tr>)}</tbody></table>
        {row("Content carried to next day", x.carried_over.length ? x.carried_over.join("; ") : "None")}
        {h("D · Participant performance and learning")}
        {row("Quiz / assessment", x.quiz_administered ? `Y · ${x.quiz_title ?? ""} · mean ${pct(x.mean_score)} · pass ${pct(x.pass_rate)}${x.quiz_comments ? ` · ${x.quiz_comments}` : ""}` : "N")}
        {row("Practical / CAPI hands-on", `${x.practice_minutes ?? "N/A"} minutes${x.practice_comments ? ` · ${x.practice_comments}` : ""}`)}
        {row("Hardest topics", `${x.hardest_topics.length ? x.hardest_topics.join("; ") : "None"}${x.hardest_comments ? ` · ${x.hardest_comments}` : ""}`)}
      </div>
      <div>
        <h3 className="mb-1 text-xs font-bold uppercase tracking-wide text-slate-500">E · Facilitation quality</h3>
        {row("Content accuracy and clarity", score(x.q_content, x.q_content_evidence))}
        {row("Participant engagement", score(x.q_engagement, x.q_engagement_evidence))}
        {row("Time management", score(x.q_time, x.q_time_evidence))}
        {row("Illustrations and practice", score(x.q_illustrations, x.q_illustrations_evidence))}
        {row("Overall class rating", <b>{x.overall.toFixed(2)}</b>)}
        {h("F · Materials and assessment issues")}
        {x.material_issues.length === 0 ? row("Issues", "None") : x.material_issues.map((m, i) => <div key={i} className="mb-1 rounded-md border border-slate-200 bg-white p-2 text-sm"><b>{i + 1}.</b> {m.item} · {m.type} · severity {m.severity}{m.correction ? <div className="text-slate-600">Correction: {m.correction}</div> : null}</div>)}
        {h("G · Connectivity, power and logistics")}
        {row("Internet connectivity", score(x.g_internet, x.g_internet_details))}
        {row("Power supply", score(x.g_power, x.g_power_details))}
        {row("Device shortages", `${x.g_devices} short${x.g_devices_details ? ` · ${x.g_devices_details}` : ""}`)}
        {row("Food & beverages", score(x.g_food, x.g_food_details))}
        {h("H · Escalations and decisions needed")}
        {x.escalations.length === 0 ? row("Escalations", "None") : x.escalations.map((e, i) => (
          <div key={i} className="mb-1 rounded-md border border-slate-200 bg-white p-2 text-sm">
            <div><b>{i + 1}.</b> {e.issue}</div>
            <div className="text-slate-600">Raised to {e.raised_to ?? "—"} · owner {e.owner ?? "—"} · needed by {e.needed_by ?? "—"}</div>
            {canManage ? <select className={clsx("mt-1 rounded-md border-0 px-2 py-1 text-xs font-semibold", STATUS[e.status ?? "OPEN"])} value={e.status ?? "OPEN"} onChange={(ev) => onStatus(i, ev.target.value)}><option value="OPEN">Open</option><option value="IN_PROGRESS">In progress</option><option value="RESOLVED">Resolved</option></select>
              : <span className={clsx("rounded-full px-2 py-0.5 text-xs font-semibold", STATUS[e.status ?? "OPEN"])}>{e.status}</span>}
          </div>
        ))}
        {h("Record")}
        {row("Submitted", fmt(x.submitted_at))}
        {x.edited_by_name && row("Last edited", `${fmt(x.updated_at)} by ${x.edited_by_name}`)}
      </div>
    </div>
  );
}

function fromReport(x: MeDailyReport): DailyValues {
  const s = (v: number | null | undefined) => (v === null || v === undefined ? "" : String(v));
  return {
    phase: x.phase, platform_venue: x.platform_venue, class_hall: x.class_hall, training_day: String(x.training_day), report_date: x.report_date, lead_facilitator: x.lead_facilitator, co_facilitators: x.co_facilitators ?? "", district: x.district ?? "",
    sessions: x.sessions.map((ss) => ({ topic: ss.topic, planned_start: ss.planned_start ?? "", planned_end: ss.planned_end ?? "", actual_start: ss.actual_start ?? "", actual_end: ss.actual_end ?? "", delivered: ss.delivered ?? "", reason: ss.reason ?? "" })),
    carried_over: x.carried_over,
    quiz_administered: x.quiz_administered ? "yes" : "no", quiz_title: x.quiz_title ?? "", mean_score: s(x.mean_score), pass_rate: s(x.pass_rate), quiz_comments: x.quiz_comments ?? "",
    practice_minutes: s(x.practice_minutes), practice_comments: x.practice_comments ?? "", hardest_topics: x.hardest_topics, hardest_comments: x.hardest_comments ?? "",
    q_content: s(x.q_content), q_content_evidence: x.q_content_evidence ?? "", q_engagement: s(x.q_engagement), q_engagement_evidence: x.q_engagement_evidence ?? "", q_time: s(x.q_time), q_time_evidence: x.q_time_evidence ?? "", q_illustrations: s(x.q_illustrations), q_illustrations_evidence: x.q_illustrations_evidence ?? "",
    material_issues: x.material_issues.map((m) => ({ item: m.item, type: m.type ?? "", severity: m.severity ?? "", correction: m.correction ?? "" })),
    g_internet: s(x.g_internet), g_internet_details: x.g_internet_details ?? "", g_power: s(x.g_power), g_power_details: x.g_power_details ?? "", g_devices: s(x.g_devices), g_devices_details: x.g_devices_details ?? "", g_food: s(x.g_food), g_food_details: x.g_food_details ?? "",
    escalations: x.escalations.map((e) => ({ issue: e.issue, raised_to: e.raised_to ?? "", owner: e.owner ?? "", needed_by: e.needed_by ?? "", status: e.status ?? "OPEN" })),
  };
}

function EditDialog({ roundId, report, spec, agenda, onClose, onSaved }: { roundId: number; report: MeDailyReport; spec: DailySpec; agenda: MeDailyAgendaItem[]; onClose: () => void; onSaved: () => void }) {
  const [values, setValues] = useState<DailyValues>(() => fromReport(report));
  const [serverErrors, setServerErrors] = useState<string[]>([]);
  const errors = validate(values, spec);
  const save = useMutation({
    mutationFn: () => api.put(`/me/daily/rounds/${roundId}/reports/${report.id}`, toPayload(values)),
    onSuccess: onSaved,
    onError: (err) => {
      const detail = err instanceof ApiError ? (err.body as { detail?: { errors?: string[] } } | undefined)?.detail : undefined;
      setServerErrors(detail && typeof detail === "object" && Array.isArray(detail.errors) ? detail.errors : [err instanceof ApiError ? err.message : String(err)]);
    },
  });
  return (
    <div className="fixed inset-0 z-40 flex items-start justify-center overflow-y-auto bg-black/40 p-4" onClick={onClose}>
      <div className="w-full max-w-4xl rounded-lg bg-white p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="mb-3 flex items-center justify-between"><h2 className="text-lg font-semibold">Edit report · {report.class_hall}, day {report.training_day}</h2><button className="btn-outline" onClick={onClose}>Close</button></div>
        {serverErrors.length > 0 && <div className="mb-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800"><ul className="list-disc pl-5">{serverErrors.map((x) => <li key={x}>{x}</li>)}</ul></div>}
        <DailyReportForm spec={spec} agenda={agenda} values={values} onChange={setValues} onSubmit={() => { if (!errors.length) save.mutate(); }} busy={save.isPending} submitLabel="Save changes" errors={errors} compact />
      </div>
    </div>
  );
}
