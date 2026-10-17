import clsx from "clsx";
import type { MeFacAgendaItem, MeFacSpec } from "../../api/types";

/* ------------------------------------------------------------------------------------------------
 * The Daily Trainer Facilitation Rating Tool, rendered from the server's spec (app/core/me_fac_form.py).
 * Used by the public page (M&E monitors in the halls) and by the dashboard's edit dialog (M&E staff).
 * ---------------------------------------------------------------------------------------------- */

export type FacValues = {
  assessment_date: string; training_day: string; district: string; hall: string; monitor_name: string; trainer_name: string;
  scores: Record<string, string>; sections: { topic: string; rating: string }[]; strengths: string; improvements: string; comments: string;
};

export const today = () => new Date().toISOString().slice(0, 10);
export const CRITERIA_KEYS = ["technical", "clarity", "practical", "participation", "time"];

export function emptyFacValues(): FacValues {
  return { assessment_date: today(), training_day: "", district: "", hall: "", monitor_name: "", trainer_name: "", scores: {}, sections: [], strengths: "", improvements: "", comments: "" };
}

/** The chapters of a training day, as unrated section B rows. */
export function sectionsForDay(agenda: MeFacAgendaItem[], day: number) {
  return agenda.filter((a) => a.day === day).map((a) => ({ topic: a.topic, rating: "" }));
}

export const BAND_CLS: Record<string, string> = { EXCELLENT: "bg-emerald-100 text-emerald-800", GOOD: "bg-lime-100 text-lime-800", FAIR: "bg-amber-100 text-amber-800", NEEDS_IMPROVEMENT: "bg-red-100 text-red-800" };
export const BAND_COLOR: Record<string, string> = { EXCELLENT: "#15803d", GOOD: "#65a30d", FAIR: "#d97706", NEEDS_IMPROVEMENT: "#b91c1c" };
export const SCORE_COLOR: Record<string, string> = { "4": "#15803d", "3": "#65a30d", "2": "#d97706", "1": "#b91c1c" };

/** Live scoring, the same arithmetic as the server: A out of 20, B over the sections rated, overall %. */
export function facScore(v: FacValues, spec: MeFacSpec) {
  const a = CRITERIA_KEYS.map((k) => Number(v.scores[k] || 0));
  const aDone = a.every((x) => x >= 1);
  const aTotal = a.reduce((s, x) => s + x, 0);
  const rated = v.sections.filter((s) => s.rating !== "");
  const bTotal = rated.reduce((s, x) => s + Number(x.rating), 0);
  const bMax = rated.length * 4;
  const pct = aDone ? Math.round((1000 * (aTotal + bTotal)) / (spec.section_a_max + bMax)) / 10 : null;
  const bandA = aDone ? spec.bands.find((b) => aTotal >= b.min_total)?.label ?? null : null;
  const band = pct === null ? null : spec.bands.find((b) => pct >= b.min_pct) ?? null;
  return { aTotal, aDone, bTotal, bMax, rated: rated.length, pct, bandA, band };
}

export function toFacPayload(v: FacValues) {
  const t = (s: string) => (s.trim() === "" ? null : s.trim());
  return {
    assessment_date: v.assessment_date, training_day: Number(v.training_day), district: t(v.district), hall: v.hall.trim(), monitor_name: v.monitor_name.trim(), trainer_name: v.trainer_name.trim(),
    s_technical: Number(v.scores.technical), s_clarity: Number(v.scores.clarity), s_practical: Number(v.scores.practical), s_participation: Number(v.scores.participation), s_time: Number(v.scores.time),
    sections: v.sections.filter((s) => s.topic.trim()).map((s) => ({ topic: s.topic.trim(), rating: s.rating === "" ? null : Number(s.rating) })),
    strengths: t(v.strengths), improvements: t(v.improvements), comments: t(v.comments),
  };
}

export function validateFac(v: FacValues, spec: MeFacSpec): string[] {
  const e: string[] = [];
  if (!v.assessment_date) e.push("Enter the date");
  else if (v.assessment_date > today()) e.push("The date cannot be in the future");
  if (!v.training_day || Number(v.training_day) < 1) e.push("Choose the training day");
  if (v.hall.trim().length < 1) e.push("Enter the hall");
  if (v.monitor_name.trim().length < 2) e.push("Enter your name (M&E monitor)");
  if (v.trainer_name.trim().length < 2) e.push("Enter the trainer's name");
  for (const c of spec.criteria) if (!v.scores[c.key]) e.push(`Rate: ${c.label}`);
  return e;
}

