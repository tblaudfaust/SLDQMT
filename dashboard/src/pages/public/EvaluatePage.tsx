import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import clsx from "clsx";
import { ArrowLeft, ArrowRight, CheckCircle2, ClipboardCheck, Mail, Phone, UserRound } from "lucide-react";
import { ApiError, api } from "../../api/client";

/* ------------------------------------------------------------------------------------------------
 * The public training evaluation page: /evaluate/<token>. No sign-in. Trainees and trainers
 * register with name, email and phone, then answer the questionnaire step by step. The question
 * set, options and routing come from the server (app/core/me_form.py) so the two cannot drift.
 * ---------------------------------------------------------------------------------------------- */

type Option = { value: string; label: string };
type Item = { code: string; text: string; type: "single" | "likert" | "multi" | "text" | "number"; options?: Option[]; scale?: "agree" | "confidence"; audience: string; required: boolean; other?: boolean; help?: string | null; text_in_person?: string | null; max_select?: number; exclusive?: string | null; min?: number };
type Section = { code: string; title: string; audience: string; intro?: string; scale?: "agree" | "confidence"; items: Item[] };
type Form = { scales: { agree: Option[]; confidence: Option[] }; sections: Section[]; rules: { role_item: string; in_person_hidden: string[] } };
type Evaluation = { title: string; training_mode: "ONLINE" | "IN_PERSON"; period_start: string | null; period_end: string | null; description: string | null; status: string; form: Form };
type Answers = Record<string, string | string[] | number | undefined>;
type Saved = { respondent_id: number; resume_token: string; full_name: string; answers: Answers; step: number; done?: boolean };

const roleOf = (a: Answers) => ({ "1": "TRAINER", "2": "TRAINEE", "3": "NEITHER" } as Record<string, string>)[String(a.A00 ?? "")];
const sectionOf = (code: string) => code[0];

/** The routing and skip rules, mirrored from the server. */
function isAsked(code: string, item: Item, a: Answers, mode: string): boolean {
  if (code === "A00") return true;
  const role = roleOf(a);
  if (!role || role === "NEITHER") return false;
  if (role === "TRAINER") {
    if (["A02", "A03", "A04", "A05"].includes(code)) return true;
    if (item.audience !== "trainer") return false;
    if (code === "J12_n" || code === "J12_names") return String(a.J11) === "1";
    return true;
  }
  if (item.audience === "trainer") return false;
  if (mode === "IN_PERSON" && ["A09", "B01", "B02", "B03", "B04", "B05", "B06", "B07"].includes(code)) return false;
  if (code === "B07") return String(a.A06) === "0" || String(a.A08) === "0";
  if (sectionOf(code) === "F") return !["1", "9"].includes(String(a.A07));
  if (code === "G07") return String(a.A01) === "1";
  if (code === "G08") return String(a.A01) === "2";
  return true;
}

const fmtDate = (d: string | null) => (d ? new Date(d + "T00:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" }) : "");

export default function EvaluatePage() {
  const { token = "" } = useParams();
  const key = `me-eval-${token}`;
  const [ev, setEv] = useState<Evaluation | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saved, setSaved] = useState<Saved | null>(() => { try { const s = localStorage.getItem(key); return s ? (JSON.parse(s) as Saved) : null; } catch { return null; } });

  useEffect(() => {
    api.get<Evaluation>(`/public/evaluations/${token}`).then(setEv).catch((e) => setLoadError(e instanceof ApiError ? e.message : "This evaluation link is not valid."));
  }, [token]);
  useEffect(() => { try { if (saved) localStorage.setItem(key, JSON.stringify(saved)); } catch { /* private mode */ } }, [saved, key]);

  return (
    <div className="min-h-screen bg-[radial-gradient(ellipse_at_top_left,_#2a6aa6_0%,_#1F4E79_45%,_#0f3557_100%)] px-3 py-6 text-slate-800 sm:px-6 sm:py-10">
      <div className="mx-auto max-w-2xl">
        <header className="mb-5 flex items-center gap-3 text-white">
          <img src="/statsl-logo.png" alt="Statistics Sierra Leone" className="h-12 w-12 rounded-full bg-white p-0.5 shadow" />
          <div>
            <div className="text-xs uppercase tracking-[0.25em] text-sky-200">Statistics Sierra Leone · 2026 PHC</div>
            <div className="text-lg font-bold leading-tight">Training evaluation</div>
          </div>
        </header>
        {loadError ? (
          <Card><h1 className="text-xl font-bold">Link not valid</h1><p className="mt-2 text-slate-600">{loadError}</p></Card>
        ) : !ev ? (
          <Card><div className="animate-pulse text-slate-500">Loading the evaluation…</div></Card>
        ) : ev.status !== "OPEN" && !saved?.done ? (
          <Card><h1 className="text-xl font-bold">{ev.title}</h1><p className="mt-2 text-slate-600">This evaluation is closed. Thank you for your interest.</p></Card>
        ) : saved?.done ? (
          <ThankYou ev={ev} name={saved.full_name} />
        ) : !saved ? (
          <Register ev={ev} token={token} onDone={(s) => setSaved(s)} />
        ) : (
          <Wizard ev={ev} token={token} saved={saved} setSaved={setSaved} />
        )}
        <p className="mt-6 text-center text-xs text-sky-100/70">Results are reported in aggregate only. This form does not replace the formal trainee assessment.</p>
      </div>
    </div>
  );
}

