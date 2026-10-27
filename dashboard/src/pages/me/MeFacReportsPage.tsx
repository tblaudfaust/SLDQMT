import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import clsx from "clsx";
import { BarChart3, Copy, ExternalLink, Plus, QrCode } from "lucide-react";
import { ApiError, api, fmtDate } from "../../api/client";
import type { MeDailyAgendaTemplate, MeFacReportRound, MeFacRound } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { Card, Empty, ErrorBox, Field, Spinner } from "../../components/ui";
import QrDialog from "../../components/QrDialog";
import { CountCard } from "./kpi/kpiUi";
import { PHASE_LABEL } from "./MeFacPage";

/** The link the Lead Facilitators use: the configured public address (censusme.statistics.sl) or this dashboard's own. */
export const reportLink = (r: MeFacReportRound) => r.report_url ?? `${window.location.origin}/report/${r.round.token}`;

/** Daily Facilitator's Report: one entry per training (shared with the facilitator assessment), the public link and QR code, and the feedback dashboard. */
export default function MeFacReportsPage() {
  const { can } = useAuth();
  const list = useQuery({ queryKey: ["me-facrep", "rounds"], queryFn: () => api.get<MeFacReportRound[]>("/me/facreports/rounds") });
  const [creating, setCreating] = useState(false);
  const [copied, setCopied] = useState<number | null>(null);
  const [qr, setQr] = useState<MeFacReportRound | null>(null);
  const data = list.data ?? [];
  const totals = data.reduce((t, r) => ({ reports: t.reports + r.reports, halls: t.halls + r.halls, attention: t.attention + r.attention }), { reports: 0, halls: 0, attention: 0 });
  const copy = async (r: MeFacReportRound) => { try { await navigator.clipboard.writeText(reportLink(r)); setCopied(r.round.id); setTimeout(() => setCopied(null), 2000); } catch { prompt("Copy this link", reportLink(r)); } };

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Facilitator daily report</h1>
          <p className="text-sm text-slate-500">Daily Facilitator's Report, Training of Trainers (in-person): one report per hall per day by the Lead Facilitator, for the Training Coordinator and the CTA. Share the link or QR code of the training with the Lead Facilitators; the trainings and their chapters per day are the ones of the Facilitator assessment.</p>
        </div>
        {can("me_fac.manage") && (
          <div className="flex flex-wrap gap-2">
            <Link to="/me/facilitators" className="btn-outline">Manage trainings and chapters</Link>
            <button className="btn-primary" onClick={() => setCreating(true)}><Plus size={16} /> New training</button>
          </div>
        )}
      </div>
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <CountCard label="Trainings" value={data.length} sub={`${data.filter((r) => r.round.status === "OPEN").length} open`} />
        <CountCard label="Reports received" value={totals.reports} sub={`${totals.halls} halls`} tone="green" />
        <CountCard label="Need attention" value={totals.attention} sub="low ratings, sessions not delivered, poor attendance, power or internet" tone={totals.attention ? "amber" : "navy"} />
        <CountCard label="Attendance" value={data.length && data.some((r) => r.attendance_pct !== null) ? `${Math.round(data.filter((r) => r.attendance_pct !== null).reduce((s, r) => s + (r.attendance_pct ?? 0), 0) / data.filter((r) => r.attendance_pct !== null).length)}%` : "—"} sub="mean of the trainings" />
      </div>
      {list.isLoading ? <Spinner /> : data.length === 0 ? (
        <Card><Empty text={can("me_fac.manage") ? "No training yet. Use New training (the 2026 agenda loads its chapters per day); its link then serves both the trainer ratings and the daily facilitator reports." : "No training yet. Ask the M&E team to create the training."} /></Card>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {data.map((r) => (
            <Card key={r.round.id}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <Link to={`/me/facreports/${r.round.id}`} className="text-lg font-semibold text-navy hover:underline">{r.round.title}</Link>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
                    <span className="rounded-full bg-violet-100 px-2 py-0.5 font-semibold text-violet-800">{PHASE_LABEL[r.round.phase] ?? r.round.phase}</span>
                    <span className={clsx("rounded-full px-2 py-0.5 font-semibold", r.round.status === "OPEN" ? "bg-green-100 text-green-800" : "bg-slate-200 text-slate-700")}>{r.round.status === "OPEN" ? "Open" : "Closed"}</span>
                    {(r.round.period_start || r.round.period_end) && <span className="text-slate-500">{fmtDate(r.round.period_start)}{r.round.period_end ? ` – ${fmtDate(r.round.period_end)}` : ""}</span>}
                    <span className="text-slate-500">{r.round.agenda_items} chapters, {r.round.agenda_days} days</span>
                  </div>
                </div>
                <Link to={`/me/facreports/${r.round.id}`} className="btn-primary shrink-0"><BarChart3 size={16} /> Dashboard</Link>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2 text-center sm:grid-cols-4">
                {[["Reports", r.reports], ["Halls", r.halls], ["Attendance", r.attendance_pct === null ? "—" : `${Math.round(r.attendance_pct)}%`], ["Class rating", r.mean_rating === null ? "—" : `${r.mean_rating.toFixed(1)} / 5`]].map(([l, v]) => <div key={String(l)} className="rounded-lg bg-slate-50 px-2 py-2"><div className="text-xl font-bold text-navy">{v}</div><div className="text-[11px] uppercase tracking-wide text-slate-500">{l}</div></div>)}
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
                <span className="text-xs text-slate-500">{r.venues} venue{r.venues === 1 ? "" : "s"} · {r.days} day{r.days === 1 ? "" : "s"}{r.last_date ? ` · last report ${fmtDate(r.last_date)}` : ""}{r.attention ? ` · ${r.attention} need attention` : ""}</span>
                <span className="flex-1" />
                <button className="btn-outline py-1" onClick={() => copy(r)}><Copy size={14} /> {copied === r.round.id ? "Copied" : "Copy link"}</button>
                <a className="btn-outline py-1" href={reportLink(r)} target="_blank" rel="noreferrer"><ExternalLink size={14} /> Open the form</a>
                <button className="btn-outline py-1" onClick={() => setQr(r)}><QrCode size={14} /> QR code</button>
              </div>
            </Card>
          ))}
        </div>
      )}
      {creating && <NewTrainingDialog onClose={() => setCreating(false)} />}
      {qr && <QrDialog url={reportLink(qr)} title={qr.round.title} subtitle="Daily Facilitator's Report · the Lead Facilitator of each hall sends one report per day" onClose={() => setQr(null)} />}
    </div>
  );
}