export function fromAssessment(x: { assessment_date: string; training_day: number; district: string | null; hall: string; monitor_name: string; trainer_name: string; s_technical: number; s_clarity: number; s_practical: number; s_participation: number; s_time: number; sections: { topic: string; rating: number | null }[]; strengths: string | null; improvements: string | null; comments: string | null }): FacValues {
  return {
    assessment_date: x.assessment_date, training_day: String(x.training_day), district: x.district ?? "", hall: x.hall, monitor_name: x.monitor_name, trainer_name: x.trainer_name,
    scores: { technical: String(x.s_technical), clarity: String(x.s_clarity), practical: String(x.s_practical), participation: String(x.s_participation), time: String(x.s_time) },
    sections: x.sections.map((s) => ({ topic: s.topic, rating: s.rating === null ? "" : String(s.rating) })), strengths: x.strengths ?? "", improvements: x.improvements ?? "", comments: x.comments ?? "",
  };
}

function ScoreButtons({ value, onChange, scale, compact, allowNone }: { value: string; onChange: (v: string) => void; scale: { value: number; label: string }[]; compact?: boolean; allowNone?: boolean }) {
  return (
    <div className={clsx("flex flex-wrap gap-1.5", compact ? "" : "sm:gap-2")}>
      {scale.map((o) => {
        const on = value === String(o.value);
        return (
          <button type="button" key={o.value} onClick={() => onChange(on && allowNone ? "" : String(o.value))} title={o.label}
            className={clsx("rounded-xl border-2 font-semibold transition", compact ? "px-2.5 py-1 text-xs" : "min-w-[4.5rem] px-3 py-2 text-sm", on ? "text-white" : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50")}
            style={on ? { background: SCORE_COLOR[String(o.value)], borderColor: SCORE_COLOR[String(o.value)] } : undefined}>
            {o.value}{compact ? "" : ` · ${o.label}`}
          </button>
        );
      })}
      {allowNone && <button type="button" onClick={() => onChange("")} className={clsx("rounded-xl border-2 border-dashed px-2.5 py-1 text-xs font-medium", value === "" ? "border-slate-400 bg-slate-100 text-slate-700" : "border-slate-200 text-slate-400 hover:bg-slate-50")}>Not observed</button>}
    </div>
  );
}

export function FacilitatorForm({ spec, agenda, values, onChange, onSubmit, busy, submitLabel, errors, compact }: {
  spec: MeFacSpec; agenda: MeFacAgendaItem[]; values: FacValues; onChange: (v: FacValues) => void; onSubmit: () => void; busy: boolean; submitLabel: string; errors: string[]; compact?: boolean;
}) {
  const v = values;
  const set = <K extends keyof FacValues>(k: K, val: FacValues[K]) => onChange({ ...v, [k]: val });
  const input = compact ? "input" : "pub-input";
  const label = compact ? "mb-1 block text-xs font-medium text-slate-600" : "mb-1 block text-sm font-medium text-slate-700";
  const days = Array.from(new Set(agenda.map((a) => a.day))).sort((a, b) => a - b);
  const sc = facScore(v, spec);
  const chooseDay = (d: string) => {
    const n = Number(d);
    onChange({ ...v, training_day: d, sections: n >= 1 && agenda.some((a) => a.day === n) ? sectionsForDay(agenda, n) : v.sections });
  };
  const setSection = (i: number, patch: Partial<{ topic: string; rating: string }>) => set("sections", v.sections.map((s, j) => (j === i ? { ...s, ...patch } : s)));
  const H = ({ n, title, sub }: { n: string; title: string; sub?: string }) => (
    <div className={clsx("border-b border-slate-200 pb-1", compact ? "mt-4 mb-2" : "mt-7 mb-3")}><h2 className={clsx("font-bold text-navy", compact ? "text-sm" : "text-lg")}>{n}. {title}</h2>{sub && <p className="text-xs text-slate-500">{sub}</p>}</div>
  );

  return (
    <form onSubmit={(e) => { e.preventDefault(); onSubmit(); }} className="space-y-3">
      <H n="1" title="Where and who" sub="One rating per trainer, per day, per hall." />
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="block"><span className={label}>Date *</span><input className={input} type="date" max={today()} value={v.assessment_date} onChange={(e) => set("assessment_date", e.target.value)} /></label>
        <label className="block"><span className={label}>Training day *</span>
          {days.length ? (
            <select className={input} value={v.training_day} onChange={(e) => chooseDay(e.target.value)}><option value="">Choose…</option>{days.map((d) => <option key={d} value={d}>Day {d}</option>)}</select>
          ) : <input className={input} type="number" min={1} max={60} value={v.training_day} onChange={(e) => chooseDay(e.target.value)} placeholder="e.g. 2" />}
        </label>
        <label className="block"><span className={label}>District</span>
          <select className={input} value={v.district} onChange={(e) => set("district", e.target.value)}><option value="">National / HQ</option>{spec.districts.map((d) => <option key={d} value={d}>{d}</option>)}</select>
        </label>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="block"><span className={label}>Hall *</span><input className={input} value={v.hall} onChange={(e) => set("hall", e.target.value)} placeholder="e.g. Hall 2" maxLength={80} /></label>
        <label className="block"><span className={label}>M&amp;E monitor (your name) *</span><input className={input} value={v.monitor_name} onChange={(e) => set("monitor_name", e.target.value)} maxLength={160} /></label>
        <label className="block"><span className={label}>Trainer's name *</span><input className={input} value={v.trainer_name} onChange={(e) => set("trainer_name", e.target.value)} maxLength={160} /></label>
      </div>

      <H n="2" title="Section A · Assessment criteria" sub="Rate each of the trainer's strengths: 1 = Poor, 2 = Fair, 3 = Good, 4 = Excellent." />
      <div className="space-y-3">
        {spec.criteria.map((c, i) => (
          <div key={c.key} className={clsx("rounded-xl border px-3 py-3", v.scores[c.key] ? "border-slate-200 bg-white" : "border-amber-200 bg-amber-50/40")}>
            <div className={clsx("font-semibold text-slate-800", compact ? "text-sm" : "")}>{i + 1}. {c.label}</div>
            <div className="mb-2 text-xs text-slate-500">{c.help}</div>
            <ScoreButtons value={v.scores[c.key] ?? ""} onChange={(x) => set("scores", { ...v.scores, [c.key]: x })} scale={spec.scale} compact={compact} />
          </div>
        ))}
        <div className={clsx("flex flex-wrap items-center justify-between gap-2 rounded-xl px-4 py-3", sc.aDone ? "bg-navy text-white" : "bg-slate-100 text-slate-600")}>
          <span className="font-semibold">Total score: {sc.aDone ? sc.aTotal : "—"} / {spec.section_a_max}</span>
          <span className="text-sm">{sc.aDone ? `Overall rating: ${sc.bandA}` : "Rate all five criteria"}</span>
        </div>
        <p className="text-xs text-slate-500">{spec.bands.filter((b) => b.min_total > 0).map((b) => `${b.min_total}–${b.min_total === 17 ? 20 : b.min_total + 3}: ${b.label}`).join(" · ")} · 5–8: {spec.bands[3].label}</p>
      </div>

      <H n="3" title="Section B · Chapter / thematic section" sub="Rate how well the trainer facilitated each section of the day. Leave a section unrated if you did not observe it." />
      {v.sections.length === 0 && <p className="rounded-xl bg-sky-50 px-4 py-3 text-sm text-sky-900">{days.length ? "Choose the training day above to list the day's chapters." : "No chapter list for this training. Add the sections you observed."}</p>}
      <div className="space-y-2">
        {v.sections.map((s, i) => (
          <div key={i} className="flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 px-3 py-2">
            <input className={clsx(input, "min-w-[12rem] flex-1 py-1.5 text-sm")} value={s.topic} onChange={(e) => setSection(i, { topic: e.target.value })} placeholder="Chapter or section" maxLength={200} />
            <ScoreButtons value={s.rating} onChange={(x) => setSection(i, { rating: x })} scale={spec.scale} compact allowNone />
            <button type="button" className="text-xs text-red-700" onClick={() => set("sections", v.sections.filter((_, j) => j !== i))} title="Remove">✕</button>
          </div>
        ))}
      </div>
      <button type="button" className={compact ? "btn-outline" : "pub-btn-ghost"} onClick={() => set("sections", [...v.sections, { topic: "", rating: "" }])}>+ Add a section</button>
      <div className={clsx("flex flex-wrap items-center justify-between gap-2 rounded-xl px-4 py-3", sc.rated ? "bg-slate-800 text-white" : "bg-slate-100 text-slate-600")}>
        <span className="font-semibold">Section B: {sc.bTotal} / {sc.bMax} {sc.rated ? `(${sc.rated} section${sc.rated === 1 ? "" : "s"} rated)` : ""}</span>
        <span className="text-sm">{sc.pct === null ? "Overall % appears when section A is complete" : `Score: ${sc.pct}% · ${sc.band?.label}`}</span>
      </div>

      <H n="4" title="Comments" sub="Optional. Specific, so the trainer can act on them." />
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block"><span className={label}>Strengths observed</span><textarea className={input} rows={2} value={v.strengths} onChange={(e) => set("strengths", e.target.value)} /></label>
        <label className="block"><span className={label}>What to improve</span><textarea className={input} rows={2} value={v.improvements} onChange={(e) => set("improvements", e.target.value)} /></label>
      </div>
      <label className="block"><span className={label}>Other comments</span><textarea className={input} rows={2} value={v.comments} onChange={(e) => set("comments", e.target.value)} /></label>

      {errors.length > 0 && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"><div className="font-semibold">Please complete before sending</div><ul className="mt-1 list-disc pl-5">{errors.map((x) => <li key={x}>{x}</li>)}</ul></div>
      )}
      <div className={clsx("pt-2", compact ? "flex justify-end" : "")}>
        <button className={compact ? "btn-primary" : "pub-btn w-full"} disabled={busy}>{busy ? "Sending…" : submitLabel}</button>
      </div>
    </form>
  );
}