function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={clsx("rounded-2xl bg-white p-5 shadow-xl shadow-black/20 sm:p-8", className)}>{children}</div>;
}

function ModeBadge({ mode }: { mode: string }) {
  return <span className={clsx("inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold", mode === "ONLINE" ? "bg-sky-100 text-sky-800" : "bg-emerald-100 text-emerald-800")}>{mode === "ONLINE" ? "Online / self-paced" : "In-person"}</span>;
}

/* ---- step 1: register --------------------------------------------------------------------------- */

function Register({ ev, token, onDone }: { ev: Evaluation; token: string; onDone: (s: Saved) => void }) {
  const [form, setForm] = useState({ full_name: "", email: "", phone: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const phoneOk = /^\+?\d{8,15}$/.test(form.phone.replace(/[\s\-()]/g, ""));
  const emailOk = /^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test(form.email.trim());
  const ready = form.full_name.trim().length >= 2 && emailOk && phoneOk;
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      const r = await api.post<{ respondent_id: number; resume_token: string; full_name: string; already_submitted: boolean }>(`/public/evaluations/${token}/register`, form);
      onDone({ respondent_id: r.respondent_id, resume_token: r.resume_token, full_name: r.full_name, answers: {}, step: 0, done: r.already_submitted });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not register. Please try again.");
    } finally { setBusy(false); }
  };
  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-bold text-navy">{ev.title}</h1>
        <ModeBadge mode={ev.training_mode} />
      </div>
      {(ev.period_start || ev.period_end) && <p className="mt-1 text-sm text-slate-500">Training period: {fmtDate(ev.period_start)}{ev.period_end ? ` – ${fmtDate(ev.period_end)}` : ""}</p>}
      <p className="mt-3 text-slate-700">{ev.description || "Your feedback helps us assess training quality, participant readiness, CAPI and data-quality preparedness, and trainer performance. It takes about 10 minutes."}</p>
      <div className="mt-4 rounded-xl bg-slate-50 p-4 text-sm text-slate-600">
        <b className="text-slate-800">Who should answer:</b> trainees and participants rate the training; trainers and facilitators rate their group of trainees. Please answer from your own experience.
      </div>
      <form onSubmit={submit} className="mt-6 space-y-4">
        <h2 className="text-base font-semibold text-slate-800">Register to start</h2>
        <Field icon={<UserRound size={18} />} label="Full name"><input className="pub-input" required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} placeholder="Your full name" autoComplete="name" /></Field>
        <Field icon={<Mail size={18} />} label="Email address"><input className="pub-input" type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="name@example.com" autoComplete="email" /></Field>
        <Field icon={<Phone size={18} />} label="Phone number (required)" hint={form.phone && !phoneOk ? "Enter 8 to 15 digits, for example 076 123 456" : undefined}><input className="pub-input" type="tel" required value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="076 123 456" autoComplete="tel" /></Field>
        {error && <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}
        <button className="pub-btn w-full" disabled={!ready || busy}>{busy ? "One moment…" : "Start the evaluation"} <ArrowRight size={18} /></button>
        <p className="text-center text-xs text-slate-500">Your email lets you continue later on the same link and prevents duplicate submissions. Your answers are reported in aggregate only.</p>
      </form>
    </Card>
  );
}