const PHASES = ["TOT", "MASTER", "FIELD"] as const;
type NewForm = { title: string; phase: (typeof PHASES)[number]; period_start: string; period_end: string; description: string; agenda_template: string };

/** Create a training from this page (the same entry as under Facilitator assessment): Training of Trainers by default, with the 2026 agenda loaded. */
function NewTrainingDialog({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const templates = useQuery({ queryKey: ["me-fac", "agenda-templates"], queryFn: () => api.get<MeDailyAgendaTemplate[]>("/me/facilitators/agenda-templates") });
  const [form, setForm] = useState<NewForm>({ title: "", phase: "TOT", period_start: "", period_end: "", description: "", agenda_template: "TRAINING_2026" });
  const [error, setError] = useState<unknown>(null);
  const save = useMutation({
    mutationFn: (f: NewForm) => api.post<MeFacRound>("/me/facilitators/rounds", { title: f.title, phase: f.phase, period_start: f.period_start || null, period_end: f.period_end || null, description: f.description || null, agenda_template: f.agenda_template || null }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["me-facrep"] }); qc.invalidateQueries({ queryKey: ["me-fac"] }); onClose(); },
    onError: setError,
  });
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <form className="w-full max-w-lg rounded-lg bg-white p-5 shadow-xl" onClick={(e) => e.stopPropagation()} onSubmit={(e) => { e.preventDefault(); save.mutate(form); }}>
        <h2 className="mb-1 text-lg font-semibold">New training</h2>
        <p className="mb-3 text-xs text-slate-500">One entry per training: its link and QR code serve the Daily Facilitator's Report and the trainer ratings. The chapters per day can be edited afterwards under Facilitator assessment.</p>
        <div className="grid gap-3">
          <Field label="Training"><input className="input" required minLength={3} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="e.g. Training of Trainers (in-person), November 2026" /></Field>
          <Field label="Training phase">
            <div className="grid grid-cols-3 gap-2">
              {PHASES.map((m) => (
                <button type="button" key={m} onClick={() => setForm({ ...form, phase: m })} className={clsx("rounded-md border px-3 py-2 text-sm font-medium", form.phase === m ? "border-navy bg-navy text-white" : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50")}>{PHASE_LABEL[m]}</button>
              ))}
            </div>
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Training from"><input className="input" type="date" value={form.period_start} onChange={(e) => setForm({ ...form, period_start: e.target.value })} /></Field>
            <Field label="to"><input className="input" type="date" value={form.period_end} onChange={(e) => setForm({ ...form, period_end: e.target.value })} /></Field>
          </div>
          <Field label="Chapters per day (sessions of section C and topics of section G)">
            <select className="input" value={form.agenda_template} onChange={(e) => setForm({ ...form, agenda_template: e.target.value })}>
              <option value="">None now (add them afterwards)</option>
              {(templates.data ?? []).map((t) => <option key={t.key} value={t.key}>{t.title} · {t.items.length} chapters, {t.days} days</option>)}
            </select>
          </Field>
          <Field label="Note shown to the Lead Facilitators (optional)"><textarea className="input" rows={2} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="e.g. Send the report of your hall before 18:00 each day." /></Field>
        </div>
        <ErrorBox error={error instanceof ApiError ? error.message : error} />
        <div className="mt-4 flex justify-end gap-2">
          <button type="button" className="btn-outline" onClick={onClose}>Cancel</button>
          <button className="btn-primary" disabled={save.isPending}>{save.isPending ? "Creating…" : "Create training"}</button>
        </div>
      </form>
    </div>
  );
}
