import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import clsx from "clsx";
import { BarChart3, CalendarDays, Copy, ExternalLink, FileSpreadsheet, Link2, Lock, Plus, QrCode, Trash2, Unlock } from "lucide-react";
import { ApiError, api, fmtDate } from "../../api/client";
import type { MeDailyAgendaTemplate, MeFacAgendaItem, MeFacRound } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { Card, Empty, ErrorBox, Field, KpiTile, Spinner } from "../../components/ui";
import QrDialog from "../../components/QrDialog";
import { BAND_CLS } from "../public/FacilitatorForm";

interface Form { id?: number; title: string; phase: "MASTER" | "TOT" | "FIELD"; period_start: string; period_end: string; description: string; agenda_template: string }
const empty: Form = { title: "", phase: "MASTER", period_start: "", period_end: "", description: "", agenda_template: "TRAINING_2026" };
export const PHASE_LABEL: Record<string, string> = { MASTER: "Master Training", TOT: "Training of Trainers", FIELD: "Field Staff Training" };

/** The link M&E monitors use in the halls: the configured evaluation address (censusme.statistics.sl), or this dashboard's own address. */
export const assessLink = (r: { token: string; share_url: string | null }) => r.share_url ?? `${window.location.origin}/assess/${r.token}`;
const bandOf = (pct: number | null) => (pct === null ? null : pct >= 85 ? "EXCELLENT" : pct >= 65 ? "GOOD" : pct >= 45 ? "FAIR" : "NEEDS_IMPROVEMENT");
const BAND_LABEL: Record<string, string> = { EXCELLENT: "Excellent", GOOD: "Good", FAIR: "Fair", NEEDS_IMPROVEMENT: "Needs improvement" };