function Field({ icon, label, hint, children }: { icon: React.ReactNode; label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 flex items-center gap-2 text-sm font-medium text-slate-700">{icon} {label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-amber-700">{hint}</span>}
    </label>
  );
}

/* ---- step 2: the questionnaire, one section per step ------------------------------------------- */

function Wizard({ ev, token, saved, setSaved }: { ev: Evaluation; token: string; saved: Saved; setSaved: (s: Saved) => void }) {
  const mode = ev.training_mode;
  const answers = saved.answers;
  const role = roleOf(answers);
  // the sections this respondent answers, given their role and the training mode
  const steps = useMemo(() => {
    const visible = ev.form.sections.filter((s) => s.items.some((it) => isAsked(it.code, it, answers, mode)));
    return visible.length ? visible : [ev.form.sections[0]];
  }, [ev.form.sections, answers, mode]);
  const stepIndex = Math.min(saved.step, steps.length - 1);
  const section = steps[stepIndex];
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const items = section.items.filter((it) => isAsked(it.code, it, answers, mode));
  const scale = (it: Item) => ev.form.scales[it.scale ?? section.scale ?? "agree"];
  const set = (code: string, value: Answers[string]) => setSaved({ ...saved, answers: { ...answers, [code]: value } });
  // "Submit" only once the role is known and this is the respondent's last section
  const last = role === "NEITHER" || (!!role && stepIndex === steps.length - 1);

  const validateStep = () => {
    const errs: Record<string, string> = {};
    for (const it of items) {
      const v = answers[it.code];
      const empty = v === undefined || v === "" || (Array.isArray(v) && v.length === 0);
      if (it.required && empty) errs[it.code] = "Please answer this question";
      if (!empty && (it.type === "single" || it.type === "multi") && it.other) {
        const chosen = Array.isArray(v) ? v.includes("96") : String(v) === "96";
        if (chosen && !String(answers[`${it.code}_other`] ?? "").trim()) errs[it.code] = "Please specify";
      }
      if (it.type === "multi" && Array.isArray(v) && it.exclusive && v.includes(it.exclusive) && v.length > 1) errs[it.code] = "'None' cannot be combined with other options";
      if (it.type === "number" && !empty && (Number.isNaN(Number(v)) || Number(v) < (it.min ?? 0))) errs[it.code] = `Enter a whole number of at least ${it.min ?? 0}`;
    }
    if (section.code === "J" && answers.J12_n !== undefined && Number(answers.J12_n) > Number(answers.J02)) errs.J12_n = "Cannot exceed the number of trainees in the group";
    setErrors(errs);
    if (Object.keys(errs).length) document.getElementById(`q-${Object.keys(errs)[0]}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
    return Object.keys(errs).length === 0;
  };

  const next = async () => {
    if (!validateStep()) return;
    if (!last) { setSaved({ ...saved, step: stepIndex + 1 }); window.scrollTo({ top: 0, behavior: "smooth" }); return; }
    setBusy(true); setServerError(null);
    try {
      await api.post(`/public/evaluations/${token}/submit`, { respondent_id: saved.respondent_id, resume_token: saved.resume_token, answers });
      setSaved({ ...saved, done: true });
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) { setSaved({ ...saved, done: true }); return; }
      if (err instanceof ApiError && err.status === 403) { setServerError("Your session expired. Please reload the page and register again; your answers are kept on this device."); return; }
      const detail = err instanceof ApiError ? (err.body as { detail?: { errors?: string[] } } | undefined)?.detail : undefined;
      if (detail && typeof detail === "object" && Array.isArray(detail.errors)) {
        const errs: Record<string, string> = {};
        for (const e of detail.errors) { const [code, msg] = e.split(": "); errs[code] = msg; }
        setErrors(errs);
        const first = steps.findIndex((s) => s.items.some((it) => it.code in errs));
        if (first >= 0 && first !== stepIndex) setSaved({ ...saved, step: first });
        setServerError("Some answers need attention. Please check the highlighted questions.");
      } else {
        setServerError(err instanceof ApiError ? err.message : "Could not send your answers. Check your connection and try again; your answers are kept on this device.");
      }
    } finally { setBusy(false); }
  };

  const progress = Math.round(((stepIndex + (role === "NEITHER" ? 1 : 0)) / Math.max(steps.length, 1)) * 100);
  return (
    <Card className="p-0 sm:p-0">
      <div className="rounded-t-2xl bg-gradient-to-r from-navy to-[#2a6aa6] px-5 py-4 text-white sm:px-8">
        <div className="flex items-center justify-between gap-3 text-xs text-sky-100">
          <span>{saved.full_name}</span>
          <ModeBadge mode={mode} />
        </div>
        <div className="mt-2 flex items-end justify-between gap-3">
          <div>
            <div className="text-xs uppercase tracking-widest text-sky-200">Section {section.code} · step {stepIndex + 1} of {steps.length}</div>
            <h2 className="text-lg font-bold leading-tight">{section.title}</h2>
          </div>
          <div className="text-2xl font-bold">{progress}%</div>
        </div>
        <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/20"><div className="h-full rounded-full bg-emerald-400 transition-all" style={{ width: `${progress}%` }} /></div>
      </div>
      <div className="px-5 py-5 sm:px-8 sm:py-7">
        {section.intro && <p className="mb-4 rounded-xl bg-sky-50 px-4 py-3 text-sm text-slate-700">{section.intro}</p>}
        {(section.scale || items.some((it) => it.type === "likert")) && (
          <ScaleLegend options={ev.form.scales[section.scale ?? "agree"]} />
        )}
        <div className="space-y-6">
          {items.map((it, i) => (
            <Question key={it.code} index={i + 1} item={it} mode={mode} value={answers[it.code]} other={answers[`${it.code}_other`] as string | undefined} error={errors[it.code]} scale={scale(it)}
              onChange={(v) => { set(it.code, v); if (errors[it.code]) setErrors({ ...errors, [it.code]: "" }); }}
              onOther={(v) => set(`${it.code}_other`, v)} />
          ))}
          {role === "NEITHER" && section.code === "A" && (
            <div className="rounded-xl bg-emerald-50 px-4 py-3 text-sm text-emerald-900">Thank you. As an observer or support staff you have no further questions; press Submit to finish.</div>
          )}
        </div>
        {serverError && <div className="mt-5 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{serverError}</div>}
        <div className="mt-7 flex items-center justify-between gap-3">
          <button type="button" className="pub-btn-ghost" disabled={stepIndex === 0 || busy} onClick={() => { setSaved({ ...saved, step: stepIndex - 1 }); window.scrollTo({ top: 0 }); }}><ArrowLeft size={18} /> Back</button>
          <button type="button" className="pub-btn" disabled={busy} onClick={next}>{busy ? "Sending…" : last ? <>Submit <CheckCircle2 size={18} /></> : <>Continue <ArrowRight size={18} /></>}</button>
        </div>
        <p className="mt-3 text-center text-xs text-slate-400">Your answers are saved on this device as you go.</p>
      </div>
    </Card>
  );
}

function ScaleLegend({ options }: { options: Option[] }) {
  return (
    <div className="mb-5 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
      {options.map((o) => <span key={o.value}><b className="text-slate-700">{o.value}</b> = {o.label}</span>)}
      <span><b className="text-slate-700">N/A</b> = not applicable</span>
    </div>
  );
}

function Question({ index, item, mode, value, other, error, scale, onChange, onOther }: { index: number; item: Item; mode: string; value: Answers[string]; other?: string; error?: string; scale: Option[]; onChange: (v: Answers[string]) => void; onOther: (v: string) => void }) {
  const text = mode === "IN_PERSON" && item.text_in_person ? item.text_in_person : item.text;
  const showOther = item.other && (Array.isArray(value) ? value.includes("96") : String(value ?? "") === "96");
  return (
    <div id={`q-${item.code}`} className={clsx("rounded-xl border p-4 transition", error ? "border-red-300 bg-red-50/40" : "border-slate-200")}>
      <div className="flex gap-3">
        <span className="mt-0.5 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-navy/10 text-xs font-bold text-navy">{index}</span>
        <div className="flex-1">
          <p className="font-medium text-slate-800">{text}{item.required && <span className="text-red-500"> *</span>}</p>
          {item.help && <p className="text-xs text-slate-500">{item.help}</p>}
          <div className="mt-3">
            {item.type === "likert" && (
              <div className="grid grid-cols-6 gap-1.5">
                {[...scale.map((o) => o.value), "NA"].map((v) => {
                  const selected = String(value ?? "") === v;
                  const label = v === "NA" ? "N/A" : v;
                  return (
                    <button key={v} type="button" onClick={() => onChange(v)} title={v === "NA" ? "Not applicable" : scale.find((o) => o.value === v)?.label}
                      className={clsx("rounded-lg border py-2.5 text-sm font-semibold transition", selected ? (v === "NA" ? "border-slate-500 bg-slate-600 text-white" : "border-navy bg-navy text-white shadow") : "border-slate-200 bg-white text-slate-700 hover:border-navy/50 hover:bg-sky-50")}>
                      {label}
                    </button>
                  );
                })}
                <div className="col-span-6 flex justify-between text-[11px] text-slate-400"><span>{scale[0].label}</span><span>{scale[scale.length - 1].label}</span></div>
              </div>
            )}
            {item.type === "single" && (
              <div className={clsx("grid gap-2", (item.options?.length ?? 0) > 6 ? "sm:grid-cols-2" : "")}>
                {item.options!.map((o) => {
                  const selected = String(value ?? "") === o.value;
                  return (
                    <button key={o.value} type="button" onClick={() => onChange(o.value)}
                      className={clsx("flex items-center gap-3 rounded-lg border px-3 py-2.5 text-left text-sm transition", selected ? "border-navy bg-navy text-white shadow" : "border-slate-200 bg-white text-slate-700 hover:border-navy/50 hover:bg-sky-50")}>
                      <span className={clsx("inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full border", selected ? "border-white bg-white" : "border-slate-400")}>{selected && <span className="h-2 w-2 rounded-full bg-navy" />}</span>
                      {o.label}
                    </button>
                  );
                })}
              </div>
            )}
            {item.type === "multi" && (
              <div className="grid gap-2 sm:grid-cols-2">
                {item.options!.map((o) => {
                  const list = Array.isArray(value) ? value : [];
                  const selected = list.includes(o.value);
                  const toggle = () => {
                    let next = selected ? list.filter((x) => x !== o.value) : [...list, o.value];
                    if (item.exclusive) next = o.value === item.exclusive && !selected ? [o.value] : next.filter((x) => x !== item.exclusive || o.value === item.exclusive);
                    if (next.length > (item.max_select ?? 3)) return;
                    onChange(next);
                  };
                  return (
                    <button key={o.value} type="button" onClick={toggle}
                      className={clsx("flex items-center gap-3 rounded-lg border px-3 py-2.5 text-left text-sm transition", selected ? "border-navy bg-navy text-white shadow" : "border-slate-200 bg-white text-slate-700 hover:border-navy/50 hover:bg-sky-50")}>
                      <span className={clsx("inline-flex h-4 w-4 shrink-0 items-center justify-center rounded border", selected ? "border-white bg-white text-navy" : "border-slate-400")}>{selected && <CheckCircle2 size={12} />}</span>
                      {o.label}
                    </button>
                  );
                })}
                <div className="text-xs text-slate-500 sm:col-span-2">Choose up to {item.max_select ?? 3}.</div>
              </div>
            )}
            {item.type === "text" && <textarea className="pub-input" rows={3} value={String(value ?? "")} onChange={(e) => onChange(e.target.value)} placeholder="Short, practical answer" />}
            {item.type === "number" && <input className="pub-input sm:w-48" type="number" min={item.min ?? 0} value={value === undefined ? "" : String(value)} onChange={(e) => onChange(e.target.value === "" ? undefined : Number(e.target.value))} />}
            {showOther && <input className="pub-input mt-2" placeholder="Please specify" value={other ?? ""} onChange={(e) => onOther(e.target.value)} />}
          </div>
          {error && <p className="mt-2 text-sm font-medium text-red-600">{error}</p>}
        </div>
      </div>
    </div>
  );
}

function ThankYou({ ev, name }: { ev: Evaluation; name: string }) {
  return (
    <Card className="text-center">
      <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100 text-emerald-700"><ClipboardCheck size={34} /></div>
      <h1 className="text-2xl font-bold text-navy">Thank you, {name.split(" ")[0]}!</h1>
      <p className="mt-2 text-slate-600">Your evaluation of <b>{ev.title}</b> has been received. Your feedback helps Statistics Sierra Leone improve the 2026 census training.</p>
      <p className="mt-4 text-xs text-slate-400">You can close this page. Each person can submit once per evaluation.</p>
    </Card>
  );
}
