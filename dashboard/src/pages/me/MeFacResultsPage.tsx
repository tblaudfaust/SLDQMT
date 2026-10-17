import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import clsx from "clsx";
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Copy, Download, ExternalLink, Pencil, QrCode, Trash2 } from "lucide-react";
import { ApiError, api, download, fmtDate, qs } from "../../api/client";
import type { MeFacAgendaItem, MeFacAssessment, MeFacGroup, MeFacSpec, MeFacSummary } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { Card, Empty, ErrorBox, KpiTile, Spinner } from "../../components/ui";
import QrDialog from "../../components/QrDialog";
import { BAND_CLS, BAND_COLOR, FacilitatorForm, SCORE_COLOR, fromAssessment, toFacPayload, validateFac, type FacValues } from "../public/FacilitatorForm";
import { PHASE_LABEL, assessLink } from "./MeFacPage";

const NAVY = "#1F4E79";
const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${v}%`);
const num = (v: number | null | undefined, d = 1) => (v === null || v === undefined ? "—" : v.toFixed(d));
const CRIT = ["technical", "clarity", "practical", "participation", "time"] as const;
const CRIT_SHORT: Record<string, string> = { technical: "Technical", clarity: "Clarity", practical: "Practical", participation: "Participation", time: "Time" };
type Tab = "overview" | "district" | "hall" | "trainer" | "day" | "chapters" | "monitor" | "ratings";

function BandPill({ band, label }: { band: string | null; label?: string | null }) {
  if (!band) return <span className="text-slate-400">—</span>;
  return <span className={clsx("inline-block whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-semibold", BAND_CLS[band])}>{label ?? band}</span>;
}

function Score({ v }: { v: number }) {
  return <span className="inline-block w-6 rounded text-center text-xs font-bold text-white" style={{ background: SCORE_COLOR[String(v)] }}>{v}</span>;
}

/** One training's trainer ratings: by district, hall, trainer, day, chapter and monitor, with the list of ratings. */
export default function MeFacResultsPage() {
  const { id } = useParams();
  const { can } = useAuth();
  const qc = useQueryClient();
  const [f, setF] = useState({ district: "", hall: "", trainer: "", monitor: "", training_day: "", date_from: "", date_to: "" });
  const query = qs(f);
  const res = useQuery({ queryKey: ["me-fac", "summary", id, query], queryFn: () => api.get<MeFacSummary>(`/me/facilitators/rounds/${id}/summary${query}`) });
  const all = useQuery({ queryKey: ["me-fac", "summary", id, "all"], queryFn: () => api.get<MeFacSummary>(`/me/facilitators/rounds/${id}/summary`) });
  const spec = useQuery({ queryKey: ["me-fac", "form"], queryFn: () => api.get<MeFacSpec>("/me/facilitators/form") });
  const agenda = useQuery({ queryKey: ["me-fac", "agenda", id], queryFn: () => api.get<MeFacAgendaItem[]>(`/me/facilitators/rounds/${id}/agenda`) });
  const ratings = useQuery({ queryKey: ["me-fac", "assessments", id, query], queryFn: () => api.get<MeFacAssessment[]>(`/me/facilitators/rounds/${id}/assessments${query}`) });
  const [tab, setTab] = useState<Tab>("overview");
  const [open, setOpen] = useState<number | null>(null);
  const [edit, setEdit] = useState<MeFacAssessment | null>(null);
  const [qr, setQr] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const invalidate = () => qc.invalidateQueries({ queryKey: ["me-fac"] });
  const remove = useMutation({ mutationFn: (x: MeFacAssessment) => api.delete(`/me/facilitators/rounds/${id}/assessments/${x.id}`), onSuccess: invalidate, onError: setError });
  if (res.isLoading) return <Spinner />;
  if (res.error || !res.data) return <ErrorBox error={res.error} />;
  const d = res.data;
  const r = d.round;
  const lists = all.data ?? d;
  const filtered = Object.values(f).some(Boolean);
  const exportFile = async (format: "xlsx" | "pdf") => {
    setError(null);
    try { await download(`/me/facilitators/rounds/${id}/export${qs({ ...f, format })}`, `facilitators-${id}.${format}`); } catch (err) { setError(err); }
  };
  const districtRows = d.by_district.map((g) => ({ name: g.label, "Score %": g.mean_pct ?? 0, Ratings: g.assessments, band: g.band }));
  const hallRows = d.by_hall.map((g) => ({ name: g.label, "Score %": g.mean_pct ?? 0, Ratings: g.assessments, band: g.band }));
  const dayRows = d.by_day.map((g) => ({ name: g.label, "Score %": g.mean_pct ?? 0, ...Object.fromEntries(CRIT.map((c) => [CRIT_SHORT[c], g.criteria[c] ?? 0])) }));
  const critRows = d.criteria.map((c) => ({ name: c.label, mean: c.mean ?? 0, ...Object.fromEntries(c.distribution.map((x) => [x.code, x.count])) }));
  const overallBand = d.mean_pct === null ? null : spec.data?.bands.find((b) => d.mean_pct! >= b.min_pct) ?? null;

  const GroupTable = ({ rows, first, showPlace }: { rows: MeFacGroup[]; first: string; showPlace?: boolean }) => (
    <div className="overflow-x-auto">
      <table className="table">
        <thead><tr><th>{first}</th>{showPlace && <th>District · hall</th>}<th className="text-right">Ratings</th><th className="text-right">Trainers</th><th className="text-right">Section A /20</th><th className="text-right">Score %</th><th>Band</th>{CRIT.map((c) => <th key={c} className="text-right">{CRIT_SHORT[c]}</th>)}<th>Weakest</th><th className="text-right">1s and 2s</th></tr></thead>
        <tbody>
          {rows.map((g) => (
            <tr key={g.key} className={clsx(g.band === "NEEDS_IMPROVEMENT" && "bg-red-50", g.band === "FAIR" && "bg-amber-50/60")}>
              <td className="font-medium">{g.label}</td>
              {showPlace && <td className="text-xs text-slate-500">{g.district}{g.hall ? ` · ${g.hall}` : ""}</td>}
              <td className="text-right">{g.assessments}</td><td className="text-right">{g.trainers}</td>
              <td className="text-right">{num(g.mean_a_total)}</td><td className="text-right font-semibold">{pct(g.mean_pct)}</td><td><BandPill band={g.band} label={g.band_label} /></td>
              {CRIT.map((c) => <td key={c} className={clsx("text-right", (g.criteria[c] ?? 4) < 2.5 && "font-semibold text-red-700")}>{num(g.criteria[c], 2)}</td>)}
              <td className="text-xs text-slate-500">{g.lowest_criterion ?? "—"}</td>
              <td className={clsx("text-right", g.low_scores && "font-semibold text-red-700")}>{g.low_scores}</td>
            </tr>
          ))}
          {rows.length === 0 && <tr><td colSpan={14}><Empty /></td></tr>}
        </tbody>
      </table>
    </div>
  );

  return (
    <div className="max-w-7xl">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link to="/me/facilitators" className="text-sm text-navy">← Facilitator assessment</Link>
          <h1 className="text-2xl font-bold">{r.title}</h1>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
            <span className="rounded-full bg-violet-100 px-2 py-0.5 font-semibold text-violet-800">{PHASE_LABEL[r.phase] ?? r.phase}</span>
            <span className={clsx("rounded-full px-2 py-0.5 font-semibold", r.status === "OPEN" ? "bg-green-100 text-green-800" : "bg-slate-200 text-slate-700")}>{r.status === "OPEN" ? "Open" : "Closed"}</span>
            {(r.period_start || r.period_end) && <span className="text-slate-500">{fmtDate(r.period_start)}{r.period_end ? ` – ${fmtDate(r.period_end)}` : ""}</span>}
            <span className="text-slate-500">{r.agenda_items} chapters, {r.agenda_days} days</span>
            <button className="text-navy" onClick={() => navigator.clipboard.writeText(assessLink(r))}><Copy size={12} className="mr-1 inline" />Copy link</button>
            <a className="text-navy" href={assessLink(r)} target="_blank" rel="noreferrer"><ExternalLink size={12} className="mr-1 inline" />Open the rating page</a>
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
        <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-7">
          <select className="input" value={f.district} onChange={(e) => setF({ ...f, district: e.target.value, hall: "" })}><option value="">All districts</option>{lists.by_district.map((g) => <option key={g.key} value={g.key === "HQ" ? "HQ" : g.label}>{g.label} ({g.assessments})</option>)}</select>
          <select className="input" value={f.hall} onChange={(e) => setF({ ...f, hall: e.target.value })}><option value="">All halls</option>{lists.by_hall.filter((g) => !f.district || (f.district === "HQ" ? g.district === "National / HQ" : g.district === f.district)).map((g) => <option key={g.key} value={g.hall ?? ""}>{g.label} ({g.assessments})</option>)}</select>
          <select className="input" value={f.trainer} onChange={(e) => setF({ ...f, trainer: e.target.value })}><option value="">All trainers</option>{lists.by_trainer.map((g) => <option key={g.key} value={g.label}>{g.label} ({g.assessments})</option>)}</select>
          <select className="input" value={f.monitor} onChange={(e) => setF({ ...f, monitor: e.target.value })}><option value="">All monitors</option>{lists.by_monitor.map((g) => <option key={g.key} value={g.label}>{g.label} ({g.assessments})</option>)}</select>
          <select className="input" value={f.training_day} onChange={(e) => setF({ ...f, training_day: e.target.value })}><option value="">All days</option>{lists.by_day.map((g) => <option key={g.key} value={g.key}>{g.label} ({g.assessments})</option>)}</select>
          <input className="input" type="date" value={f.date_from} onChange={(e) => setF({ ...f, date_from: e.target.value })} title="From date" />
          <input className="input" type="date" value={f.date_to} onChange={(e) => setF({ ...f, date_to: e.target.value })} title="To date" />
        </div>
        {filtered && <div className="mt-2 text-xs text-sky-900">Every figure and export on this page follows these filters. <button className="font-semibold underline" onClick={() => setF({ district: "", hall: "", trainer: "", monitor: "", training_day: "", date_from: "", date_to: "" })}>Clear</button></div>}
      </Card>

      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <KpiTile label="Ratings" value={d.assessments} sub={`${d.trainers} trainers · ${d.monitors} monitors · ${d.days} days`} />
        <KpiTile label="Halls" value={d.halls} sub={`${d.districts} district${d.districts === 1 ? "" : "s"}`} />
        <KpiTile label="Mean score" value={pct(d.mean_pct)} tone={d.mean_pct === null ? "navy" : d.mean_pct < 45 ? "red" : d.mean_pct < 65 ? "amber" : "green"} sub={overallBand ? overallBand.label : "section A and the chapters rated"} />
        <KpiTile label="Section A" value={num(d.mean_a_total)} sub="mean of 20 · five criteria" />
        <KpiTile label="Excellent" value={d.band_counts[0]?.count ?? 0} tone="green" sub={`${pct(d.band_counts[0]?.pct)} of ratings`} />
        <KpiTile label="Need improvement" value={d.band_counts[3]?.count ?? 0} tone={d.band_counts[3]?.count ? "red" : "navy"} sub={`${d.low_scores} ratings with a 1 or 2`} />
      </div>

      <div className="mb-4 flex flex-wrap gap-1 border-b border-slate-200">
        {([["overview", "Overview"], ["district", `By district (${d.by_district.length})`], ["hall", `By hall (${d.by_hall.length})`], ["trainer", `By trainer (${d.by_trainer.length})`], ["day", "By day"], ["chapters", `Chapters (${d.topics.length})`], ["monitor", "By monitor"], ["ratings", `Ratings (${d.assessments})`]] as [Tab, string][]).map(([t, label]) => (
          <button key={t} onClick={() => setTab(t)} className={clsx("-mb-px border-b-2 px-3 py-2 text-sm font-medium", tab === t ? "border-navy text-navy" : "border-transparent text-slate-500 hover:text-slate-700")}>{label}</button>
        ))}
      </div>

      {tab === "overview" && (d.assessments === 0 ? <Card><Empty text="No rating yet. Share the link or QR code with the M&E monitors in the halls." /></Card> : (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card title="Mean score by district (%)">
            <div style={{ height: 40 + 36 * Math.max(districtRows.length, 3) }}>
              <ResponsiveContainer>
                <BarChart data={districtRows} layout="vertical" margin={{ left: 10, right: 30 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" domain={[0, 100]} unit="%" tick={{ fontSize: 12 }} /><YAxis type="category" dataKey="name" width={110} tick={{ fontSize: 12 }} />
                  <Tooltip formatter={(v: number, n: string) => (n === "Score %" ? `${v}%` : v)} />
                  <Bar dataKey="Score %" isAnimationActive={false} label={{ position: "right", fontSize: 11, formatter: (v: number) => `${v}%` }}>{districtRows.map((x) => <Cell key={x.name} fill={BAND_COLOR[x.band ?? "GOOD"]} />)}</Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
          <Card title="Mean score by hall (%)">
            <div style={{ height: 40 + 36 * Math.max(hallRows.length, 3) }}>
              <ResponsiveContainer>
                <BarChart data={hallRows} layout="vertical" margin={{ left: 10, right: 30 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" domain={[0, 100]} unit="%" tick={{ fontSize: 12 }} /><YAxis type="category" dataKey="name" width={150} tick={{ fontSize: 12 }} />
                  <Tooltip formatter={(v: number, n: string) => (n === "Score %" ? `${v}%` : v)} />
                  <Bar dataKey="Score %" isAnimationActive={false} label={{ position: "right", fontSize: 11, formatter: (v: number) => `${v}%` }}>{hallRows.map((x) => <Cell key={x.name} fill={BAND_COLOR[x.band ?? "GOOD"]} />)}</Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
          <Card title="Rating bands">
            <div className="flex items-center gap-4">
              <div style={{ width: 180, height: 180 }}>
                <ResponsiveContainer>
                  <PieChart><Pie data={d.band_counts.filter((b) => b.count)} dataKey="count" nameKey="label" innerRadius={50} outerRadius={85} isAnimationActive={false}>{d.band_counts.filter((b) => b.count).map((b) => <Cell key={b.code} fill={BAND_COLOR[b.code]} />)}</Pie><Tooltip /></PieChart>
                </ResponsiveContainer>
              </div>
              <ul className="flex-1 space-y-1 text-sm">
                {d.band_counts.map((b) => <li key={b.code} className="flex items-center justify-between"><span className="flex items-center gap-2"><span className="inline-block h-3 w-3 rounded-sm" style={{ background: BAND_COLOR[b.code] }} />{b.label}</span><span className="font-semibold">{b.count} <span className="font-normal text-slate-400">· {pct(b.pct)}</span></span></li>)}
              </ul>
            </div>
            <p className="mt-2 text-xs text-slate-500">Excellent 85 % and above (17–20 of 20) · Good 65–84 % (13–16) · Fair 45–64 % (9–12) · Needs improvement below 45 % (5–8).</p>
          </Card>
          <Card title="Section A · criteria (mean 1–4) and score distribution">
            <div style={{ height: 230 }}>
              <ResponsiveContainer>
                <BarChart data={critRows} layout="vertical" margin={{ left: 10, right: 10 }} stackOffset="expand">
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" tickFormatter={(v) => `${Math.round(v * 100)}%`} tick={{ fontSize: 11 }} /><YAxis type="category" dataKey="name" width={130} tick={{ fontSize: 11 }} />
                  <Tooltip /><Legend />
                  {["4", "3", "2", "1"].map((s) => <Bar key={s} dataKey={s} stackId="a" fill={SCORE_COLOR[s]} name={`${s} · ${s === "4" ? "Excellent" : s === "3" ? "Good" : s === "2" ? "Fair" : "Poor"}`} isAnimationActive={false} />)}
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-2 grid grid-cols-5 gap-1 text-center text-xs">{d.criteria.map((c) => <div key={c.key} className={clsx("rounded py-1", (c.mean ?? 4) < 2.5 ? "bg-red-50 text-red-800" : "bg-slate-50")}><div className="font-semibold">{num(c.mean, 2)}</div><div className="text-slate-500">{CRIT_SHORT[c.key]}</div></div>)}</div>
          </Card>
          <Card title="Score by training day (%)" className="lg:col-span-2">
            <div style={{ height: 240 }}>
              <ResponsiveContainer>
                <LineChart data={dayRows} margin={{ left: 0, right: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} /><YAxis domain={[0, 100]} unit="%" tick={{ fontSize: 12 }} />
                  <Tooltip /><Legend />
                  <Line type="monotone" dataKey="Score %" stroke={NAVY} strokeWidth={3} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Card>
          <Card title="Trainers needing attention" className="lg:col-span-2">
            {d.needs_attention.length === 0 ? <Empty text="No trainer in the Fair or Needs improvement bands, and no criterion scored 1 or 2." /> : <GroupTable rows={d.needs_attention} first="Trainer" showPlace />}
          </Card>
        </div>
      ))}

      {tab === "district" && <Card title="By district"><GroupTable rows={d.by_district} first="District" /></Card>}
      {tab === "hall" && <Card title="By hall"><GroupTable rows={d.by_hall} first="District · hall" /></Card>}
      {tab === "trainer" && <Card title="By trainer · best first"><GroupTable rows={d.by_trainer} first="Trainer" showPlace /></Card>}
      {tab === "day" && (
        <Card title="By training day">
          <div style={{ height: 260 }} className="mb-3">
            <ResponsiveContainer>
              <LineChart data={dayRows} margin={{ left: 0, right: 10 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 12 }} /><YAxis domain={[1, 4]} tick={{ fontSize: 12 }} />
                <Tooltip /><Legend />
                {CRIT.map((c, i) => <Line key={c} type="monotone" dataKey={CRIT_SHORT[c]} stroke={[NAVY, "#15803d", "#d97706", "#38bdf8", "#b91c1c"][i]} isAnimationActive={false} />)}
              </LineChart>
            </ResponsiveContainer>
          </div>
          <GroupTable rows={d.by_day} first="Day" />
        </Card>
      )}
      {tab === "chapters" && (
        <Card title="Chapters and thematic sections · how well they were facilitated (mean 1–4)">
          <table className="table">
            <thead><tr><th className="w-16">Day</th><th>Chapter / section</th><th className="text-right">Ratings</th><th className="text-right">Mean</th><th className="w-40" /></tr></thead>
            <tbody>
              {d.topics.map((t) => (
                <tr key={`${t.day}-${t.topic}`} className={clsx((t.mean ?? 4) < 2.5 && "bg-red-50")}>
                  <td>Day {t.day}</td><td>{t.topic}</td><td className="text-right">{t.ratings}</td><td className="text-right font-semibold">{num(t.mean, 2)}</td>
                  <td><div className="h-2 rounded bg-slate-100"><div className="h-2 rounded" style={{ width: `${((t.mean ?? 0) / 4) * 100}%`, background: SCORE_COLOR[String(Math.round(t.mean ?? 0))] ?? NAVY }} /></div></td>
                </tr>
              ))}
              {d.topics.length === 0 && <tr><td colSpan={5}><Empty text="No chapter rated yet." /></td></tr>}
            </tbody>
          </table>
        </Card>
      )}
      {tab === "monitor" && <Card title="By M&E monitor"><GroupTable rows={d.by_monitor} first="Monitor" /></Card>}

      {tab === "ratings" && (
        <Card title="Ratings">
          {ratings.isLoading ? <Spinner /> : (
            <div className="overflow-x-auto">
              <table className="table">
                <thead><tr><th>Date</th><th>Day</th><th>District · hall</th><th>Trainer</th><th>Monitor</th>{CRIT.map((c) => <th key={c} className="text-center">{CRIT_SHORT[c].slice(0, 4)}</th>)}<th className="text-right">A /20</th><th className="text-right">B</th><th className="text-right">Score</th><th>Band</th><th /></tr></thead>
                <tbody>
                  {(ratings.data ?? []).map((x) => (
                    <>
                      <tr key={x.id} className={clsx("cursor-pointer hover:bg-slate-50", open === x.id && "bg-sky-50")} onClick={() => setOpen(open === x.id ? null : x.id)}>
                        <td className="whitespace-nowrap">{fmtDate(x.assessment_date)}</td><td>{x.training_day}</td><td>{x.district ?? "National / HQ"} · {x.hall}</td><td className="font-medium">{x.trainer_name}</td><td>{x.monitor_name}</td>
                        {[x.s_technical, x.s_clarity, x.s_practical, x.s_participation, x.s_time].map((v, i) => <td key={i} className="text-center"><Score v={v} /></td>)}
                        <td className="text-right">{x.section_a_total}</td><td className="text-right text-slate-500">{x.section_b_max ? `${x.section_b_total}/${x.section_b_max}` : "—"}</td><td className="text-right font-semibold">{x.score_pct}%</td><td><BandPill band={x.band} label={x.band_label} /></td>
                        <td className="whitespace-nowrap text-right">
                          {can("me_fac.manage") && <button className="mr-2 text-navy" title="Edit" onClick={(e) => { e.stopPropagation(); setEdit(x); }}><Pencil size={14} /></button>}
                          {can("me_fac.manage") && <button className="text-red-700" title="Remove" onClick={(e) => { e.stopPropagation(); if (confirm(`Remove the rating of ${x.trainer_name} by ${x.monitor_name} on ${fmtDate(x.assessment_date)}?`)) remove.mutate(x); }}><Trash2 size={14} /></button>}
                        </td>
                      </tr>
                      {open === x.id && (
                        <tr key={`${x.id}-d`} className="bg-sky-50/60"><td colSpan={15} className="text-sm">
                          <div className="grid gap-3 md:grid-cols-3">
                            <div><div className="text-xs font-bold uppercase text-slate-500">Section B · chapters</div>{x.sections.length === 0 ? <div className="text-slate-400">None listed</div> : <ul className="mt-1 space-y-0.5">{x.sections.map((s) => <li key={s.topic} className="flex items-center justify-between gap-2"><span>{s.topic}</span>{s.rating === null ? <span className="text-xs text-slate-400">not observed</span> : <Score v={s.rating} />}</li>)}</ul>}</div>
                            <div><div className="text-xs font-bold uppercase text-slate-500">Strengths</div><div className="whitespace-pre-wrap">{x.strengths ?? "—"}</div><div className="mt-2 text-xs font-bold uppercase text-slate-500">To improve</div><div className="whitespace-pre-wrap">{x.improvements ?? "—"}</div></div>
                            <div><div className="text-xs font-bold uppercase text-slate-500">Comments</div><div className="whitespace-pre-wrap">{x.comments ?? "—"}</div><div className="mt-2 text-xs text-slate-400">Sent {new Date(x.submitted_at).toLocaleString("en-GB")}{x.edited_by_name ? ` · edited by ${x.edited_by_name}` : ""}</div></div>
                          </div>
                        </td></tr>
                      )}
                    </>
                  ))}
                  {(ratings.data ?? []).length === 0 && <tr><td colSpan={15}><Empty text="No rating for these filters." /></td></tr>}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}

      {qr && <QrDialog url={assessLink(r)} title={r.title} subtitle="Daily Trainer Facilitation Rating · the M&E monitor rates each trainer once a day" onClose={() => setQr(false)} />}
      {edit && spec.data && <EditDialog assessment={edit} spec={spec.data} agenda={agenda.data ?? []} onClose={() => { setEdit(null); invalidate(); }} roundId={id!} />}
    </div>
  );
}

function EditDialog({ assessment, spec, agenda, onClose, roundId }: { assessment: MeFacAssessment; spec: MeFacSpec; agenda: MeFacAgendaItem[]; onClose: () => void; roundId: string }) {
  const [values, setValues] = useState<FacValues>(() => fromAssessment(assessment));
  const [error, setError] = useState<unknown>(null);
  const [touched, setTouched] = useState(false);
  const errors = validateFac(values, spec);
  const save = useMutation({ mutationFn: () => api.put(`/me/facilitators/rounds/${roundId}/assessments/${assessment.id}`, toFacPayload(values)), onSuccess: onClose, onError: setError });
  return (
    <div className="fixed inset-0 z-40 flex items-start justify-center overflow-y-auto bg-black/40 p-4" onClick={onClose}>
      <div className="w-full max-w-3xl rounded-lg bg-white p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="mb-3 flex items-center justify-between"><h2 className="text-lg font-semibold">Edit rating · {assessment.trainer_name}</h2><button className="btn-outline" onClick={onClose}>Close</button></div>
        <ErrorBox error={error instanceof ApiError ? error.message : error} />
        <FacilitatorForm spec={spec} agenda={agenda} values={values} onChange={setValues} onSubmit={() => { setTouched(true); if (!errors.length) save.mutate(); }} busy={save.isPending} submitLabel="Save changes" errors={touched ? errors : []} compact />
      </div>
    </div>
  );
}
