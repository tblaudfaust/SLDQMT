import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Fragment, useState } from "react";
import { Link, useParams } from "react-router-dom";
import clsx from "clsx";
import { Bar, BarChart, CartesianGrid, Cell, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Copy, Download, ExternalLink, Pencil, QrCode, Trash2 } from "lucide-react";
import { ApiError, api, download, fmt, fmtDate, qs } from "../../api/client";
import type { MeDailyCount, MeDailyGroup, MeDailyReport, MeDailySummary } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { Card, Empty, ErrorBox, KpiTile, Spinner } from "../../components/ui";
import QrDialog from "../../components/QrDialog";
import { DailyReportForm, toPayload, validate, type DailySpec, type DailyValues } from "../public/DailyReportForm";
import { PHASE_LABEL, dailyLink } from "./MeDailyPage";

const C = { navy: "#1F4E79", green: "#15803d", amber: "#d97706", red: "#b91c1c", sky: "#38bdf8", slate: "#94a3b8" };
const RATING = { GOOD: { label: "Good", cls: "bg-emerald-100 text-emerald-800", color: C.green }, SOME: { label: "Some gaps", cls: "bg-amber-100 text-amber-800", color: C.amber }, MAJOR: { label: "Major gaps", cls: "bg-red-100 text-red-800", color: C.red } };
const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${v}%`);
type Tab = "overview" | "day" | "class" | "district" | "trainer" | "reports" | "actions";

/** One training's daily reports: every detail, grouped by day, class, district and trainer, with the issues and actions. */
export default function MeDailyResultsPage() {
  const { id } = useParams();
  const { can } = useAuth();
  const qc = useQueryClient();
  const [f, setF] = useState({ district: "", class_hall: "", trainer: "", phase: "", date_from: "", date_to: "" });
  const query = qs(f);
  const res = useQuery({ queryKey: ["me-daily", "summary", id, query], queryFn: () => api.get<MeDailySummary>(`/me/daily/rounds/${id}/summary${query}`) });
  const all = useQuery({ queryKey: ["me-daily", "summary", id, "all"], queryFn: () => api.get<MeDailySummary>(`/me/daily/rounds/${id}/summary`) });
  const spec = useQuery({ queryKey: ["me-daily", "form"], queryFn: () => api.get<DailySpec>("/me/daily/form") });
  const [tab, setTab] = useState<Tab>("overview");
  const [open, setOpen] = useState<number | null>(null);
  const [edit, setEdit] = useState<MeDailyReport | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [qr, setQr] = useState(false);
  const invalidate = () => qc.invalidateQueries({ queryKey: ["me-daily"] });
  const remove = useMutation({ mutationFn: (r: MeDailyReport) => api.delete(`/me/daily/rounds/${id}/reports/${r.id}`), onSuccess: invalidate, onError: setError });
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
  const dayRows = d.by_day.map((g) => ({ name: g.label, Expected: g.expected, Present: g.present, Late: g.late, pass: g.pass_rate, att: g.attendance_rate }));
  const deliveryRows = (["content", "participation", "time"] as const).map((k) => ({ name: { content: "Content accuracy and clarity", participation: "Participation and use of practice", time: "Time management" }[k], Good: d.delivery[k][0].count, "Some gaps": d.delivery[k][1].count, "Major gaps": d.delivery[k][2].count }));

  return (
    <div className="max-w-6xl">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link to="/me/daily" className="text-sm text-navy">← Daily Evaluation</Link>
          <h1 className="text-2xl font-bold">{r.title}</h1>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
            <span className="rounded-full bg-violet-100 px-2 py-0.5 font-semibold text-violet-800">{PHASE_LABEL[r.phase] ?? r.phase}</span>
            <span className={clsx("rounded-full px-2 py-0.5 font-semibold", r.status === "OPEN" ? "bg-green-100 text-green-800" : "bg-slate-200 text-slate-700")}>{r.status === "OPEN" ? "Open" : "Closed"}</span>
            {(r.period_start || r.period_end) && <span className="text-slate-500">{fmtDate(r.period_start)}{r.period_end ? ` – ${fmtDate(r.period_end)}` : ""}</span>}
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
          <select className="input" value={f.trainer} onChange={(e) => setF({ ...f, trainer: e.target.value })}><option value="">All lead trainers</option>{lists.by_trainer.map((g) => <option key={g.key} value={g.label}>{g.label} ({g.reports})</option>)}</select>
          <select className="input" value={f.phase} onChange={(e) => setF({ ...f, phase: e.target.value })}><option value="">All phases</option>{lists.by_phase.map((g) => <option key={g.key} value={g.key}>{g.label} ({g.reports})</option>)}</select>
          <input className="input" type="date" value={f.date_from} onChange={(e) => setF({ ...f, date_from: e.target.value })} title="From date" />
          <input className="input" type="date" value={f.date_to} onChange={(e) => setF({ ...f, date_to: e.target.value })} title="To date" />
        </div>
        {filtered && <div className="mt-2 text-xs text-sky-900">Every figure and export on this page follows these filters. <button className="font-semibold underline" onClick={() => setF({ district: "", class_hall: "", trainer: "", phase: "", date_from: "", date_to: "" })}>Clear</button></div>}
      </Card>

      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
        <KpiTile label="Daily reports" value={d.reports} sub={`${d.classes} classes · ${d.days} days · ${d.trainers} trainers`} />
        <KpiTile label="Attendance" value={pct(d.attendance_rate)} tone={d.attendance_rate !== null && d.attendance_rate < 90 ? "amber" : "green"} sub={`${d.present} of ${d.expected} expected`} />
        <KpiTile label="Arrived late" value={pct(d.late_rate)} sub={`${d.late} trainees`} />
        <KpiTile label="Agenda completed" value={pct(d.agenda_all_pct)} tone={d.agenda_all_pct !== null && d.agenda_all_pct < 80 ? "amber" : "navy"} sub="reports with all topics done" />
        <KpiTile label="Learning pass rate" value={pct(d.pass_rate)} tone={d.pass_rate !== null && d.pass_rate < 70 ? "red" : "green"} sub={`${d.met} of ${d.checked} checked · ${d.assessed} reports assessed`} />
        <KpiTile label="Needing follow-up" value={d.followup} tone={d.followup ? "amber" : "navy"} sub={`${d.followup_not_assessed} reports not assessed`} />
        <KpiTile label="Major gaps" value={d.reports_with_major_gaps} tone={d.reports_with_major_gaps ? "red" : "navy"} sub="reports with a Major gaps rating" />
        <KpiTile label="Help requested" value={d.help_requests} tone={d.help_requests ? "amber" : "navy"} sub={`${d.actions_total} priority actions`} />
      </div>

      <div className="mb-4 flex flex-wrap gap-1 border-b border-slate-200">
        {([["overview", "Overview"], ["day", "By day"], ["class", "By class"], ["district", "By district"], ["trainer", "By trainer"], ["reports", `Reports (${d.reports})`], ["actions", `Actions & issues (${d.actions_total + d.incomplete_topics.length + d.learning_gaps.length})`]] as [Tab, string][]).map(([t, label]) => (
          <button key={t} onClick={() => setTab(t)} className={clsx("-mb-px border-b-2 px-3 py-2 text-sm font-medium", tab === t ? "border-navy text-navy" : "border-transparent text-slate-500 hover:text-slate-700")}>{label}</button>
        ))}
      </div>

      {tab === "overview" && (d.reports === 0 ? <Card><Empty text="No daily report yet. Share the link with the lead trainers." /></Card> : (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card title="Attendance by training day" className="lg:col-span-2">
            <div style={{ height: 260 }}>
              <ResponsiveContainer>
                <BarChart data={dayRows} margin={{ left: 0, right: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} /><YAxis tick={{ fontSize: 12 }} />
                  <Tooltip formatter={(v: number, name: string, p) => [v, name === "Present" ? `Present (${pct((p.payload as { att: number | null }).att)})` : name]} />
                  <Legend />
                  <Bar dataKey="Expected" fill={C.slate} isAnimationActive={false} />
                  <Bar dataKey="Present" fill={C.navy} isAnimationActive={false} />
                  <Bar dataKey="Late" fill={C.amber} isAnimationActive={false} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
          <Card title="Delivery and support · ratings per area">
            <div style={{ height: 200 }}>
              <ResponsiveContainer>
                <BarChart data={deliveryRows} layout="vertical" margin={{ left: 10, right: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" allowDecimals={false} /><YAxis type="category" dataKey="name" width={200} tick={{ fontSize: 12 }} />
                  <Tooltip /><Legend />
                  <Bar dataKey="Good" stackId="a" fill={C.green} isAnimationActive={false} />
                  <Bar dataKey="Some gaps" stackId="a" fill={C.amber} isAnimationActive={false} />
                  <Bar dataKey="Major gaps" stackId="a" fill={C.red} isAnimationActive={false} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
          <CountCard title="Support problems reported" rows={d.support} color={C.red} />
          <CountCard title="Agenda coverage" rows={d.coverage} color={C.navy} />
          <CountCard title="Learning check used" rows={d.checks} color={C.sky} />
          <Card title="Practical / CAPI practice">
            <div className="grid grid-cols-2 gap-3 text-center">
              <div className="rounded-md bg-slate-50 py-3"><div className="text-2xl font-bold text-navy">{d.practice_minutes_avg ?? "—"}</div><div className="text-xs text-slate-500">average minutes per class-day</div></div>
              <div className="rounded-md bg-slate-50 py-3"><div className="text-2xl font-bold text-amber-700">{d.practice_not_scheduled}</div><div className="text-xs text-slate-500">reports with no practice scheduled</div></div>
            </div>
          </Card>
          <Card title="Learning evidence">
            <div className="grid grid-cols-3 gap-3 text-center">
              <div className="rounded-md bg-slate-50 py-3"><div className="text-2xl font-bold text-navy">{d.checked}</div><div className="text-xs text-slate-500">trainees checked</div></div>
              <div className="rounded-md bg-slate-50 py-3"><div className="text-2xl font-bold text-green-700">{d.met}</div><div className="text-xs text-slate-500">met the criterion</div></div>
              <div className="rounded-md bg-slate-50 py-3"><div className="text-2xl font-bold text-amber-700">{d.followup}</div><div className="text-xs text-slate-500">need follow-up</div></div>
            </div>
            <p className="mt-2 text-xs text-slate-500">{d.assessed} of {d.reports} reports checked learning; {d.reports - d.assessed} ticked Not assessed.</p>
          </Card>
        </div>
      ))}

      {tab === "day" && <GroupTable rows={d.by_day} label="Training day" />}
      {tab === "class" && <GroupTable rows={d.by_class} label="Class / hall" />}
      {tab === "district" && <GroupTable rows={d.by_district} label="District" />}
      {tab === "trainer" && <GroupTable rows={d.by_trainer} label="Lead trainer" />}

      {tab === "reports" && (
        <Card title="Every daily report · click a row for all its details">
          {d.latest.length === 0 ? <Empty text="No report matches" /> : (
            <div className="overflow-x-auto">
              <table className="table">
                <thead><tr><th>Date</th><th>Day</th><th>Class / hall</th><th>District</th><th>Lead trainer</th><th className="text-right">Present / expected</th><th>Agenda</th><th className="text-right">Pass</th><th className="text-right">Follow-up</th><th>Delivery</th><th>Support</th><th>Help</th>{can("me_daily.manage") && <th />}</tr></thead>
                <tbody>
                  {d.latest.map((x) => (
                    <Fragment key={x.id}>
                      <tr className="cursor-pointer hover:bg-slate-50" onClick={() => setOpen(open === x.id ? null : x.id)}>
                        <td className="whitespace-nowrap">{fmtDate(x.report_date)}</td><td>{x.training_day}</td><td className="font-medium">{x.class_hall}</td><td>{x.district ?? "National / HQ"}</td><td>{x.lead_trainer}</td>
                        <td className="whitespace-nowrap text-right">{x.present} / {x.expected} <span className="text-slate-400">({pct(x.attendance_rate)})</span></td>
                        <td className={x.coverage === "ALL" ? "" : "text-amber-700"}>{x.coverage_label}</td>
                        <td className="text-right">{x.assessed ? pct(x.pass_rate) : <span className="text-slate-400">n/a</span>}</td>
                        <td className="text-right">{x.followup_not_assessed ? <span className="text-slate-400">n/a</span> : x.followup_count}</td>
                        <td><span className="flex gap-1">{(["delivery_content", "delivery_participation", "delivery_time"] as const).map((k) => <span key={k} title={k.replace("delivery_", "")} className={clsx("inline-block h-3 w-3 rounded-full", { GOOD: "bg-emerald-500", SOME: "bg-amber-500", MAJOR: "bg-red-600" }[x[k]])} />)}</span></td>
                        <td className={x.support.includes("NONE") ? "text-slate-400" : "text-red-700"}>{x.support_label}</td>
                        <td>{x.mgmt_help ? <span className="font-semibold text-amber-700">Yes</span> : "No"}</td>
                        {can("me_daily.manage") && <td className="whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
                          <button className="text-navy" title="Edit" onClick={() => setEdit(x)}><Pencil size={14} /></button>
                          <button className="ml-2 text-red-700" title="Delete" onClick={() => { if (confirm(`Delete the report for ${x.class_hall}, day ${x.training_day}, ${fmtDate(x.report_date)}?`)) remove.mutate(x); }}><Trash2 size={14} /></button>
                        </td>}
                      </tr>
                      {open === x.id && <tr><td colSpan={13} className="bg-slate-50"><ReportDetail x={x} /></td></tr>}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}

      {tab === "actions" && (
        <div className="grid gap-4">
          <Card title={`Priority actions (${d.actions.length})`}>
            {d.actions.length === 0 ? <Empty text="No priority action recorded" /> : (
              <div className="overflow-x-auto"><table className="table">
                <thead><tr><th>Date</th><th>Day</th><th>Class / hall</th><th>District</th><th>Lead trainer</th><th>Issue and impact</th><th>Next action</th><th>Owner and due time</th></tr></thead>
                <tbody>{d.actions.map((a, i) => <tr key={i}><td className="whitespace-nowrap">{fmtDate(a.report_date)}</td><td>{a.training_day}</td><td>{a.class_hall}</td><td>{a.district ?? ""}</td><td>{a.lead_trainer}</td><td>{a.issue}</td><td>{a.action}</td><td>{a.owner_due}</td></tr>)}</tbody>
              </table></div>
            )}
          </Card>
          <IssueCard title={`Management / CCIT help requested (${d.help_requested.length})`} rows={d.help_requested} column="Raised to" />
          <IssueCard title={`Incomplete agenda topics (${d.incomplete_topics.length})`} rows={d.incomplete_topics} column="Topic and reason" />
          <IssueCard title={`Learning gaps and common errors (${d.learning_gaps.length})`} rows={d.learning_gaps} column="Main learning gap or common error" />
        </div>
      )}

      {qr && <QrDialog url={dailyLink(r)} title={r.title} subtitle="Daily Trainer Class Evaluation · one form per class each day" onClose={() => setQr(false)} />}
      {edit && spec.data && (
        <EditDialog roundId={Number(id)} report={edit} spec={spec.data} onClose={() => setEdit(null)} onSaved={() => { setEdit(null); invalidate(); }} />
      )}
    </div>
  );
}

function CountCard({ title, rows, color }: { title: string; rows: MeDailyCount[]; color: string }) {
  const data = rows.filter((x) => x.count > 0 || rows.length <= 4);
  return (
    <Card title={title}>
      {data.length === 0 ? <Empty text="Nothing reported" /> : (
        <div style={{ height: 40 + 30 * data.length }}>
          <ResponsiveContainer>
            <BarChart data={data} layout="vertical" margin={{ left: 10, right: 50 }}>
              <XAxis type="number" allowDecimals={false} hide /><YAxis type="category" dataKey="label" width={170} tick={{ fontSize: 12 }} />
              <Tooltip formatter={(v: number, _n, p) => [`${v} report(s) · ${(p.payload as MeDailyCount).pct}%`, ""]} />
              <Bar dataKey="count" radius={[0, 4, 4, 0]} isAnimationActive={false} label={{ position: "right", fontSize: 12, formatter: (v: number) => (v ? v : "") }}>
                {data.map((x) => <Cell key={x.code} fill={x.code === "NONE" || x.code === "ALL" || x.code === "GOOD" ? C.green : color} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  );
}

function GroupTable({ rows, label }: { rows: MeDailyGroup[]; label: string }) {
  return (
    <Card title={`By ${label.toLowerCase()}`}>
      {rows.length === 0 ? <Empty text="No report matches" /> : (
        <div className="overflow-x-auto">
          <table className="table">
            <thead><tr><th>{label}</th><th className="text-right">Reports</th><th className="text-right">Expected</th><th className="text-right">Present</th><th className="text-right">Attendance</th><th className="text-right">Late</th><th className="text-right">Agenda all topics</th><th className="text-right">Assessed</th><th className="text-right">Checked</th><th className="text-right">Met</th><th className="text-right">Pass</th><th className="text-right">Follow-up</th><th className="text-right">Major gaps</th><th className="text-right">Support problems</th><th className="text-right">Help</th><th className="text-right">Practice min</th></tr></thead>
            <tbody>
              {rows.map((g) => (
                <tr key={g.key}>
                  <td className="font-medium">{g.label}</td><td className="text-right">{g.reports}</td><td className="text-right">{g.expected}</td><td className="text-right">{g.present}</td>
                  <td className={clsx("text-right", g.attendance_rate !== null && g.attendance_rate < 90 && "text-amber-700")}>{pct(g.attendance_rate)}</td>
                  <td className="text-right">{g.late}{g.late_rate !== null ? <span className="text-slate-400"> ({g.late_rate}%)</span> : null}</td>
                  <td className="text-right">{g.agenda_all} <span className="text-slate-400">({pct(g.agenda_all_pct)})</span></td>
                  <td className="text-right">{g.assessed}</td><td className="text-right">{g.checked}</td><td className="text-right">{g.met}</td>
                  <td className={clsx("text-right", g.pass_rate !== null && g.pass_rate < 70 && "font-semibold text-red-700")}>{pct(g.pass_rate)}</td>
                  <td className="text-right">{g.followup}</td>
                  <td className={clsx("text-right", g.major_gaps && "font-semibold text-red-700")}>{g.major_gaps}</td>
                  <td className="text-right">{g.support_problems}</td><td className={clsx("text-right", g.help_requests && "text-amber-700")}>{g.help_requests}</td>
                  <td className="text-right">{g.practice_minutes_avg ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function IssueCard({ title, rows, column }: { title: string; rows: { report_id: number; report_date: string; training_day: number; class_hall: string; district: string | null; lead_trainer: string; text: string }[]; column: string }) {
  return (
    <Card title={title}>
      {rows.length === 0 ? <Empty text="None recorded" /> : (
        <div className="overflow-x-auto"><table className="table">
          <thead><tr><th>Date</th><th>Day</th><th>Class / hall</th><th>District</th><th>Lead trainer</th><th>{column}</th></tr></thead>
          <tbody>{rows.map((x, i) => <tr key={i}><td className="whitespace-nowrap">{fmtDate(x.report_date)}</td><td>{x.training_day}</td><td>{x.class_hall}</td><td>{x.district ?? ""}</td><td>{x.lead_trainer}</td><td>{x.text}</td></tr>)}</tbody>
        </table></div>
      )}
    </Card>
  );
}

function ReportDetail({ x }: { x: MeDailyReport }) {
  const row = (label: string, value: React.ReactNode) => <div className="grid grid-cols-[220px_1fr] gap-2 py-1 text-sm"><span className="text-slate-500">{label}</span><span>{value}</span></div>;
  const rating = (v: "GOOD" | "SOME" | "MAJOR") => <span className={clsx("rounded-full px-2 py-0.5 text-xs font-semibold", RATING[v].cls)}>{RATING[v].label}</span>;
  return (
    <div className="grid gap-4 p-3 lg:grid-cols-2">
      <div>
        <h3 className="mb-1 text-xs font-bold uppercase tracking-wide text-slate-500">Class and day</h3>
        {row("Date · training day", `${fmtDate(x.report_date)} · day ${x.training_day}`)}
        {row("Class / hall · venue", `${x.class_hall}${x.venue ? ` · ${x.venue}` : ""}`)}
        {row("Lead trainer", x.lead_trainer)}
        {row("Phase · district", `${x.phase_label} · ${x.district ?? "National / HQ"}`)}
        <h3 className="mb-1 mt-3 text-xs font-bold uppercase tracking-wide text-slate-500">1 Attendance and delivery</h3>
        {row("Expected · present · late", `${x.expected} · ${x.present} (${pct(x.attendance_rate)}) · ${x.late} late`)}
        {row("Agenda coverage", x.coverage_label)}
        {x.incomplete_topic && row("Topic and reason", x.incomplete_topic)}
        {row("Practical / CAPI practice", x.practice_not_scheduled ? "Not scheduled" : `${x.practice_minutes ?? "—"} minutes`)}
        <h3 className="mb-1 mt-3 text-xs font-bold uppercase tracking-wide text-slate-500">2 Learning evidence</h3>
        {row("Check used", x.checks_label)}
        {x.assessed && row("Task / topic checked", x.task_checked)}
        {x.assessed && row("Checked · met criterion", `${x.number_checked} · ${x.number_met} (${pct(x.pass_rate)})`)}
        {x.assessed && row("Criterion used", x.criterion)}
        {row("Main learning gap", x.learning_gap ?? "None")}
        {row("Trainees needing follow-up", x.followup_not_assessed ? "Not assessed" : x.followup_count)}
      </div>
      <div>
        <h3 className="mb-1 text-xs font-bold uppercase tracking-wide text-slate-500">3 Delivery and support</h3>
        {row("Content accuracy and clarity", rating(x.delivery_content))}
        {row("Participation and use of practice", rating(x.delivery_participation))}
        {row("Time management", rating(x.delivery_time))}
        {row("Support problems", x.support_label + (x.support_other ? ` · ${x.support_other}` : ""))}
        <h3 className="mb-1 mt-3 text-xs font-bold uppercase tracking-wide text-slate-500">4 Priority actions</h3>
        {x.actions.length === 0 ? row("Actions", "None") : x.actions.map((a, i) => (
          <div key={i} className="mb-2 rounded-md border border-slate-200 bg-white p-2 text-sm">
            <div><span className="text-slate-500">Issue and impact:</span> {a.issue}</div>
            <div><span className="text-slate-500">Next action:</span> {a.action}</div>
            <div><span className="text-slate-500">Owner and due time:</span> {a.owner_due || "—"}</div>
          </div>
        ))}
        {row("Management / CCIT help", x.mgmt_help ? `Yes — raised to ${x.raised_to ?? "—"}` : "No")}
        <h3 className="mb-1 mt-3 text-xs font-bold uppercase tracking-wide text-slate-500">Record</h3>
        {row("Submitted", fmt(x.submitted_at))}
        {x.edited_by_name && row("Last edited", `${fmt(x.updated_at)} by ${x.edited_by_name}`)}
      </div>
    </div>
  );
}

function fromReport(x: MeDailyReport): DailyValues {
  const s = (v: number | null | undefined) => (v === null || v === undefined ? "" : String(v));
  const actions = [...x.actions, { issue: "", action: "", owner_due: "" }, { issue: "", action: "", owner_due: "" }].slice(0, 2);
  return {
    report_date: x.report_date, training_day: String(x.training_day), class_hall: x.class_hall, venue: x.venue ?? "", lead_trainer: x.lead_trainer, phase: x.phase, district: x.district ?? "",
    expected: s(x.expected), present: s(x.present), late: s(x.late), coverage: x.coverage, incomplete_topic: x.incomplete_topic ?? "", practice_minutes: s(x.practice_minutes), practice_not_scheduled: x.practice_not_scheduled,
    checks: x.checks, task_checked: x.task_checked ?? "", number_checked: s(x.number_checked), number_met: s(x.number_met), criterion: x.criterion ?? "", learning_gap: x.learning_gap ?? "", followup_count: s(x.followup_count), followup_not_assessed: x.followup_not_assessed,
    delivery_content: x.delivery_content, delivery_participation: x.delivery_participation, delivery_time: x.delivery_time, support: x.support, support_other: x.support_other ?? "",
    actions, mgmt_help: x.mgmt_help, raised_to: x.raised_to ?? "",
  };
}

function EditDialog({ roundId, report, spec, onClose, onSaved }: { roundId: number; report: MeDailyReport; spec: DailySpec; onClose: () => void; onSaved: () => void }) {
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
      <div className="w-full max-w-3xl rounded-lg bg-white p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="mb-3 flex items-center justify-between"><h2 className="text-lg font-semibold">Edit report · {report.class_hall}, day {report.training_day}</h2><button className="btn-outline" onClick={onClose}>Close</button></div>
        {serverErrors.length > 0 && <div className="mb-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800"><ul className="list-disc pl-5">{serverErrors.map((x) => <li key={x}>{x}</li>)}</ul></div>}
        <DailyReportForm spec={spec} values={values} onChange={setValues} onSubmit={() => { if (!errors.length) save.mutate(); }} busy={save.isPending} submitLabel="Save changes" errors={errors} compact />
      </div>
    </div>
  );
}
