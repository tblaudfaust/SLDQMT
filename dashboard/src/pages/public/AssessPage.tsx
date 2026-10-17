import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import clsx from "clsx";
import { ClipboardCheck, Pencil, Star, Users } from "lucide-react";
import { ApiError, api } from "../../api/client";
import SiteFooter from "../../components/SiteFooter";
import type { MeFacAgendaItem, MeFacSpec } from "../../api/types";
import { BAND_CLS, FacilitatorForm, emptyFacValues, sectionsForDay, toFacPayload, validateFac, type FacValues } from "./FacilitatorForm";
import { PageWatermark } from "./EvaluatePage";

/* ------------------------------------------------------------------------------------------------
 * The public Daily Trainer Facilitation Rating page: /assess/<token>. No sign-in. The M&E monitor
 * rates each trainer of the hall once a day; a sent rating can be corrected from the same device.
 * ---------------------------------------------------------------------------------------------- */

type Round = { title: string; phase: string; period_start: string | null; period_end: string | null; description: string | null; status: string; agenda: MeFacAgendaItem[]; form: MeFacSpec };
type Sent = { assessment_id: number; edit_token: string; assessment_date: string; training_day: string; hall: string; trainer_name: string; score_pct: number; band: string; band_label: string; values: FacValues; sent_at: string };
type Store = { draft: FacValues | null; sent: Sent[] };

const PHASE_LABEL: Record<string, string> = { MASTER: "Master Training", TOT: "Training of Trainers", FIELD: "Field Staff Training" };
const fmtDate = (d: string | null) => (d ? new Date(d + "T00:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" }) : "");

