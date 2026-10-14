import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import clsx from "clsx";
import { BarChart3, Copy, ExternalLink, Link2, Lock, Plus, QrCode, Trash2, Unlock } from "lucide-react";
import { ApiError, api, fmtDate } from "../../api/client";
import type { MeDailyRound } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { Card, Empty, ErrorBox, Field, KpiTile, Spinner } from "../../components/ui";
import QrDialog from "../../components/QrDialog";

interface Form { id?: number; title: string; phase: "MASTER" | "TOT" | "FIELD"; period_start: string; period_end: string; description: string }
const empty: Form = { title: "", phase: "FIELD", period_start: "", period_end: "", description: "" };
export const PHASE_LABEL: Record<string, string> = { MASTER: "Master training", TOT: "Training of trainers", FIELD: "Field staff training" };

/** The link lead trainers use: the configured evaluation address (censusme.statistics.sl), or this dashboard's own address. */
export const dailyLink = (r: { token: string; share_url: string | null }) => r.share_url ?? `${window.location.origin}/daily/${r.token}`;

/** Daily Evaluation: the Daily Trainer Class Evaluation, one form per class per day, grouped per training. */
export default function MeDailyPage() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const list = useQuery({ queryKey: ["me-daily", "rounds"], queryFn: () => api.get<MeDailyRound[]>("/me/daily/rounds") });
  const [form, setForm] = useState<Form | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [copied, setCopied] = useState<number | null>(null);
  const [qr, setQr] = useState<MeDailyRound | null>(null);
  const invalidate = () => qc.invalidateQueries({ queryKey: ["me-daily"] });
  const save = useMutation({
    mutationFn: (f: Form) => {
      const body = { title: f.title, phase: f.phase, period_start: f.period_start || null, period_end: f.period_end || null, description: f.description || null };
      return f.id ? api.patch<MeDailyRound>(`/me/daily/rounds/${f.id}`, body) : api.post<MeDailyRound>("/me/daily/rounds", body);
    },
    onSuccess: () => { invalidate(); setForm(null); setError(null); },
    onError: setError,
  });
  const toggle = useMutation({ mutationFn: (r: MeDailyRound) => api.patch<MeDailyRound>(`/me/daily/rounds/${r.id}`, { status: r.status === "OPEN" ? "CLOSED" : "OPEN" }), onSuccess: invalidate, onError: setError });
  const remove = useMutation({ mutationFn: (r: MeDailyRound) => api.delete(`/me/daily/rounds/${r.id}`), onSuccess: invalidate, onError: setError });
  const copy = async (r: MeDailyRound) => {
    try { await navigator.clipboard.writeText(dailyLink(r)); setCopied(r.id); setTimeout(() => setCopied(null), 2000); } catch { prompt("Copy this link", dailyLink(r)); }
  };
  const data = list.data ?? [];
  const totals = data.reduce((t, r) => ({ reports: t.reports + r.reports, major: t.major + r.major_gaps, help: t.help + r.help_requests }), { reports: 0, major: 0, help: 0 });

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Daily Evaluation</h1>
          <p className="text-sm text-slate-500">Daily Trainer Class Evaluation. Create one entry per training, share its link with the lead trainers, and follow attendance, agenda coverage, learning evidence, delivery and support problems class by class, day by day.</p>
        </div>
        {can("me_daily.manage") && <button className="btn-primary" onClick={() => { setForm(empty); setError(null); }}><Plus size={16} /> New daily evaluation</button>}
      </div>
      <ErrorBox error={error instanceof ApiError ? error.message : error} />
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <KpiTile label="Trainings" value={data.length} sub={`${data.filter((r) => r.status === "OPEN").length} open`} />
        <KpiTile label="Daily reports received" value={totals.reports} tone="green" />
        <KpiTile label="Reports with Major gaps" value={totals.major} tone={totals.major ? "red" : "navy"} sub="at least one delivery area rated Major gaps" />
        <KpiTile label="Management help requested" value={totals.help} tone={totals.help ? "amber" : "navy"} />
      </div>
      {list.isLoading ? <Spinner /> : data.length === 0 ? (
        <Card><Empty text="No daily evaluation yet. Create one per training, then share its link with the lead trainers." /></Card>
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
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-2xl font-bold text-navy">{r.reports}</div>
                  <div className="text-xs text-slate-500">daily reports{r.last_report_date ? ` · last ${fmtDate(r.last_report_date)}` : ""}</div>
                </div>
              </div>
              {r.description && <p className="mt-2 text-sm text-slate-600">{r.description}</p>}
              <div className="mt-3 grid grid-cols-4 gap-2 text-center text-sm">
                <div className="rounded-md bg-slate-50 py-2"><div className="font-semibold">{r.classes}</div><div className="text-xs text-slate-500">classes</div></div>
                <div className="rounded-md bg-slate-50 py-2"><div className="font-semibold">{r.days}</div><div className="text-xs text-slate-500">training days</div></div>
                <div className="rounded-md bg-slate-50 py-2"><div className="font-semibold">{r.attendance_rate === null ? "—" : `${r.attendance_rate}%`}</div><div className="text-xs text-slate-500">attendance</div></div>
                <div className={clsx("rounded-md py-2", r.major_gaps ? "bg-red-50" : "bg-slate-50")}><div className={clsx("font-semibold", r.major_gaps && "text-red-700")}>{r.major_gaps}</div><div className="text-xs text-slate-500">major gaps</div></div>
              </div>
              <div className="mt-3 flex items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-2 py-1.5 text-xs">
                <Link2 size={14} className="shrink-0 text-slate-400" />
                <span className="truncate font-mono text-slate-600">{dailyLink(r)}</span>
                <button className="ml-auto shrink-0 text-navy" onClick={() => copy(r)} title="Copy the link for the lead trainers"><Copy size={14} /> {copied === r.id ? "Copied" : "Copy"}</button>
                <a className="shrink-0 text-navy" href={dailyLink(r)} target="_blank" rel="noreferrer" title="Open the form page"><ExternalLink size={14} /></a>
                <button className="shrink-0 text-navy" onClick={() => setQr(r)} title="QR code for the lead trainers"><QrCode size={14} /></button>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <Link to={`/me/daily/${r.id}`} className="btn-primary"><BarChart3 size={16} /> Reports</Link>
                <button className="btn-outline" onClick={() => setQr(r)}><QrCode size={16} /> QR code</button>
                {can("me_daily.manage") && (
                  <>
                    <button className="btn-outline" onClick={() => { setForm({ id: r.id, title: r.title, phase: r.phase, period_start: r.period_start ?? "", period_end: r.period_end ?? "", description: r.description ?? "" }); setError(null); }}>Edit</button>
                    <button className="btn-outline" onClick={() => { if (confirm(`${r.status === "OPEN" ? "Close" : "Reopen"} "${r.title}"?${r.status === "OPEN" ? " Lead trainers cannot send reports while it is closed." : ""}`)) toggle.mutate(r); }}>
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
      {qr && <QrDialog url={dailyLink(qr)} title={qr.title} subtitle="Daily Trainer Class Evaluation · one form per class each day" onClose={() => setQr(null)} />}
      {form && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 p-4" onClick={() => setForm(null)}>
          <form className="w-full max-w-lg rounded-lg bg-white p-5 shadow-xl" onClick={(e) => e.stopPropagation()} onSubmit={(e) => { e.preventDefault(); save.mutate(form); }}>
            <h2 className="mb-3 text-lg font-semibold">{form.id ? "Edit daily evaluation" : "New daily evaluation"}</h2>
            <div className="grid gap-3">
              <Field label="Training"><input className="input" required minLength={3} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="e.g. Field staff training, Southern region" /></Field>
              <Field label="Phase (pre-selected on the form; the trainer can change it)">
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
              <Field label="Note shown to lead trainers (optional)"><textarea className="input" rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="e.g. One form per class each day, within 2 hours of class close. Urgent issues: call the coordinator." /></Field>
            </div>
            <ErrorBox error={error instanceof ApiError ? error.message : error} />
            <div className="mt-4 flex justify-end gap-2">
              <button type="button" className="btn-outline" onClick={() => setForm(null)}>Cancel</button>
              <button className="btn-primary" disabled={save.isPending}>{save.isPending ? "Saving…" : form.id ? "Save" : "Create and get the link"}</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
