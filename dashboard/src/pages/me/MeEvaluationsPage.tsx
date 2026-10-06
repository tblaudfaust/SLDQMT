import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import clsx from "clsx";
import { BarChart3, Copy, ExternalLink, Link2, Lock, Plus, Trash2, Unlock } from "lucide-react";
import { ApiError, api, fmtDate } from "../../api/client";
import type { MeEvaluation } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { Card, Empty, ErrorBox, Field, KpiTile, Spinner } from "../../components/ui";

interface Form { id?: number; title: string; training_mode: "ONLINE" | "IN_PERSON"; period_start: string; period_end: string; description: string }
const empty: Form = { title: "", training_mode: "ONLINE", period_start: "", period_end: "", description: "" };

/** The link to send to trainees and trainers: the configured evaluation address (censusme.statistics.sl), or this dashboard's own address. */
export const evaluationLink = (e: { token: string; share_url: string | null }) => e.share_url ?? `${window.location.origin}/evaluate/${e.token}`;

/** Monitoring & Evaluation: training evaluations shared by link with trainees and trainers. */
export default function MeEvaluationsPage() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const list = useQuery({ queryKey: ["me", "evaluations"], queryFn: () => api.get<MeEvaluation[]>("/me/evaluations") });
  const [form, setForm] = useState<Form | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [copied, setCopied] = useState<number | null>(null);
  const invalidate = () => qc.invalidateQueries({ queryKey: ["me"] });
  const save = useMutation({
    mutationFn: (f: Form) => {
      const body = { title: f.title, training_mode: f.training_mode, period_start: f.period_start || null, period_end: f.period_end || null, description: f.description || null };
      return f.id ? api.patch<MeEvaluation>(`/me/evaluations/${f.id}`, body) : api.post<MeEvaluation>("/me/evaluations", body);
    },
    onSuccess: () => { invalidate(); setForm(null); setError(null); },
    onError: setError,
  });
  const toggle = useMutation({
    mutationFn: (e: MeEvaluation) => api.patch<MeEvaluation>(`/me/evaluations/${e.id}`, { status: e.status === "OPEN" ? "CLOSED" : "OPEN" }),
    onSuccess: invalidate,
    onError: setError,
  });
  const remove = useMutation({
    mutationFn: (e: MeEvaluation) => api.delete(`/me/evaluations/${e.id}`),
    onSuccess: invalidate,
    onError: setError,
  });
  const copy = async (e: MeEvaluation) => {
    try { await navigator.clipboard.writeText(evaluationLink(e)); setCopied(e.id); setTimeout(() => setCopied(null), 2000); } catch { prompt("Copy this link", evaluationLink(e)); }
  };
  const data = list.data ?? [];
  const totals = data.reduce((t, e) => ({ submitted: t.submitted + e.submitted, registered: t.registered + e.registered, trainees: t.trainees + e.trainees, trainers: t.trainers + e.trainers }), { submitted: 0, registered: 0, trainees: 0, trainers: 0 });

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Training evaluations</h1>
          <p className="text-sm text-slate-500">2026 PHC training evaluation form. Create an evaluation per training round, share its link with trainees and trainers, and follow the results as they come in.</p>
        </div>
        {can("me.manage") && <button className="btn-primary" onClick={() => { setForm(empty); setError(null); }}><Plus size={16} /> New evaluation</button>}
      </div>
      <ErrorBox error={error instanceof ApiError ? error.message : error} />
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <KpiTile label="Evaluations" value={data.length} sub={`${data.filter((e) => e.status === "OPEN").length} open`} />
        <KpiTile label="Responses" value={totals.submitted} tone="green" sub={`of ${totals.registered} registered`} />
        <KpiTile label="Trainees" value={totals.trainees} />
        <KpiTile label="Trainers" value={totals.trainers} tone="amber" />
      </div>
      {list.isLoading ? <Spinner /> : data.length === 0 ? (
        <Card><Empty text="No evaluation yet. Create one, then share its link." /></Card>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {data.map((e) => (
            <Card key={e.id} className="relative">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <Link to={`/me/evaluations/${e.id}`} className="text-lg font-semibold text-navy hover:underline">{e.title}</Link>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
                    <span className={clsx("rounded-full px-2 py-0.5 font-semibold", e.training_mode === "ONLINE" ? "bg-sky-100 text-sky-800" : "bg-emerald-100 text-emerald-800")}>{e.training_mode === "ONLINE" ? "Online / self-paced" : "In-person"}</span>
                    <span className={clsx("rounded-full px-2 py-0.5 font-semibold", e.status === "OPEN" ? "bg-green-100 text-green-800" : "bg-slate-200 text-slate-700")}>{e.status === "OPEN" ? "Open" : "Closed"}</span>
                    {(e.period_start || e.period_end) && <span className="text-slate-500">{fmtDate(e.period_start)}{e.period_end ? ` – ${fmtDate(e.period_end)}` : ""}</span>}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-2xl font-bold text-navy">{e.submitted}</div>
                  <div className="text-xs text-slate-500">responses · {e.registered} registered</div>
                </div>
              </div>
              {e.description && <p className="mt-2 text-sm text-slate-600">{e.description}</p>}
              <div className="mt-3 grid grid-cols-3 gap-2 text-center text-sm">
                <div className="rounded-md bg-slate-50 py-2"><div className="font-semibold">{e.trainees}</div><div className="text-xs text-slate-500">trainees</div></div>
                <div className="rounded-md bg-slate-50 py-2"><div className="font-semibold">{e.trainers}</div><div className="text-xs text-slate-500">trainers</div></div>
                <div className="rounded-md bg-slate-50 py-2"><div className="font-semibold">{e.registered ? Math.round((100 * e.submitted) / e.registered) : 0}%</div><div className="text-xs text-slate-500">completion</div></div>
              </div>
              <div className="mt-3 flex items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-2 py-1.5 text-xs">
                <Link2 size={14} className="shrink-0 text-slate-400" />
                <span className="truncate font-mono text-slate-600">{evaluationLink(e)}</span>
                <button className="ml-auto shrink-0 text-navy" onClick={() => copy(e)} title="Copy the link to share"><Copy size={14} /> {copied === e.id ? "Copied" : "Copy"}</button>
                <a className="shrink-0 text-navy" href={evaluationLink(e)} target="_blank" rel="noreferrer" title="Open the evaluation page"><ExternalLink size={14} /></a>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <Link to={`/me/evaluations/${e.id}`} className="btn-primary"><BarChart3 size={16} /> Results</Link>
                {can("me.manage") && (
                  <>
                    <button className="btn-outline" onClick={() => { setForm({ id: e.id, title: e.title, training_mode: e.training_mode, period_start: e.period_start ?? "", period_end: e.period_end ?? "", description: e.description ?? "" }); setError(null); }}>Edit</button>
                    <button className="btn-outline" onClick={() => { if (confirm(`${e.status === "OPEN" ? "Close" : "Reopen"} "${e.title}"?${e.status === "OPEN" ? " Nobody can register or submit while it is closed." : ""}`)) toggle.mutate(e); }}>
                      {e.status === "OPEN" ? <><Lock size={16} /> Close</> : <><Unlock size={16} /> Reopen</>}
                    </button>
                    {e.submitted === 0 && <button className="btn-outline text-red-700" onClick={() => { if (confirm(`Delete "${e.title}"? It has no responses; its link will stop working.`)) remove.mutate(e); }}><Trash2 size={16} /> Delete</button>}
                  </>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}
      {form && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 p-4" onClick={() => setForm(null)}>
          <form className="w-full max-w-lg rounded-lg bg-white p-5 shadow-xl" onClick={(e) => e.stopPropagation()} onSubmit={(e) => { e.preventDefault(); save.mutate(form); }}>
            <h2 className="mb-3 text-lg font-semibold">{form.id ? "Edit evaluation" : "New evaluation"}</h2>
            <div className="grid gap-3">
              <Field label="Title"><input className="input" required minLength={3} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="e.g. Master Trainers and DQM online training, cohort 1" /></Field>
              <Field label="Training mode">
                <div className="grid grid-cols-2 gap-2">
                  {(["ONLINE", "IN_PERSON"] as const).map((m) => (
                    <button type="button" key={m} onClick={() => setForm({ ...form, training_mode: m })}
                      className={clsx("rounded-md border px-3 py-2 text-sm font-medium", form.training_mode === m ? "border-navy bg-navy text-white" : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50")}>
                      {m === "ONLINE" ? "Online / self-paced" : "In-person"}
                    </button>
                  ))}
                </div>
                <p className="mt-1 text-xs text-slate-500">In-person evaluations skip the digital-access questions (Section B) and the device question; the other sections are the same.</p>
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Training period from"><input className="input" type="date" value={form.period_start} onChange={(e) => setForm({ ...form, period_start: e.target.value })} /></Field>
                <Field label="to"><input className="input" type="date" value={form.period_end} onChange={(e) => setForm({ ...form, period_end: e.target.value })} /></Field>
              </div>
              <Field label="Introduction shown to respondents (optional)"><textarea className="input" rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Purpose of the evaluation, who should answer, deadline…" /></Field>
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