/** Facilitator assessment: the Daily Trainer Facilitation Rating Tool, one rating per trainer per day per hall, grouped per training with its chapters per day. */
export default function MeFacPage() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const list = useQuery({ queryKey: ["me-fac", "rounds"], queryFn: () => api.get<MeFacRound[]>("/me/facilitators/rounds") });
  const templates = useQuery({ queryKey: ["me-fac", "agenda-templates"], queryFn: () => api.get<MeDailyAgendaTemplate[]>("/me/facilitators/agenda-templates") });
  const [form, setForm] = useState<Form | null>(null);
  const [agendaFor, setAgendaFor] = useState<MeFacRound | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [copied, setCopied] = useState<number | null>(null);
  const [qr, setQr] = useState<MeFacRound | null>(null);
  const invalidate = () => qc.invalidateQueries({ queryKey: ["me-fac"] });
  const save = useMutation({
    mutationFn: (f: Form) => {
      const body = { title: f.title, phase: f.phase, period_start: f.period_start || null, period_end: f.period_end || null, description: f.description || null };
      return f.id ? api.patch<MeFacRound>(`/me/facilitators/rounds/${f.id}`, body) : api.post<MeFacRound>("/me/facilitators/rounds", { ...body, agenda_template: f.agenda_template || null });
    },
    onSuccess: (r, f) => { invalidate(); setForm(null); setError(null); if (!f.id && !f.agenda_template) setAgendaFor(r); },
    onError: setError,
  });
  const toggle = useMutation({ mutationFn: (r: MeFacRound) => api.patch<MeFacRound>(`/me/facilitators/rounds/${r.id}`, { status: r.status === "OPEN" ? "CLOSED" : "OPEN" }), onSuccess: invalidate, onError: setError });
  const remove = useMutation({ mutationFn: (r: MeFacRound) => api.delete(`/me/facilitators/rounds/${r.id}`), onSuccess: invalidate, onError: setError });
  const copy = async (r: MeFacRound) => {
    try { await navigator.clipboard.writeText(assessLink(r)); setCopied(r.id); setTimeout(() => setCopied(null), 2000); } catch { prompt("Copy this link", assessLink(r)); }
  };
  const data = list.data ?? [];
  const totals = data.reduce((t, r) => ({ ratings: t.ratings + r.assessments, trainers: t.trainers + r.trainers, low: t.low + r.needs_improvement }), { ratings: 0, trainers: 0, low: 0 });

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Facilitator assessment</h1>
          <p className="text-sm text-slate-500">Daily Trainer Facilitation Rating Tool. Create one entry per training, load the chapters of each day, share the link or QR code with the M&amp;E monitors in the halls, and follow every trainer's rating by district, hall, day and chapter.</p>
        </div>
        {can("me_fac.manage") && <button className="btn-primary" onClick={() => { setForm(empty); setError(null); }}><Plus size={16} /> New facilitator assessment</button>}
      </div>
      <ErrorBox error={error instanceof ApiError ? error.message : error} />
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <KpiTile label="Trainings" value={data.length} sub={`${data.filter((r) => r.status === "OPEN").length} open`} />
        <KpiTile label="Ratings received" value={totals.ratings} tone="green" sub={`${totals.trainers} trainers rated`} />
        <KpiTile label="Ratings needing improvement" value={totals.low} tone={totals.low ? "red" : "navy"} sub="score below 45 %" />
        <KpiTile label="Halls covered" value={data.reduce((t, r) => t + r.halls, 0)} sub={`${data.reduce((t, r) => t + r.districts, 0)} districts`} />
      </div>
      {list.isLoading ? <Spinner /> : data.length === 0 ? (
        <Card><Empty text="No facilitator assessment yet. Create one per training, load its chapters per day, then share its link with the M&E monitors." /></Card>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {data.map((r) => {
            const band = bandOf(r.mean_pct);
            return (
              <Card key={r.id}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <Link to={`/me/facilitators/${r.id}`} className="text-lg font-semibold text-navy hover:underline">{r.title}</Link>
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
                      <span className="rounded-full bg-violet-100 px-2 py-0.5 font-semibold text-violet-800">{PHASE_LABEL[r.phase] ?? r.phase}</span>
                      <span className={clsx("rounded-full px-2 py-0.5 font-semibold", r.status === "OPEN" ? "bg-green-100 text-green-800" : "bg-slate-200 text-slate-700")}>{r.status === "OPEN" ? "Open" : "Closed"}</span>
                      {(r.period_start || r.period_end) && <span className="text-slate-500">{fmtDate(r.period_start)}{r.period_end ? ` – ${fmtDate(r.period_end)}` : ""}</span>}
                      <span className={clsx("rounded-full px-2 py-0.5", r.agenda_items ? "bg-sky-100 text-sky-800" : "bg-amber-100 text-amber-800")}>{r.agenda_items ? `${r.agenda_items} chapters, ${r.agenda_days} days` : "No chapter list yet"}</span>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-2xl font-bold text-navy">{r.assessments}</div>
                    <div className="text-xs text-slate-500">ratings{r.last_date ? ` · last ${fmtDate(r.last_date)}` : ""}</div>
                  </div>
                </div>
                {r.description && <p className="mt-2 text-sm text-slate-600">{r.description}</p>}
                <div className="mt-3 grid grid-cols-4 gap-2 text-center text-sm">
                  <div className="rounded-md bg-slate-50 py-2"><div className="font-semibold">{r.trainers}</div><div className="text-xs text-slate-500">trainers</div></div>
                  <div className="rounded-md bg-slate-50 py-2"><div className="font-semibold">{r.halls}</div><div className="text-xs text-slate-500">halls · {r.districts} districts</div></div>
                  <div className={clsx("rounded-md py-2", band ? BAND_CLS[band] : "bg-slate-50")}><div className="font-semibold">{r.mean_pct === null ? "—" : `${r.mean_pct}%`}</div><div className="text-xs opacity-80">{band ? BAND_LABEL[band] : "mean score"}</div></div>
                  <div className={clsx("rounded-md py-2", r.needs_improvement ? "bg-red-50" : "bg-slate-50")}><div className={clsx("font-semibold", r.needs_improvement && "text-red-800")}>{r.needs_improvement}</div><div className="text-xs text-slate-500">need improvement</div></div>
                </div>
                <div className="mt-3 flex items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-2 py-1.5 text-xs">
                  <Link2 size={14} className="shrink-0 text-slate-400" />
                  <span className="truncate font-mono text-slate-600">{assessLink(r)}</span>
                  <button className="ml-auto shrink-0 text-navy" onClick={() => copy(r)} title="Copy the link for the M&E monitors"><Copy size={14} /> {copied === r.id ? "Copied" : "Copy"}</button>
                  <a className="shrink-0 text-navy" href={assessLink(r)} target="_blank" rel="noreferrer" title="Open the rating page"><ExternalLink size={14} /></a>
                  <button className="shrink-0 text-navy" onClick={() => setQr(r)} title="QR code"><QrCode size={14} /></button>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Link to={`/me/facilitators/${r.id}`} className="btn-primary"><BarChart3 size={16} /> Dashboard</Link>
                  {can("me_fac.manage") && <button className="btn-outline" onClick={() => setAgendaFor(r)}><CalendarDays size={16} /> Chapters per day</button>}
                  <button className="btn-outline" onClick={() => setQr(r)}><QrCode size={16} /> QR code</button>
                  {can("me_fac.manage") && (
                    <>
                      <button className="btn-outline" onClick={() => { setForm({ id: r.id, title: r.title, phase: r.phase, period_start: r.period_start ?? "", period_end: r.period_end ?? "", description: r.description ?? "", agenda_template: "" }); setError(null); }}>Edit</button>
                      <button className="btn-outline" onClick={() => { if (confirm(`${r.status === "OPEN" ? "Close" : "Reopen"} "${r.title}"?${r.status === "OPEN" ? " Monitors cannot send ratings while it is closed." : ""}`)) toggle.mutate(r); }}>
                        {r.status === "OPEN" ? <><Lock size={16} /> Close</> : <><Unlock size={16} /> Reopen</>}
                      </button>
                      {r.assessments === 0 && <button className="btn-outline text-red-700" onClick={() => { if (confirm(`Delete "${r.title}"? It has no ratings; its link will stop working.`)) remove.mutate(r); }}><Trash2 size={16} /> Delete</button>}
                    </>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      )}
      {qr && <QrDialog url={assessLink(qr)} title={qr.title} subtitle="Daily Trainer Facilitation Rating · the M&E monitor rates each trainer once a day" onClose={() => setQr(null)} />}
      {agendaFor && <ChaptersDialog round={agendaFor} onClose={() => { setAgendaFor(null); invalidate(); }} />}
      {form && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 p-4" onClick={() => setForm(null)}>
          <form className="w-full max-w-lg rounded-lg bg-white p-5 shadow-xl" onClick={(e) => e.stopPropagation()} onSubmit={(e) => { e.preventDefault(); save.mutate(form); }}>
            <h2 className="mb-3 text-lg font-semibold">{form.id ? "Edit facilitator assessment" : "New facilitator assessment"}</h2>
            <div className="grid gap-3">
              <Field label="Training"><input className="input" required minLength={3} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="e.g. Master Trainers session, October 2026" /></Field>
              <Field label="Training phase">
                <div className="grid grid-cols-3 gap-2">
                  {(["MASTER", "TOT", "FIELD"] as const).map((m) => (
                    <button type="button" key={m} onClick={() => setForm({ ...form, phase: m })} className={clsx("rounded-md border px-3 py-2 text-sm font-medium", form.phase === m ? "border-navy bg-navy text-white" : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50")}>{PHASE_LABEL[m]}</button>
                  ))}
                </div>
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Training from"><input className="input" type="date" value={form.period_start} onChange={(e) => setForm({ ...form, period_start: e.target.value })} /></Field>
                <Field label="to"><input className="input" type="date" value={form.period_end} onChange={(e) => setForm({ ...form, period_end: e.target.value })} /></Field>
              </div>
              {!form.id && (
                <Field label="Chapters per day to load at creation (section B of the form)">
                  <select className="input" value={form.agenda_template} onChange={(e) => setForm({ ...form, agenda_template: e.target.value })}>
                    <option value="">None now (type or upload them afterwards)</option>
                    {(templates.data ?? []).map((t) => <option key={t.key} value={t.key}>{t.title} · {t.items.length} chapters, {t.days} days</option>)}
                  </select>
                  <p className="mt-1 text-xs text-slate-500">The 2026 SLPHC training agenda is bundled: its chapters and thematic sections per day become the rows of section B. Recaps, quizzes and briefings are left out.</p>
                </Field>
              )}
              <Field label="Note shown to the monitors (optional)"><textarea className="input" rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="e.g. Rate every trainer of your hall before the daily briefing." /></Field>
            </div>
            <ErrorBox error={error instanceof ApiError ? error.message : error} />
            <div className="mt-4 flex justify-end gap-2">
              <button type="button" className="btn-outline" onClick={() => setForm(null)}>Cancel</button>
              <button className="btn-primary" disabled={save.isPending}>{save.isPending ? "Saving…" : form.id ? "Save" : form.agenda_template ? "Create with these chapters" : "Create, then add the chapters"}</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

type Row = { day: string; topic: string; details: string };

/** The editor of the chapters per day: the rows of section B on the rating form. */
function ChaptersDialog({ round, onClose }: { round: MeFacRound; onClose: () => void }) {
  const current = useQuery({ queryKey: ["me-fac", "agenda", round.id], queryFn: () => api.get<MeFacAgendaItem[]>(`/me/facilitators/rounds/${round.id}/agenda`) });
  const templates = useQuery({ queryKey: ["me-fac", "agenda-templates"], queryFn: () => api.get<MeDailyAgendaTemplate[]>("/me/facilitators/agenda-templates") });
  const [rows, setRows] = useState<Row[] | null>(null);
  const [paste, setPaste] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const toRows = (items: { day: number; topic: string; details?: string | null }[]): Row[] => items.map((a) => ({ day: String(a.day), topic: a.topic, details: a.details ?? "" }));
  const data: Row[] = rows ?? toRows(current.data ?? []);
  const replaceOrAppend = (items: { day: number; topic: string; details?: string | null }[], source: string) => {
    const incoming = toRows(items);
    if (data.length && !confirm(`Replace the ${data.length} current chapters with the ${incoming.length} from ${source}? Cancel to add them after the current ones instead.`)) setRows([...data, ...incoming]);
    else setRows(incoming);
    setNotice(`${incoming.length} chapters over ${new Set(items.map((a) => a.day)).size} days loaded from ${source}. Save to keep them.`);
  };
  const upload = async (file: File) => {
    setError(null);
    const fd = new FormData();
    fd.append("file", file);
    try {
      const r = await api.post<{ items: MeFacAgendaItem[]; days: number; warnings: string[] }>("/me/facilitators/agenda/parse", fd);
      replaceOrAppend(r.items, file.name);
      if (r.warnings.length) setNotice((n) => `${n ?? ""} ${r.warnings.length} warning(s): ${r.warnings.slice(0, 3).join("; ")}`);
    } catch (err) { setError(err); }
  };
  const setRow = (i: number, patch: Partial<Row>) => setRows(data.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  const save = useMutation({
    mutationFn: () => api.put<MeFacAgendaItem[]>(`/me/facilitators/rounds/${round.id}/agenda`, data.filter((r) => r.topic.trim() && Number(r.day) >= 1).map((r) => ({ day: Number(r.day), topic: r.topic.trim(), details: r.details.trim() || null }))),
    onSuccess: onClose,
    onError: setError,
  });
  const importPaste = () => {
    const parsed: Row[] = [];
    for (const line of paste.split(/\r?\n/)) {
      const parts = line.split(/\t|;|\|/).map((x) => x.trim());
      if (parts.length < 2) continue;
      const [day, topic, details = ""] = parts;
      if (!/^\d+$/.test(day) || !topic) continue;
      parsed.push({ day, topic, details });
    }
    if (parsed.length) { setRows([...data, ...parsed]); setPaste(""); }
  };
  const days = Array.from(new Set(data.map((r) => Number(r.day)).filter((d) => d >= 1))).sort((a, b) => a - b);
  return (
    <div className="fixed inset-0 z-40 flex items-start justify-center overflow-y-auto bg-black/40 p-4" onClick={onClose}>
      <div className="w-full max-w-4xl rounded-lg bg-white p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="mb-1 flex items-center justify-between"><h2 className="text-lg font-semibold">Chapters per day · {round.title}</h2><button className="btn-outline" onClick={onClose}>Close</button></div>
        <p className="mb-3 text-sm text-slate-500">One row per chapter or thematic section. On the form, the monitor picks the training day and the day's chapters appear in section B, each rated 1 to 4 or left as not observed. {days.length ? `${data.length} chapters over ${days.length} days.` : ""}</p>
        <ErrorBox error={error instanceof ApiError ? error.message : error} />
        <div className="mb-3 flex flex-wrap items-center gap-2 rounded-md border border-sky-200 bg-sky-50 px-3 py-2 text-sm">
          <span className="font-medium text-sky-900">Load:</span>
          {(templates.data ?? []).map((t) => <button key={t.key} className="btn-outline" onClick={() => replaceOrAppend(t.items, t.title)}><CalendarDays size={16} /> {t.title}</button>)}
          <button className="btn-outline" onClick={() => fileRef.current?.click()}><FileSpreadsheet size={16} /> Upload the agenda (Excel / CSV)</button>
          <input ref={fileRef} type="file" accept=".xlsx,.xlsm,.csv" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) upload(f); e.target.value = ""; }} />
        </div>
        {notice && <div className="mb-3 rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-900">{notice}</div>}
        {current.isLoading ? <Spinner /> : (
          <div className="max-h-[55vh] overflow-auto">
            <table className="table">
              <thead><tr><th className="w-16">Day</th><th>Chapter / thematic section</th><th>Details (sections covered)</th><th className="w-8" /></tr></thead>
              <tbody>
                {data.map((r, i) => (
                  <tr key={i} className={i > 0 && data[i - 1].day !== r.day ? "border-t-4 border-slate-200" : ""}>
                    <td><input className="input px-2" type="number" min={1} max={60} value={r.day} onChange={(e) => setRow(i, { day: e.target.value })} /></td>
                    <td><input className="input" value={r.topic} onChange={(e) => setRow(i, { topic: e.target.value })} placeholder="e.g. Chapter 8: Building Numbering and Household Listing" /></td>
                    <td><input className="input text-xs" value={r.details} onChange={(e) => setRow(i, { details: e.target.value })} placeholder="e.g. 8.1 Introduction; 8.2 …" title={r.details} /></td>
                    <td><button className="text-red-700" title="Remove" onClick={() => setRows(data.filter((_, j) => j !== i))}><Trash2 size={14} /></button></td>
                  </tr>
                ))}
                {data.length === 0 && <tr><td colSpan={4}><Empty text="No chapter yet. Load the 2026 training agenda, upload a file, paste rows, or add them one by one." /></td></tr>}
              </tbody>
            </table>
          </div>
        )}
        <div className="mt-2 flex flex-wrap gap-2">
          <button className="btn-outline" onClick={() => setRows([...data, { day: String(days.length ? days[days.length - 1] : 1), topic: "", details: "" }])}><Plus size={16} /> Add chapter</button>
        </div>
        <details className="mt-3 rounded-md border border-slate-200 p-3 text-sm">
          <summary className="cursor-pointer font-medium text-slate-700">Paste from Excel or Word</summary>
          <p className="mt-1 text-xs text-slate-500">One chapter per line: day, chapter, details (tab- or semicolon-separated). For example: <code>2 ⇥ Chapter 6: Preliminary Work in the Enumeration Area</code></p>
          <textarea className="input mt-2 font-mono text-xs" rows={5} value={paste} onChange={(e) => setPaste(e.target.value)} />
          <button className="btn-outline mt-2" onClick={importPaste} disabled={!paste.trim()}>Add these rows</button>
        </details>
        <div className="mt-4 flex justify-end gap-2">
          <button className="btn-outline" onClick={onClose}>Cancel</button>
          <button className="btn-primary" onClick={() => save.mutate()} disabled={save.isPending}>{save.isPending ? "Saving…" : "Save chapters"}</button>
        </div>
      </div>
    </div>
  );
}
