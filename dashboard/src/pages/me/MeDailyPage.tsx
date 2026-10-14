import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import clsx from "clsx";
import { BarChart3, CalendarDays, Copy, ExternalLink, Link2, Lock, Plus, QrCode, Trash2, Unlock } from "lucide-react";
import { ApiError, api, fmtDate } from "../../api/client";
import type { MeDailyAgendaItem, MeDailyRound } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { Card, Empty, ErrorBox, Field, KpiTile, Spinner } from "../../components/ui";
import QrDialog from "../../components/QrDialog";

interface Form { id?: number; title: string; phase: "MASTER" | "TOT" | "FIELD"; period_start: string; period_end: string; description: string }
const empty: Form = { title: "", phase: "FIELD", period_start: "", period_end: "", description: "" };
export const PHASE_LABEL: Record<string, string> = { MASTER: "Master Training", TOT: "Training of Trainers", FIELD: "Field Staff Training" };

/** The link lead facilitators use: the configured evaluation address (censusme.statistics.sl), or this dashboard's own address. */
export const dailyLink = (r: { token: string; share_url: string | null }) => r.share_url ?? `${window.location.origin}/daily/${r.token}`;

/** Daily Evaluation: the Daily Facilitator Report, one per class per day, grouped per training with its agenda. */
export default function MeDailyPage() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const list = useQuery({ queryKey: ["me-daily", "rounds"], queryFn: () => api.get<MeDailyRound[]>("/me/daily/rounds") });
  const [form, setForm] = useState<Form | null>(null);
  const [agendaFor, setAgendaFor] = useState<MeDailyRound | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [copied, setCopied] = useState<number | null>(null);
  const [qr, setQr] = useState<MeDailyRound | null>(null);
  const invalidate = () => qc.invalidateQueries({ queryKey: ["me-daily"] });
  const save = useMutation({
    mutationFn: (f: Form) => {
      const body = { title: f.title, phase: f.phase, period_start: f.period_start || null, period_end: f.period_end || null, description: f.description || null };
      return f.id ? api.patch<MeDailyRound>(`/me/daily/rounds/${f.id}`, body) : api.post<MeDailyRound>("/me/daily/rounds", body);
    },
    onSuccess: (r, f) => { invalidate(); setForm(null); setError(null); if (!f.id) setAgendaFor(r); },
    onError: setError,
  });
  const toggle = useMutation({ mutationFn: (r: MeDailyRound) => api.patch<MeDailyRound>(`/me/daily/rounds/${r.id}`, { status: r.status === "OPEN" ? "CLOSED" : "OPEN" }), onSuccess: invalidate, onError: setError });
  const remove = useMutation({ mutationFn: (r: MeDailyRound) => api.delete(`/me/daily/rounds/${r.id}`), onSuccess: invalidate, onError: setError });
  const copy = async (r: MeDailyRound) => {
    try { await navigator.clipboard.writeText(dailyLink(r)); setCopied(r.id); setTimeout(() => setCopied(null), 2000); } catch { prompt("Copy this link", dailyLink(r)); }
  };
  const data = list.data ?? [];
  const totals = data.reduce((t, r) => ({ reports: t.reports + r.reports, low: t.low + r.low_scores, open: t.open + r.open_escalations }), { reports: 0, low: 0, open: 0 });

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Daily Evaluation</h1>
          <p className="text-sm text-slate-500">Daily Facilitator Report. Create one entry per training, load its agenda, share the link or QR code with the lead facilitators, and follow content coverage, learning, facilitation quality, materials issues, logistics and escalations class by class, day by day.</p>
        </div>
        {can("me_daily.manage") && <button className="btn-primary" onClick={() => { setForm(empty); setError(null); }}><Plus size={16} /> New daily evaluation</button>}
      </div>
      <ErrorBox error={error instanceof ApiError ? error.message : error} />
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <KpiTile label="Trainings" value={data.length} sub={`${data.filter((r) => r.status === "OPEN").length} open`} />
        <KpiTile label="Daily reports received" value={totals.reports} tone="green" />
        <KpiTile label="Reports with a score of 1 or 2" value={totals.low} tone={totals.low ? "red" : "navy"} sub="any facilitation criterion" />
        <KpiTile label="Open escalations" value={totals.open} tone={totals.open ? "amber" : "navy"} sub="management / CCIT action pending" />
      </div>
      {list.isLoading ? <Spinner /> : data.length === 0 ? (
        <Card><Empty text="No daily evaluation yet. Create one per training, load its agenda, then share its link with the lead facilitators." /></Card>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {data.map((r) => (
            <Card key={r.id}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <Link to={`/me/daily/${r.id}`} className="text-lg font-semibold text-navy hover:underline">{r.title}</Link>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
                    <span className="rounded-full bg-violet-100 px-2 py-0.5 font-semibold text-violet-800">{PHASE_LABEL[r.phase] ?? r.phase}</span>
                    <span className={clsx("rounded-full px-2 py-0.5 font-semibold", r.status === "OPEN" ? "bg-green-100 text-green-800" : "bg-slate-200 text-slate-700")}>{r.status === "OPEN" ? "Open" : "Closed"}</span>
                    {(r.period_start || r.period_end) && <span className="text-slate-500">{fmtDate(r.period_start)}{r.period_end ? ` – ${fmtDate(r.period_end)}` : ""}</span>}
                    <span className={clsx("rounded-full px-2 py-0.5", r.agenda_items ? "bg-sky-100 text-sky-800" : "bg-amber-100 text-amber-800")}>{r.agenda_items ? `Agenda: ${r.agenda_items} sessions, ${r.agenda_days} days` : "No agenda yet"}</span>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-2xl font-bold text-navy">{r.reports}</div>
                  <div className="text-xs text-slate-500">daily reports{r.last_report_date ? ` · last ${fmtDate(r.last_report_date)}` : ""}</div>
                </div>
              </div>
              {r.description && <p className="mt-2 text-sm text-slate-600">{r.description}</p>}
              <div className="mt-3 grid grid-cols-4 gap-2 text-center text-sm">
                <div className="rounded-md bg-slate-50 py-2"><div className="font-semibold">{r.classes}</div><div className="text-xs text-slate-500">classes · {r.days} days</div></div>
                <div className="rounded-md bg-slate-50 py-2"><div className="font-semibold">{r.delivered_pct === null ? "—" : `${r.delivered_pct}%`}</div><div className="text-xs text-slate-500">sessions delivered</div></div>
                <div className={clsx("rounded-md py-2", r.overall_mean !== null && r.overall_mean < 3 ? "bg-red-50" : "bg-slate-50")}><div className="font-semibold">{r.overall_mean === null ? "—" : r.overall_mean.toFixed(2)}</div><div className="text-xs text-slate-500">overall rating (1–5)</div></div>
                <div className={clsx("rounded-md py-2", r.open_escalations ? "bg-amber-50" : "bg-slate-50")}><div className={clsx("font-semibold", r.open_escalations && "text-amber-800")}>{r.open_escalations}</div><div className="text-xs text-slate-500">open escalations</div></div>
              </div>
              <div className="mt-3 flex items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-2 py-1.5 text-xs">
                <Link2 size={14} className="shrink-0 text-slate-400" />
                <span className="truncate font-mono text-slate-600">{dailyLink(r)}</span>
                <button className="ml-auto shrink-0 text-navy" onClick={() => copy(r)} title="Copy the link for the lead facilitators"><Copy size={14} /> {copied === r.id ? "Copied" : "Copy"}</button>
                <a className="shrink-0 text-navy" href={dailyLink(r)} target="_blank" rel="noreferrer" title="Open the form page"><ExternalLink size={14} /></a>
                <button className="shrink-0 text-navy" onClick={() => setQr(r)} title="QR code"><QrCode size={14} /></button>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <Link to={`/me/daily/${r.id}`} className="btn-primary"><BarChart3 size={16} /> Reports</Link>
                {can("me_daily.manage") && <button className="btn-outline" onClick={() => setAgendaFor(r)}><CalendarDays size={16} /> Agenda</button>}
                <button className="btn-outline" onClick={() => setQr(r)}><QrCode size={16} /> QR code</button>
                {can("me_daily.manage") && (
                  <>
                    <button className="btn-outline" onClick={() => { setForm({ id: r.id, title: r.title, phase: r.phase, period_start: r.period_start ?? "", period_end: r.period_end ?? "", description: r.description ?? "" }); setError(null); }}>Edit</button>
                    <button className="btn-outline" onClick={() => { if (confirm(`${r.status === "OPEN" ? "Close" : "Reopen"} "${r.title}"?${r.status === "OPEN" ? " Lead facilitators cannot send reports while it is closed." : ""}`)) toggle.mutate(r); }}>
                      {r.status === "OPEN" ? <><Lock size={16} /> Close</> : <><Unlock size={16} /> Reopen</>}
                    </button>
                    {r.reports === 0 && <button className="btn-outline text-red-700" onClick={() => { if (confirm(`Delete "${r.title}"? It has no reports; its link will stop working.`)) remove.mutate(r); }}><Trash2 size={16} /> Delete</button>}
                  </>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}
      {qr && <QrDialog url={dailyLink(qr)} title={qr.title} subtitle="Daily Facilitator Report · one report per class each day" onClose={() => setQr(null)} />}
      {agendaFor && <AgendaDialog round={agendaFor} onClose={() => { setAgendaFor(null); invalidate(); }} />}
      {form && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 p-4" onClick={() => setForm(null)}>
          <form className="w-full max-w-lg rounded-lg bg-white p-5 shadow-xl" onClick={(e) => e.stopPropagation()} onSubmit={(e) => { e.preventDefault(); save.mutate(form); }}>
            <h2 className="mb-3 text-lg font-semibold">{form.id ? "Edit daily evaluation" : "New daily evaluation"}</h2>
            <div className="grid gap-3">
              <Field label="Training"><input className="input" required minLength={3} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="e.g. Field staff training, Southern region" /></Field>
              <Field label="Training phase / mode (pre-selected on the form)">
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
              <Field label="Note shown to lead facilitators (optional)"><textarea className="input" rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="e.g. One report per class each day, within 2 hours of class close." /></Field>
            </div>
            <ErrorBox error={error instanceof ApiError ? error.message : error} />
            <div className="mt-4 flex justify-end gap-2">
              <button type="button" className="btn-outline" onClick={() => setForm(null)}>Cancel</button>
              <button className="btn-primary" disabled={save.isPending}>{save.isPending ? "Saving…" : form.id ? "Save" : "Create, then load the agenda"}</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

type Row = { day: string; topic: string; planned_start: string; planned_end: string };

/** The agenda editor: the sessions per training day that the form lists in section C (drop-down of topics). */
function AgendaDialog({ round, onClose }: { round: MeDailyRound; onClose: () => void }) {
  const current = useQuery({ queryKey: ["me-daily", "agenda", round.id], queryFn: () => api.get<MeDailyAgendaItem[]>(`/me/daily/rounds/${round.id}/agenda`) });
  const [rows, setRows] = useState<Row[] | null>(null);
  const [paste, setPaste] = useState("");
  const [error, setError] = useState<unknown>(null);
  const data: Row[] = rows ?? (current.data ?? []).map((a) => ({ day: String(a.day), topic: a.topic, planned_start: a.planned_start ?? "", planned_end: a.planned_end ?? "" }));
  const setRow = (i: number, patch: Partial<Row>) => setRows(data.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  const save = useMutation({
    mutationFn: () => api.put<MeDailyAgendaItem[]>(`/me/daily/rounds/${round.id}/agenda`, data.filter((r) => r.topic.trim() && Number(r.day) >= 1).map((r) => ({ day: Number(r.day), topic: r.topic.trim(), planned_start: r.planned_start || null, planned_end: r.planned_end || null }))),
    onSuccess: onClose,
    onError: setError,
  });
  const importPaste = () => {
    // one session per line: day<TAB or comma>topic<TAB>start<TAB>end  — start/end optional
    const parsed: Row[] = [];
    for (const line of paste.split(/\r?\n/)) {
      const parts = line.split(/\t|;|,(?=\s*\d{1,2}(?::\d{2})?\s*(?:,|$))|\|/).map((x) => x.trim());
      if (parts.length < 2) continue;
      const [day, topic, start = "", end = ""] = parts;
      if (!/^\d+$/.test(day) || !topic) continue;
      parsed.push({ day, topic, planned_start: start.slice(0, 5), planned_end: end.slice(0, 5) });
    }
    if (parsed.length) { setRows([...data, ...parsed]); setPaste(""); }
  };
  const days = Array.from(new Set(data.map((r) => Number(r.day)).filter((d) => d >= 1))).sort((a, b) => a - b);
  return (
    <div className="fixed inset-0 z-40 flex items-start justify-center overflow-y-auto bg-black/40 p-4" onClick={onClose}>
      <div className="w-full max-w-4xl rounded-lg bg-white p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="mb-1 flex items-center justify-between"><h2 className="text-lg font-semibold">Agenda · {round.title}</h2><button className="btn-outline" onClick={onClose}>Close</button></div>
        <p className="mb-3 text-sm text-slate-500">One row per session. On the form, the facilitator picks the training day and the day's sessions appear with their planned times; the topics also feed the "carried to next day" and "hardest topics" drop-downs. {days.length ? `${data.length} sessions over ${days.length} days.` : ""}</p>
        <ErrorBox error={error instanceof ApiError ? error.message : error} />
        {current.isLoading ? <Spinner /> : (
          <div className="overflow-x-auto">
            <table className="table">
              <thead><tr><th className="w-20">Day</th><th>Session / topic</th><th className="w-32">Planned start</th><th className="w-32">Planned end</th><th className="w-10" /></tr></thead>
              <tbody>
                {data.map((r, i) => (
                  <tr key={i}>
                    <td><input className="input" type="number" min={1} max={60} value={r.day} onChange={(e) => setRow(i, { day: e.target.value })} /></td>
                    <td><input className="input" value={r.topic} onChange={(e) => setRow(i, { topic: e.target.value })} placeholder="e.g. Household listing on CAPI" /></td>
                    <td><input className="input" type="time" value={r.planned_start} onChange={(e) => setRow(i, { planned_start: e.target.value })} /></td>
                    <td><input className="input" type="time" value={r.planned_end} onChange={(e) => setRow(i, { planned_end: e.target.value })} /></td>
                    <td><button className="text-red-700" title="Remove" onClick={() => setRows(data.filter((_, j) => j !== i))}><Trash2 size={14} /></button></td>
                  </tr>
                ))}
                {data.length === 0 && <tr><td colSpan={5}><Empty text="No session yet. Add rows, or paste the agenda below." /></td></tr>}
              </tbody>
            </table>
          </div>
        )}
        <div className="mt-2 flex flex-wrap gap-2">
          <button className="btn-outline" onClick={() => setRows([...data, { day: String(days.length ? days[days.length - 1] : 1), topic: "", planned_start: "", planned_end: "" }])}><Plus size={16} /> Add session</button>
        </div>
        <details className="mt-3 rounded-md border border-slate-200 p-3 text-sm">
          <summary className="cursor-pointer font-medium text-slate-700">Paste the agenda from Excel or Word</summary>
          <p className="mt-1 text-xs text-slate-500">One session per line: day, topic, planned start, planned end (tab- or semicolon-separated; times optional). For example: <code>1 ⇥ Census concepts and reference night ⇥ 09:00 ⇥ 10:30</code></p>
          <textarea className="input mt-2 font-mono text-xs" rows={5} value={paste} onChange={(e) => setPaste(e.target.value)} />
          <button className="btn-outline mt-2" onClick={importPaste} disabled={!paste.trim()}>Add these rows</button>
        </details>
        <div className="mt-4 flex justify-end gap-2">
          <button className="btn-outline" onClick={onClose}>Cancel</button>
          <button className="btn-primary" onClick={() => save.mutate()} disabled={save.isPending}>{save.isPending ? "Saving…" : "Save agenda"}</button>
        </div>
      </div>
    </div>
  );
}