export default function AssessPage() {
  const { token = "" } = useParams();
  const key = `me-fac-${token}`;
  const [round, setRound] = useState<Round | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [store, setStore] = useState<Store>(() => { try { const s = localStorage.getItem(key); return s ? (JSON.parse(s) as Store) : { draft: null, sent: [] }; } catch { return { draft: null, sent: [] }; } });
  const [values, setValues] = useState<FacValues | null>(null);
  const [editing, setEditing] = useState<Sent | null>(null);
  const [done, setDone] = useState<Sent | null>(null);
  const [busy, setBusy] = useState(false);
  const [touched, setTouched] = useState(false);
  const [serverErrors, setServerErrors] = useState<string[]>([]);

  useEffect(() => {
    api.get<Round>(`/public/assess/${token}`).then((r) => { setRound(r); setValues(store.draft ?? emptyFacValues()); }).catch((e) => setLoadError(e instanceof ApiError ? e.message : "This link is not valid."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);
  useEffect(() => { try { localStorage.setItem(key, JSON.stringify(store)); } catch { /* private mode */ } }, [store, key]);
  useEffect(() => { if (values && !editing) setStore((s) => ({ ...s, draft: values })); }, [values, editing]);

  const errors = round && values ? validateFac(values, round.form) : [];

  const submit = async () => {
    if (!round || !values) return;
    setTouched(true);
    if (errors.length) return;
    setBusy(true); setServerErrors([]);
    try {
      const body = { ...toFacPayload(values), ...(editing ? { assessment_id: editing.assessment_id, edit_token: editing.edit_token } : {}) };
      const r = await api.post<{ assessment_id: number; edit_token: string; score_pct: number; band: string; band_label: string }>(`/public/assess/${token}/submit`, body);
      const sent: Sent = { assessment_id: r.assessment_id, edit_token: r.edit_token, assessment_date: values.assessment_date, training_day: values.training_day, hall: values.hall, trainer_name: values.trainer_name, score_pct: r.score_pct, band: r.band, band_label: r.band_label, values, sent_at: new Date().toISOString() };
      setStore((s) => ({ draft: null, sent: [sent, ...s.sent.filter((x) => x.assessment_id !== sent.assessment_id)].slice(0, 40) }));
      setDone(sent); setEditing(null); setTouched(false);
      // the next rating keeps the date, day, district, hall and monitor: the next trainer of the same hall
      const day = Number(values.training_day);
      setValues({ ...emptyFacValues(), assessment_date: values.assessment_date, training_day: values.training_day, district: values.district, hall: values.hall, monitor_name: values.monitor_name, sections: sectionsForDay(round.agenda, day) });
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      const detail = err instanceof ApiError ? (err.body as { detail?: string } | undefined)?.detail : undefined;
      setServerErrors([typeof detail === "string" ? detail : err instanceof ApiError ? err.message : "Could not send the rating. Check your connection and try again; your answers are kept on this device."]);
    } finally { setBusy(false); }
  };

  const startEdit = (s: Sent) => { setEditing(s); setValues(s.values); setDone(null); window.scrollTo({ top: 0, behavior: "smooth" }); };

  return (
    <div className="relative min-h-screen overflow-hidden bg-[radial-gradient(ellipse_at_top_left,_#2a6aa6_0%,_#1F4E79_45%,_#0f3557_100%)] px-3 py-6 text-slate-800 sm:px-6 sm:py-10">
      <PageWatermark />
      <div className="relative mx-auto max-w-3xl">
        <header className="mb-5 flex items-center gap-3 text-white">
          <img src="/statsl-logo.png" alt="Statistics Sierra Leone" className="h-12 w-12 rounded-full bg-white p-0.5 shadow" />
          <div>
            <div className="text-xs uppercase tracking-[0.25em] text-sky-200">Statistics Sierra Leone · 2026 PHC</div>
            <div className="text-lg font-bold leading-tight">Daily Trainer Facilitation Rating</div>
          </div>
        </header>
        {loadError ? (
          <Card><h1 className="text-xl font-bold">Link not valid</h1><p className="mt-2 text-slate-600">{loadError}</p></Card>
        ) : !round || !values ? (
          <Card><div className="animate-pulse text-slate-500">Loading…</div></Card>
        ) : round.status !== "OPEN" ? (
          <Card><h1 className="text-xl font-bold">{round.title}</h1><p className="mt-2 text-slate-600">This facilitator assessment is closed. Thank you.</p></Card>
        ) : (
          <div className="space-y-4">
            {done && (
              <Card className="border-l-4 border-emerald-500">
                <div className="flex items-start gap-3">
                  <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-emerald-700"><ClipboardCheck size={26} /></div>
                  <div>
                    <h2 className="text-lg font-bold text-navy">Rating received — thank you</h2>
                    <p className="text-sm text-slate-600"><b>{done.trainer_name}</b>, {done.hall}, day {done.training_day}: score {done.score_pct}% · <span className={clsx("rounded-full px-2 py-0.5 text-xs font-semibold", BAND_CLS[done.band])}>{done.band_label}</span>. The form below is ready for the next trainer of this hall. To correct a rating, use <b>My sent ratings</b> at the bottom.</p>
                  </div>
                </div>
              </Card>
            )}
            <Card className="overflow-hidden p-0 sm:p-0">
              <div className="bg-gradient-to-br from-navy via-[#245a8c] to-[#1b7f6b] px-5 py-6 text-white sm:px-8">
                <div className="text-xs uppercase tracking-[0.3em] text-sky-100/80">2026 Population and Housing Census, Sierra Leone</div>
                <h1 className="mt-1 text-2xl font-bold leading-tight sm:text-3xl">{round.title}</h1>
                <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                  <span className="rounded-full bg-white/15 px-3 py-1 font-semibold">{PHASE_LABEL[round.phase] ?? round.phase}</span>
                  {(round.period_start || round.period_end) && <span className="text-sky-100">{fmtDate(round.period_start)}{round.period_end ? ` – ${fmtDate(round.period_end)}` : ""}</span>}
                </div>
                <p className="mt-4 max-w-2xl text-sm text-sky-50/90">{round.description || round.form.intro}</p>
                <div className="mt-5 grid gap-2 sm:grid-cols-3">
                  {[
                    { icon: <Users size={18} />, title: "Who rates", text: "The M&E monitor in the hall, each trainer once a day." },
                    { icon: <Star size={18} />, title: "Scale 1 to 4", text: "1 Poor · 2 Fair · 3 Good · 4 Excellent. Section A out of 20; section B on the chapters observed." },
                    { icon: <ClipboardCheck size={18} />, title: "Chapters loaded", text: round.agenda.length ? `${round.agenda.length} chapters over ${new Set(round.agenda.map((a) => a.day)).size} days are listed by training day.` : "Add the sections you observed." },
                  ].map((b) => (
                    <div key={b.title} className="rounded-xl bg-white/10 p-3 backdrop-blur-sm">
                      <div className="flex items-center gap-2 text-sm font-semibold">{b.icon} {b.title}</div>
                      <div className="mt-1 text-xs text-sky-50/85">{b.text}</div>
                    </div>
                  ))}
                </div>
              </div>
              <div className="px-5 py-6 sm:px-8 sm:py-7">
                {editing && (
                  <div className="mb-4 flex items-center justify-between gap-3 rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-900">
                    <span><Pencil size={14} className="mr-1 inline" /> Correcting the rating of <b>{editing.trainer_name}</b>, {editing.hall}, day {editing.training_day}.</span>
                    <button type="button" className="font-semibold underline" onClick={() => { setEditing(null); setValues(store.draft ?? emptyFacValues()); }}>Cancel</button>
                  </div>
                )}
                {serverErrors.length > 0 && (
                  <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"><div className="font-semibold">The server could not accept the rating</div><ul className="mt-1 list-disc pl-5">{serverErrors.map((x) => <li key={x}>{x}</li>)}</ul></div>
                )}
                <FacilitatorForm spec={round.form} agenda={round.agenda} values={values} onChange={setValues} onSubmit={submit} busy={busy} submitLabel={editing ? "Send the correction" : "Send this rating"} errors={touched ? errors : []} />
              </div>
            </Card>
            {store.sent.length > 0 && (
              <Card>
                <h2 className="text-base font-bold text-navy">My sent ratings <span className="text-xs font-normal text-slate-400">(this device)</span></h2>
                <ul className="mt-2 divide-y divide-slate-100 text-sm">
                  {store.sent.map((s) => (
                    <li key={s.assessment_id} className="flex items-center justify-between gap-3 py-2">
                      <span><b>{s.trainer_name}</b> · {s.hall} · day {s.training_day} · {fmtDate(s.assessment_date)} · {s.score_pct}% <span className={clsx("rounded-full px-2 py-0.5 text-xs font-semibold", BAND_CLS[s.band])}>{s.band_label}</span></span>
                      <button type="button" className={clsx("pub-btn-ghost py-1.5 text-sm", editing?.assessment_id === s.assessment_id && "text-navy")} onClick={() => startEdit(s)}><Pencil size={14} /> Correct</button>
                    </li>
                  ))}
                </ul>
              </Card>
            )}
          </div>
        )}
        <p className="mt-6 text-center text-xs text-sky-100/70">Ratings are seen only by the Monitoring &amp; Evaluation accounts.</p>
        <SiteFooter tone="dark" className="mt-8" />
      </div>
    </div>
  );
}

function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={clsx("rounded-2xl bg-white p-5 shadow-xl shadow-black/20 sm:p-8", className)}>{children}</div>;
}
