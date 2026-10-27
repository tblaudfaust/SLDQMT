import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import clsx from "clsx";
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AlertTriangle, Copy, Download, ExternalLink, Pencil, QrCode, Trash2, X } from "lucide-react";
import { ApiError, api, download, fmtDate, qs } from "../../api/client";
import type { MeFacAgendaItem, MeFacReport, MeFacReportGroup, MeFacReportSpec, MeFacReportSummary } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { Empty, ErrorBox, Spinner } from "../../components/ui";
import QrDialog from "../../components/QrDialog";
import { Bars, CountCard, GREEN, NAVY, Panel, RED, Scorecard, SKY, status, statusBg } from "./kpi/kpiUi";
import { FacReportForm, SCALE_COLOR, fromReport, toPayload, validate, type Values } from "../public/FacReportPage";
import { PHASE_LABEL } from "./MeFacPage";

const DELIVERY_COLOR: Record<string, string> = { FULL: GREEN, PARTLY: "#d97706", NO: RED };
const num = (v: number | null | undefined, d = 1) => (v === null || v === undefined ? "—" : v.toFixed(d));
const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${Math.round(v)}%`);
const r5 = (v: number | null | undefined) => (v === null || v === undefined ? "none" : v >= 4 ? "good" : v >= 3 ? "warn" : "bad");
const emptyFilters = { venue: "", hall: "", training_day: "", date_from: "", date_to: "" };

/** Feedback dashboard of the Daily Facilitator's Report for one training: attendance, delivery, class ratings, logistics, what went right and wrong, recommendations and who should act; by venue, hall and day. */
export default function MeFacReportResultsPage() {
  const { id = "" } = useParams();
  const { can } = useAuth();
  const qc = useQueryClient();
  const [f, setF] = useState(emptyFilters);
  const query = qs(f);
  const sum = useQuery({ queryKey: ["me-facrep", "summary", id, query], queryFn: () => api.get<MeFacReportSummary>(`/me/facreports/rounds/${id}/summary${query}`) });
  const all = useQuery({ queryKey: ["me-facrep", "summary", id, ""], queryFn: () => api.get<MeFacReportSummary>(`/me/facreports/rounds/${id}/summary`) });
  const rows = useQuery({ queryKey: ["me-facrep", "reports", id, query], queryFn: () => api.get<MeFacReport[]>(`/me/facreports/rounds/${id}/reports${query}`) });
  const spec = useQuery({ queryKey: ["me-facrep", "form"], queryFn: () => api.get<MeFacReportSpec>("/me/facreports/form") });
  const agenda = useQuery({ queryKey: ["me-fac", "agenda", id], queryFn: () => api.get<MeFacAgendaItem[]>(`/me/facilitators/rounds/${id}/agenda`) });
  const [tab, setTab] = useState<"overview" | "venue" | "hall" | "day" | "feedback" | "reports">("overview");
  const [open, setOpen] = useState<MeFacReport | null>(null);
  const [edit, setEdit] = useState<{ report: MeFacReport; values: Values } | null>(null);
  const [touched, setTouched] = useState(false);
  const [qr, setQr] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const invalidate = () => qc.invalidateQueries({ queryKey: ["me-facrep"] });
  const save = useMutation({ mutationFn: (e: { report: MeFacReport; values: Values }) => api.put<MeFacReport>(`/me/facreports/rounds/${id}/reports/${e.report.id}`, toPayload(e.values)), onSuccess: (r) => { invalidate(); setEdit(null); setOpen(r); setError(null); }, onError: setError });
  const remove = useMutation({ mutationFn: (r: MeFacReport) => api.delete(`/me/facreports/rounds/${id}/reports/${r.id}`), onSuccess: () => { invalidate(); setOpen(null); }, onError: setError });
  const editErrors = useMemo(() => (edit && spec.data ? validate(edit.values, spec.data) : []), [edit, spec.data]);
  if (sum.isLoading) return <Spinner />;
  if (sum.error || !sum.data) return <ErrorBox error={sum.error} />;
  const d = sum.data;
  const lists = all.data ?? d;
  const r = d.round;
  const link = d.report_url ?? `${window.location.origin}/report/${r.token}`;
  const filtered = Object.values(f).some(Boolean);
  const exportFile = async (format: "xlsx" | "pdf") => { setError(null); try { await download(`/me/facreports/rounds/${id}/export${qs({ ...f, format })}`, `facilitator-report.${format}`); } catch (e) { setError(e); } };
  const data = rows.data ?? [];
  const venueRows = d.by_venue.map((g) => ({ name: g.label, "Class rating": g.mean_rating ?? 0, Attendance: g.attendance_pct ?? 0 }));
  const dayRows = d.by_day.map((g) => ({ name: g.label, "Class rating": g.mean_rating ?? 0, "Attendance %": g.attendance_pct ?? 0, "Delivered fully %": g.delivered_full_pct ?? 0 }));
  const critRows = d.criteria.map((c) => ({ name: c.label, mean: c.mean ?? 0 }));

  const GroupTable = ({ groups, first }: { groups: MeFacReportGroup[]; first: string }) => (
    <div className="overflow-x-auto">
      <table className="table text-sm">
        <thead><tr><th>{first}</th><th className="text-right">Reports</th><th className="text-right">Halls</th><th className="text-right">Registered</th><th className="text-right">Present</th><th className="text-right">Attendance</th><th className="text-right">Class rating</th>{d.criteria.map((c) => <th key={c.key} className="text-right" title={c.label}>{c.label.split(" ")[0] === "Participants'" ? c.label.split(" ").slice(1, 3).join(" ") : c.label.split(" ").slice(0, 2).join(" ")}</th>)}<th className="text-right">Delivered fully</th><th className="text-right">Min. lost</th><th className="text-right">Internet</th><th className="text-right">Power</th><th className="text-right">Attention</th></tr></thead>
        <tbody>
          {groups.map((g) => (
            <tr key={g.key} className={clsx(g.attention && "bg-amber-50/50")}>
              <td className="font-semibold">{g.label}<span className="block text-[11px] font-normal text-slate-400">{g.days} day{g.days === 1 ? "" : "s"}</span></td>
              <td className="text-right">{g.reports}</td><td className="text-right">{g.halls}</td><td className="text-right">{g.registered}</td><td className="text-right">{g.present}</td>
              <td className={clsx("text-right font-semibold", statusBg[status(g.attendance_pct, 90, 75)])}>{pct(g.attendance_pct)}</td>
              <td className={clsx("text-right font-semibold", statusBg[r5(g.mean_rating)])}>{num(g.mean_rating)}</td>
              {d.criteria.map((c) => <td key={c.key} className={clsx("text-right", statusBg[r5(g.ratings[c.key])])}>{num(g.ratings[c.key])}</td>)}
              <td className={clsx("text-right", statusBg[status(g.delivered_full_pct, 80, 50)])}>{pct(g.delivered_full_pct)}</td><td className="text-right">{g.minutes_lost || "·"}</td>
              <td className={clsx("text-right", statusBg[r5(g.internet)])}>{num(g.internet)}</td><td className={clsx("text-right", statusBg[r5(g.power)])}>{num(g.power)}</td>
              <td className={clsx("text-right", g.attention && "font-bold text-amber-800")}>{g.attention || "·"}</td>
            </tr>
          ))}
          {groups.length === 0 && <tr><td colSpan={16}><Empty /></td></tr>}
        </tbody>
      </table>
    </div>
  );

  const Detail = ({ x }: { x: MeFacReport }) => (
    <div className="space-y-4 text-sm">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {[["Attendance", `${x.present} / ${x.registered}`, pct(x.attendance_pct)], ["Delivered", x.delivered_label, x.minutes_lost ? `${x.minutes_lost} min lost` : ""], ["Class rating", `${x.mean_rating.toFixed(1)} / 5`, ""], ["Internet · power", `${x.e_internet ?? "—"} · ${x.e_power ?? "—"}`, "1 to 5"]].map(([l, v, s]) => <div key={l} className="rounded-md bg-slate-50 px-3 py-2"><div className="text-xs text-slate-500">{l}</div><div className="text-lg font-bold text-navy">{v}</div>{s && <div className="text-xs text-slate-500">{s}</div>}</div>)}
      </div>
      {x.reasons.length > 0 && <div className="flex flex-wrap gap-1">{x.reasons.map((s) => <span key={s} className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-900"><AlertTriangle size={11} className="mr-1 inline" />{s}</span>)}</div>}
      <div className="grid gap-1 sm:grid-cols-5">{d.criteria.map((c) => { const v = (x as unknown as Record<string, number>)[`r_${c.key}`]; return <div key={c.key} className="rounded-md border border-slate-200 px-2 py-1.5"><div className="text-[11px] text-slate-500">{c.label}</div><div className="text-base font-bold" style={{ color: SCALE_COLOR[String(v)] }}>{v}</div></div>; })}</div>
      {(x.missed_sessions.length > 0 || x.missed_reason) && <Block title="C · Sessions affected">{x.missed_sessions.length > 0 && <div className="mb-1 flex flex-wrap gap-1">{x.missed_sessions.map((s) => <span key={s} className="rounded-full bg-slate-100 px-2 py-0.5 text-xs">{s}</span>)}</div>}{x.missed_reason}</Block>}
      {(x.e_internet_details || x.e_power_details || x.e_devices || x.e_food) && <Block title="E · Connectivity, power and logistics"><dl className="grid gap-x-4 gap-y-1 sm:grid-cols-2">{[["Internet", x.e_internet_details], ["Power", x.e_power_details], ["Device shortages", [x.e_devices, x.e_devices_details].filter(Boolean).join(" · ")], ["Food & beverages", [x.e_food, x.e_food_details].filter(Boolean).join(" · ")]].filter(([, v]) => v).map(([l, v]) => <div key={l}><dt className="text-xs text-slate-500">{l}</dt><dd>{v}</dd></div>)}</dl></Block>}
      <Block title="F · What worked well">{x.went_right}{x.repeat_share && <p className="mt-1 text-slate-600"><b>To repeat / share:</b> {x.repeat_share}</p>}</Block>
      <Block title="G · What did not work well">{x.went_wrong}{(x.difficult_topics.length > 0 || x.difficult_notes) && <p className="mt-1 text-slate-600"><b>Needs reinforcement:</b> {[...x.difficult_topics, x.difficult_notes].filter(Boolean).join("; ")}</p>}</Block>
      <Block title="H · Recommendations">{x.recommendations}<p className="mt-1 text-slate-600"><b>Gaps / errors / aids:</b> {x.gaps}</p><p className="mt-1"><b>Who should act:</b> {x.actor_labels.join(", ")}{x.actor_other ? ` (${x.actor_other})` : ""}</p></Block>
      {x.comments && <Block title="I · Additional comments">{x.comments}</Block>}
      <div className="text-xs text-slate-500">Sent {new Date(x.submitted_at).toLocaleString("en-GB")}{x.email ? ` · ${x.email}` : ""}{x.phone ? ` · ${x.phone}` : ""}{x.edited_by_name ? ` · edited by ${x.edited_by_name}` : ""}</div>
    </div>
  );

  return (
    <div className="max-w-7xl">
      <div className="mb-4 rounded-2xl bg-gradient-to-r from-navy to-[#1b7f6b] p-5 text-white shadow">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <Link to="/me/facreports" className="text-sm font-bold text-sky-100 hover:underline">← Facilitator daily report</Link>
            <h1 className="text-2xl font-extrabold">{r.title}</h1>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
              <span className="rounded-full bg-white/15 px-2 py-0.5 font-semibold">{PHASE_LABEL[r.phase] ?? r.phase}</span>
              <span className={clsx("rounded-full px-2 py-0.5 font-semibold", r.status === "OPEN" ? "bg-emerald-400/30" : "bg-white/20")}>{r.status === "OPEN" ? "Open" : "Closed"}</span>
              {(r.period_start || r.period_end) && <span className="text-sky-100">{fmtDate(r.period_start)}{r.period_end ? ` – ${fmtDate(r.period_end)}` : ""}</span>}
              <span className="text-sky-100">{d.reports} reports · {d.halls} halls · {d.venues} venues · {d.days} days · {d.facilitators} lead facilitators</span>
            </div>
            <div className="mt-2 flex flex-wrap gap-3 text-xs">
              <button className="text-sky-100 hover:text-white" onClick={() => navigator.clipboard.writeText(link)}><Copy size={12} className="mr-1 inline" />Copy link</button>
              <a className="text-sky-100 hover:text-white" href={link} target="_blank" rel="noreferrer"><ExternalLink size={12} className="mr-1 inline" />Open the form</a>
              <button className="text-sky-100 hover:text-white" onClick={() => setQr(true)}><QrCode size={12} className="mr-1 inline" />QR code</button>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button className="rounded-lg bg-white px-3 py-2 text-sm font-semibold text-navy hover:bg-sky-50" onClick={() => exportFile("xlsx")}><Download size={15} className="mr-1 inline" />Excel</button>
            <button className="rounded-lg bg-white px-3 py-2 text-sm font-semibold text-navy hover:bg-sky-50" onClick={() => exportFile("pdf")}><Download size={15} className="mr-1 inline" />PDF</button>
          </div>
        </div>
        <div className="mt-4 grid gap-2 sm:grid-cols-3 lg:grid-cols-6">
          <select className="input text-slate-800" value={f.venue} onChange={(e) => setF({ ...f, venue: e.target.value, hall: "" })}><option value="">All venues</option>{lists.by_venue.map((g) => <option key={g.key} value={g.label}>{g.label} ({g.reports})</option>)}</select>
          <select className="input text-slate-800" value={f.hall} onChange={(e) => setF({ ...f, hall: e.target.value })}><option value="">All halls</option>{lists.by_hall.filter((g) => !f.venue || g.venue === f.venue).map((g) => <option key={g.key} value={g.hall ?? ""}>{g.label} ({g.reports})</option>)}</select>
          <select className="input text-slate-800" value={f.training_day} onChange={(e) => setF({ ...f, training_day: e.target.value })}><option value="">All days</option>{lists.by_day.map((g) => <option key={g.key} value={g.key}>{g.label} ({g.reports})</option>)}</select>
          <input className="input text-slate-800" type="date" value={f.date_from} onChange={(e) => setF({ ...f, date_from: e.target.value })} title="From" />
          <input className="input text-slate-800" type="date" value={f.date_to} onChange={(e) => setF({ ...f, date_to: e.target.value })} title="To" />
          <button className={clsx("rounded-lg px-3 py-2 text-sm font-semibold", filtered ? "bg-amber-400 text-amber-950" : "bg-white/10 text-sky-100")} onClick={() => setF(emptyFilters)} disabled={!filtered}>{filtered ? "Clear filters" : "No filter"}</button>
        </div>
      </div>
      <ErrorBox error={error instanceof ApiError ? error.message : error} />

      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-3 2xl:grid-cols-6">
        <Scorecard label="Attendance" value={pct(d.attendance_pct)} raw={d.attendance_pct} good={90} warn={75} help={`${d.present} present of ${d.registered} registered`} />
        <Scorecard label="Class rating" value={num(d.mean_rating)} raw={d.mean_rating === null ? null : d.mean_rating * 20} good={80} warn={60} help="Mean of the five ratings (1 to 5)" targetText="target ≥ 4 of 5" />
        <Scorecard label="Delivered as scheduled" value={pct(d.delivered[0]?.pct)} raw={d.delivered[0]?.pct ?? null} good={80} warn={50} help={`${d.delivered[1]?.count ?? 0} partly, ${d.delivered[2]?.count ?? 0} not delivered`} />
        <Scorecard label="Internet connectivity" value={num(d.internet)} raw={d.internet === null ? null : d.internet * 20} good={80} warn={60} help="Mean rating 1 to 5" targetText="target ≥ 4 of 5" />
        <Scorecard label="Power supply" value={num(d.power)} raw={d.power === null ? null : d.power * 20} good={80} warn={60} help="Mean rating 1 to 5" targetText="target ≥ 4 of 5" />
        <CountCard label="Need attention" value={d.attention} sub={`${d.low_ratings} report${d.low_ratings === 1 ? "" : "s"} with a 1 or 2 · ${d.minutes_lost} min lost`} tone={d.attention ? "amber" : "green"} icon={<AlertTriangle size={16} />} />
      </div>

      <div className="mb-4 flex flex-wrap gap-1 border-b border-slate-200">
        {([["overview", "Overview"], ["venue", `By venue (${d.by_venue.length})`], ["hall", `By hall (${d.by_hall.length})`], ["day", `By day (${d.by_day.length})`], ["feedback", "What went right / wrong"], ["reports", `Reports (${data.length})`]] as const).map(([t, l]) => (
          <button key={t} onClick={() => setTab(t)} className={clsx("-mb-px border-b-2 px-3 py-2 text-sm font-medium", tab === t ? "border-navy text-navy" : "border-transparent text-slate-500 hover:text-slate-800")}>{l}</button>
        ))}
      </div>

      {tab === "overview" && (d.reports === 0 ? <Panel title="No report yet"><Empty text="Share the link or QR code with the Lead Facilitators of the halls." /></Panel> : (
        <div className="grid gap-4 lg:grid-cols-2">
          <Panel title="Class ratings" subtitle="Mean of each criterion, 1 to 5, with the distribution">
            <ul className="space-y-3">
              {d.criteria.map((c) => (
                <li key={c.key}>
                  <div className="flex items-center justify-between text-sm"><span>{c.label}</span><span className="font-bold" style={{ color: SCALE_COLOR[String(Math.round(c.mean ?? 0))] ?? NAVY }}>{num(c.mean)}</span></div>
                  <div className="mt-1 flex h-3 overflow-hidden rounded-full bg-slate-100">{c.distribution.map((b) => b.count ? <div key={b.code} title={`${b.label}: ${b.count}`} style={{ width: `${b.pct ?? 0}%`, background: SCALE_COLOR[b.code] }} /> : null)}</div>
                </li>
              ))}
            </ul>
            <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-slate-500">{[5, 4, 3, 2, 1].map((v) => <span key={v}><i className="mr-1 inline-block h-2.5 w-2.5 rounded-sm align-middle" style={{ background: SCALE_COLOR[String(v)] }} />{v} {spec.data?.scale.find((s) => s.value === v)?.label}</span>)}</div>
          </Panel>
          <Panel title="Sessions delivered as scheduled" subtitle="Share of reports">
            <div className="flex items-center gap-4">
              <div style={{ width: 170, height: 170 }}>
                <ResponsiveContainer><PieChart><Pie data={d.delivered.filter((c) => c.count)} dataKey="count" nameKey="label" innerRadius={45} outerRadius={80} isAnimationActive={false}>{d.delivered.filter((c) => c.count).map((c) => <Cell key={c.code} fill={DELIVERY_COLOR[c.code]} />)}</Pie><Tooltip /></PieChart></ResponsiveContainer>
              </div>
              <ul className="flex-1 space-y-2 text-sm">{d.delivered.map((c) => <li key={c.code} className="flex items-center justify-between"><span><i className="mr-2 inline-block h-3 w-3 rounded-sm align-middle" style={{ background: DELIVERY_COLOR[c.code] }} />{c.label}</span><b>{c.count} <span className="font-normal text-slate-400">· {pct(c.pct)}</span></b></li>)}<li className="border-t border-slate-100 pt-2 text-xs text-slate-500">{d.minutes_lost} minutes lost in total</li></ul>
            </div>
          </Panel>
          <Panel title="Class rating and attendance by venue">
            <div style={{ height: 60 + 40 * Math.max(venueRows.length, 2) }}>
              <ResponsiveContainer><BarChart data={venueRows} layout="vertical" margin={{ left: 10, right: 20 }}><CartesianGrid strokeDasharray="3 3" horizontal={false} /><XAxis type="number" domain={[0, 100]} hide /><YAxis type="category" dataKey="name" width={90} tick={{ fontSize: 12 }} /><Tooltip /><Legend /><Bar dataKey="Attendance" fill={SKY} unit="%" isAnimationActive={false} radius={[0, 3, 3, 0]} /><Bar dataKey="Class rating" fill={NAVY} isAnimationActive={false} radius={[0, 3, 3, 0]} /></BarChart></ResponsiveContainer>
            </div>
            <p className="text-[11px] text-slate-400">Class rating on a 1 to 5 scale; attendance in percent.</p>
          </Panel>
          <Panel title="Day by day" subtitle="Attendance, delivery and class rating">
            {dayRows.length === 0 ? <Empty /> : (
              <div style={{ height: 240 }}>
                <ResponsiveContainer><LineChart data={dayRows} margin={{ left: 0, right: 10 }}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="name" tick={{ fontSize: 12 }} /><YAxis yAxisId="pct" domain={[0, 100]} unit="%" tick={{ fontSize: 12 }} /><YAxis yAxisId="r" orientation="right" domain={[1, 5]} tick={{ fontSize: 12 }} /><Tooltip /><Legend /><Line yAxisId="pct" type="monotone" dataKey="Attendance %" stroke={SKY} strokeWidth={2} isAnimationActive={false} /><Line yAxisId="pct" type="monotone" dataKey="Delivered fully %" stroke={GREEN} strokeWidth={2} isAnimationActive={false} /><Line yAxisId="r" type="monotone" dataKey="Class rating" stroke={NAVY} strokeWidth={3} dot={{ r: 4 }} isAnimationActive={false} /></LineChart></ResponsiveContainer>
              </div>
            )}
          </Panel>
          <Panel title="Who should act" subtitle="Section H · question 17"><Bars rows={d.actors} color={NAVY} /></Panel>
          <Panel title="Topics that need reinforcement" subtitle="Section G · question 15"><Bars rows={d.difficult_topics} color="#d97706" /></Panel>
          <Panel title="Sessions affected" subtitle="Section C · not delivered as scheduled"><Bars rows={d.missed_sessions} color={RED} /></Panel>
          <Panel title="Mean rating per criterion" subtitle="1 to 5">
            <div style={{ height: 210 }}>
              <ResponsiveContainer><BarChart data={critRows} layout="vertical" margin={{ left: 10, right: 30 }}><XAxis type="number" domain={[0, 5]} tick={{ fontSize: 12 }} /><YAxis type="category" dataKey="name" width={190} tick={{ fontSize: 11 }} /><Tooltip /><Bar dataKey="mean" isAnimationActive={false} radius={[0, 3, 3, 0]} label={{ position: "right", fontSize: 11, formatter: (v: number) => v.toFixed(1) }}>{critRows.map((c) => <Cell key={c.name} fill={SCALE_COLOR[String(Math.max(1, Math.round(c.mean)))]} />)}</Bar></BarChart></ResponsiveContainer>
            </div>
          </Panel>
          <Panel title="Needs attention" subtitle="Low ratings, sessions not delivered, attendance under 75 %, poor internet or power" className="lg:col-span-2">
            {d.needs_attention.length === 0 ? <div className="py-2 text-sm text-emerald-800">Nothing flagged in these reports.</div> : (
              <ul className="grid gap-2 md:grid-cols-2">
                {d.needs_attention.map((x) => <li key={x.id} className="flex items-start justify-between gap-2 rounded-lg border border-amber-100 bg-amber-50/50 px-3 py-2 text-sm"><div><div className="font-semibold"><AlertTriangle size={14} className="mr-1 inline text-amber-600" />{x.venue} · {x.hall}<span className="font-normal text-slate-500"> · day {x.training_day} · {fmtDate(x.report_date)} · {x.lead_facilitator}</span></div><div className="mt-1 flex flex-wrap gap-1">{x.reasons.map((s) => <span key={s} className="rounded-full bg-white px-2 py-0.5 text-[11px] font-semibold text-amber-900 ring-1 ring-amber-200">{s}</span>)}</div></div><button className="shrink-0 text-xs font-semibold text-navy underline" onClick={() => { setOpen(x); setTab("reports"); }}>Open</button></li>)}
              </ul>
            )}
          </Panel>
        </div>
      ))}
      {tab === "venue" && <Panel title="By venue"><GroupTable groups={d.by_venue} first="Venue" /></Panel>}
      {tab === "hall" && <Panel title="By hall"><GroupTable groups={d.by_hall} first="Venue · hall" /></Panel>}
      {tab === "day" && <Panel title="By training day"><GroupTable groups={d.by_day} first="Day" /></Panel>}

      {tab === "feedback" && (
        <div className="grid gap-4 lg:grid-cols-2">
          {([["went_right", "What worked well", "F", "border-emerald-200 bg-emerald-50/40"], ["went_wrong", "What did not work well", "G", "border-red-200 bg-red-50/40"], ["recommendations", "Recommended actions", "H", "border-sky-200 bg-sky-50/40"], ["gaps", "Gaps, errors, redundancies and teaching aids", "H", "border-violet-200 bg-violet-50/40"]] as const).map(([field, title, sec, cls]) => (
            <Panel key={field} title={title} subtitle={`Section ${sec} · ${data.length} report${data.length === 1 ? "" : "s"}`}>
              {data.length === 0 ? <Empty /> : (
                <ul className="max-h-[32rem] space-y-2 overflow-auto pr-1">
                  {data.map((x) => <li key={x.id} className={clsx("rounded-lg border px-3 py-2 text-sm", cls)}><div className="text-[11px] font-semibold text-slate-500">{x.venue} · {x.hall} · day {x.training_day} · {fmtDate(x.report_date)} · {x.lead_facilitator}</div><div className="mt-0.5 whitespace-pre-line">{x[field]}</div>{field === "recommendations" && <div className="mt-1 text-xs text-slate-600">Who should act: {x.actor_labels.join(", ")}{x.actor_other ? ` (${x.actor_other})` : ""}</div>}{field === "went_right" && x.repeat_share && <div className="mt-1 text-xs text-slate-600">To repeat / share: {x.repeat_share}</div>}</li>)}
                </ul>
              )}
            </Panel>
          ))}
        </div>
      )}

      {tab === "reports" && (
        <Panel title="Reports" subtitle="Click a row for the full report">
          <div className="overflow-x-auto">
            <table className="table text-sm">
              <thead><tr><th>Date</th><th>Day</th><th>Venue</th><th>Hall</th><th>Lead facilitator</th><th className="text-right">Present / reg.</th><th className="text-right">Attendance</th><th>Delivered</th><th className="text-right">Rating</th><th>Flags</th></tr></thead>
              <tbody>
                {data.map((x) => (
                  <tr key={x.id} className={clsx("cursor-pointer hover:bg-slate-50", open?.id === x.id && "bg-sky-50")} onClick={() => setOpen(open?.id === x.id ? null : x)}>
                    <td className="whitespace-nowrap">{fmtDate(x.report_date)}</td><td>{x.training_day}</td><td>{x.venue}</td><td>{x.hall}</td><td>{x.lead_facilitator}</td>
                    <td className="text-right">{x.present} / {x.registered}</td><td className={clsx("text-right font-semibold", statusBg[status(x.attendance_pct, 90, 75)])}>{pct(x.attendance_pct)}</td>
                    <td><span className="rounded-full px-2 py-0.5 text-xs font-semibold text-white" style={{ background: DELIVERY_COLOR[x.delivered] }}>{x.delivered_label}</span></td>
                    <td className="text-right font-semibold" style={{ color: SCALE_COLOR[String(Math.round(x.mean_rating))] }}>{x.mean_rating.toFixed(1)}</td>
                    <td className="text-xs">{x.reasons.length > 0 && <span className="rounded-full bg-amber-100 px-2 py-0.5 font-semibold text-amber-900">{x.reasons.length} flag{x.reasons.length === 1 ? "" : "s"}</span>}</td>
                  </tr>
                ))}
                {data.length === 0 && <tr><td colSpan={10}><Empty text="No report for these filters." /></td></tr>}
              </tbody>
            </table>
          </div>
        </Panel>
      )}

      {open && !edit && (
        <div className="fixed inset-0 z-40 flex justify-end bg-black/40" onClick={() => setOpen(null)}>
          <div className="h-full w-full max-w-2xl overflow-y-auto bg-white shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <div className="sticky top-0 z-10 border-b border-slate-200 bg-white px-5 py-3">
              <div className="flex items-start justify-between gap-3">
                <div><div className="text-xs uppercase tracking-wide text-slate-400">Day {open.training_day} · {fmtDate(open.report_date)}</div><h2 className="text-lg font-semibold">{open.venue} · {open.hall}</h2><div className="text-xs text-slate-500">Lead facilitator {open.lead_facilitator}{open.other_facilitators ? ` · with ${open.other_facilitators}` : ""}</div></div>
                <button className="text-slate-500 hover:text-slate-800" onClick={() => setOpen(null)}><X size={20} /></button>
              </div>
              {can("me_fac.manage") && spec.data && <div className="mt-3 flex gap-2"><button className="btn-outline" onClick={() => { setEdit({ report: open, values: fromReport(open, spec.data!) }); setTouched(false); }}><Pencil size={16} /> Edit</button><button className="btn-outline text-red-700" onClick={() => { if (confirm("Remove this report?")) remove.mutate(open); }}><Trash2 size={16} /> Remove</button></div>}
            </div>
            <div className="px-5 py-4"><Detail x={open} /></div>
          </div>
        </div>
      )}
      {edit && spec.data && (
        <div className="fixed inset-0 z-40 overflow-y-auto bg-black/40 p-4" onClick={() => setEdit(null)}>
          <div className="mx-auto max-w-3xl rounded-2xl bg-white p-5 shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <div className="mb-3 flex items-center justify-between"><h2 className="text-lg font-semibold">Edit the report · {edit.report.venue} · {edit.report.hall} · day {edit.report.training_day}</h2><button className="text-slate-500 hover:text-slate-800" onClick={() => setEdit(null)}><X size={20} /></button></div>
            <FacReportForm spec={spec.data} agenda={agenda.data ?? []} values={edit.values} onChange={(v) => setEdit({ ...edit, values: v })} onSubmit={() => { setTouched(true); if (editErrors.length === 0) save.mutate(edit); }} busy={save.isPending} submitLabel="Save changes" errors={touched ? editErrors : []} />
          </div>
        </div>
      )}
      {qr && <QrDialog url={link} title={r.title} subtitle="Daily Facilitator's Report · the Lead Facilitator of each hall sends one report per day" onClose={() => setQr(false)} />}
    </div>
  );
}

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return <div><h3 className="mb-1 text-xs font-bold uppercase tracking-wide text-slate-500">{title}</h3><div className="whitespace-pre-line rounded-md border border-slate-200 px-3 py-2">{children}</div></div>;
}
