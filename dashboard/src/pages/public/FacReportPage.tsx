import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import clsx from "clsx";
import { CheckCircle2, ClipboardList, Clock, Pencil, Users } from "lucide-react";
import { ApiError, api } from "../../api/client";
import SiteFooter from "../../components/SiteFooter";
import type { MeFacAgendaItem, MeFacReport, MeFacReportSpec } from "../../api/types";
import { PageWatermark } from "./EvaluatePage";

/* ------------------------------------------------------------------------------------------------
 * The public Daily Facilitator's Report page: /report/<token>, reached by link or QR code. No sign-in.
 * The Lead Facilitator of a hall sends one report per day; a sent report can be corrected from the same
 * device. The form follows the document "Daily FACILITATOR REPORT FORM – ToT in-person" section by section.
 * ---------------------------------------------------------------------------------------------- */

export type Round = { title: string; phase: string; period_start: string | null; period_end: string | null; description: string | null; status: string; agenda: MeFacAgendaItem[]; form: MeFacReportSpec };
export type Values = {
  report_date: string; training_day: string; venue: string; venue_other: string; hall: string; lead_facilitator: string; other_facilitators: string; email: string; phone: string;
  registered: string; present: string; delivered: string; missed_sessions: string[]; minutes_lost: string; missed_reason: string;
  ratings: Record<string, string>; e_internet: string; e_internet_details: string; e_power: string; e_power_details: string; e_devices: string; e_devices_details: string; e_food: string; e_food_details: string;
  went_right: string; repeat_share: string; went_wrong: string; difficult_topics: string[]; difficult_notes: string; recommendations: string; gaps: string; actors: string[]; actor_other: string; comments: string;
};
type Sent = { report_id: number; edit_token: string; report_date: string; training_day: string; venue: string; hall: string; lead_facilitator: string; mean_rating: number; attendance_pct: number | null; values: Values; sent_at: string };
type Store = { draft: Values | null; sent: Sent[] };

const PHASE_LABEL: Record<string, string> = { MASTER: "Master Training", TOT: "Training of Trainers", FIELD: "Field Staff Training" };
export const today = () => new Date().toISOString().slice(0, 10);
const fmtDate = (d: string | null) => (d ? new Date(d + "T00:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" }) : "");
export const SCALE_COLOR: Record<string, string> = { "5": "#15803d", "4": "#65a30d", "3": "#d97706", "2": "#ea580c", "1": "#b91c1c" };

export function emptyValues(): Values {
  return { report_date: today(), training_day: "", venue: "", venue_other: "", hall: "", lead_facilitator: "", other_facilitators: "", email: "", phone: "", registered: "", present: "", delivered: "", missed_sessions: [], minutes_lost: "", missed_reason: "",
    ratings: {}, e_internet: "", e_internet_details: "", e_power: "", e_power_details: "", e_devices: "", e_devices_details: "", e_food: "", e_food_details: "", went_right: "", repeat_share: "", went_wrong: "", difficult_topics: [], difficult_notes: "", recommendations: "", gaps: "", actors: [], actor_other: "", comments: "" };
}

export function fromReport(r: MeFacReport, spec: MeFacReportSpec): Values {
  const known = spec.venues.includes(r.venue);
  return { report_date: r.report_date, training_day: String(r.training_day), venue: known ? r.venue : "Other", venue_other: known ? "" : r.venue, hall: r.hall, lead_facilitator: r.lead_facilitator, other_facilitators: r.other_facilitators ?? "", email: r.email ?? "", phone: r.phone ?? "",
    registered: String(r.registered), present: String(r.present), delivered: r.delivered, missed_sessions: r.missed_sessions, minutes_lost: r.minutes_lost === null ? "" : String(r.minutes_lost), missed_reason: r.missed_reason ?? "",
    ratings: { knowledge: String(r.r_knowledge), engagement: String(r.r_engagement), illustrations: String(r.r_illustrations), connectivity: String(r.r_connectivity), coordination: String(r.r_coordination) },
    e_internet: r.e_internet === null ? "" : String(r.e_internet), e_internet_details: r.e_internet_details ?? "", e_power: r.e_power === null ? "" : String(r.e_power), e_power_details: r.e_power_details ?? "", e_devices: r.e_devices ?? "", e_devices_details: r.e_devices_details ?? "", e_food: r.e_food ?? "", e_food_details: r.e_food_details ?? "",
    went_right: r.went_right, repeat_share: r.repeat_share ?? "", went_wrong: r.went_wrong, difficult_topics: r.difficult_topics, difficult_notes: r.difficult_notes ?? "", recommendations: r.recommendations, gaps: r.gaps, actors: r.actors, actor_other: r.actor_other ?? "", comments: r.comments ?? "" };
}

export function validate(v: Values, spec: MeFacReportSpec): string[] {
  const e: string[] = [];
  if (!v.report_date) e.push("A · Date of training");
  if (!v.training_day) e.push("A · Training day");
  if (!v.venue || (v.venue === "Other" && !v.venue_other.trim())) e.push("A · Training venue");
  if (!v.hall.trim()) e.push("A · Classroom / hall");
  if (v.lead_facilitator.trim().length < 2) e.push("A · Name of the Lead Facilitator");
  if (!v.other_facilitators.trim()) e.push("A · Other facilitators (write N/A if none)");
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v.email.trim())) e.push("A · A valid email address");
  const reg = Number(v.registered), pres = Number(v.present);
  if (v.registered === "" || !Number.isFinite(reg) || reg < 0) e.push("B · Participants registered");
  if (v.present === "" || !Number.isFinite(pres) || pres < 0) e.push("B · Participants present today");
  if (v.registered !== "" && v.present !== "" && pres > reg) e.push("B · Present cannot exceed registered");
  if (!v.delivered) e.push("C · Were today's sessions delivered as scheduled?");
  if ((v.delivered === "PARTLY" || v.delivered === "NO") && !v.missed_reason.trim()) e.push("C · Which sessions, minutes lost and why");
  for (const r of spec.ratings) if (!v.ratings[r.key]) e.push(`D · ${r.label}`);
  if (v.went_right.trim().length < 3) e.push("F · What worked well today");
  if (v.went_wrong.trim().length < 3) e.push("G · What did not work well today");
  if (v.difficult_topics.length === 0 && !v.difficult_notes.trim()) e.push("G · Topics or skills that need reinforcement (choose chapters or write N/A)");
  if (v.recommendations.trim().length < 3) e.push("H · Recommended actions");
  if (v.gaps.trim().length < 3) e.push("H · Gaps, errors, redundancies or additional aids (write N/A if none)");
  if (v.actors.length === 0) e.push("H · Who should act");
  if (v.actors.includes("OTHER") && !v.actor_other.trim()) e.push("H · Specify who else should act");
  return e;
}

export function toPayload(v: Values) {
  const n = (s: string) => (s === "" ? null : Number(s));
  const t = (s: string) => (s.trim() ? s.trim() : null);
  return {
    report_date: v.report_date, training_day: Number(v.training_day), venue: v.venue === "Other" ? v.venue_other.trim() : v.venue, hall: v.hall.trim(), lead_facilitator: v.lead_facilitator.trim(), other_facilitators: t(v.other_facilitators),
    email: t(v.email), phone: t(v.phone), registered: Number(v.registered), present: Number(v.present), delivered: v.delivered, missed_sessions: v.missed_sessions, minutes_lost: n(v.minutes_lost), missed_reason: t(v.missed_reason),
    r_knowledge: Number(v.ratings.knowledge), r_engagement: Number(v.ratings.engagement), r_illustrations: Number(v.ratings.illustrations), r_connectivity: Number(v.ratings.connectivity), r_coordination: Number(v.ratings.coordination),
    e_internet: n(v.e_internet), e_internet_details: t(v.e_internet_details), e_power: n(v.e_power), e_power_details: t(v.e_power_details), e_devices: t(v.e_devices), e_devices_details: t(v.e_devices_details), e_food: t(v.e_food), e_food_details: t(v.e_food_details),
    went_right: v.went_right.trim(), repeat_share: t(v.repeat_share), went_wrong: v.went_wrong.trim(), difficult_topics: v.difficult_topics, difficult_notes: t(v.difficult_notes), recommendations: v.recommendations.trim(), gaps: v.gaps.trim(),
    actors: v.actors, actor_other: t(v.actor_other), comments: t(v.comments),
  };
}

/* ---- the form itself (also used by the dashboard's edit dialog) ------------------------------- */

const L = ({ n, text, req, hint, children }: { n?: string; text: string; req?: boolean; hint?: string; children: React.ReactNode }) => (
  <div>
    <div className="mb-1 text-sm font-medium text-slate-800">{n && <span className="mr-1.5 inline-block min-w-[1.6rem] rounded-md bg-slate-100 px-1.5 text-center text-xs font-bold text-slate-600">{n}</span>}{text}{req && <span className="text-red-600"> *</span>}</div>
    {hint && <div className="mb-1.5 text-xs text-slate-500">{hint}</div>}
    {children}
  </div>
);

function Section({ code, title, note, children }: { code: string; title: string; note?: string | null; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white">
      <header className="flex items-start gap-3 rounded-t-2xl border-b border-slate-100 bg-slate-50 px-4 py-3 sm:px-5">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-navy text-sm font-bold text-white">{code}</span>
        <div><h2 className="text-base font-bold text-navy">Section {code} · {title}</h2>{note && <p className="text-xs text-slate-500">{note}</p>}</div>
      </header>
      <div className="space-y-4 px-4 py-4 sm:px-5">{children}</div>
    </section>
  );
}

function Scale({ value, onChange, scale, compact = false }: { value: string; onChange: (v: string) => void; scale: { value: number; label: string }[]; compact?: boolean }) {
  return (
    <div className={clsx("grid gap-1.5", compact ? "grid-cols-5" : "grid-cols-5 sm:gap-2")}>
      {scale.map((s) => {
        const on = value === String(s.value);
        return <button type="button" key={s.value} onClick={() => onChange(on ? "" : String(s.value))} className={clsx("rounded-xl border-2 px-1 py-2 text-center transition", on ? "text-white" : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50")} style={on ? { background: SCALE_COLOR[String(s.value)], borderColor: SCALE_COLOR[String(s.value)] } : undefined}><div className="text-base font-bold leading-none">{s.value}</div><div className={clsx("mt-1 text-[10px] leading-tight", on ? "text-white/90" : "text-slate-500")}>{s.label}</div></button>;
      })}
    </div>
  );
}

function ChapterPicker({ agenda, day, selected, onChange, placeholder }: { agenda: MeFacAgendaItem[]; day: number; selected: string[]; onChange: (v: string[]) => void; placeholder: string }) {
  const items = agenda.filter((a) => a.day === day);
  const [custom, setCustom] = useState("");
  const toggle = (t: string) => onChange(selected.includes(t) ? selected.filter((x) => x !== t) : [...selected, t]);
  return (
    <div>
      {items.length === 0 && <p className="text-xs text-slate-500">{day ? "No chapters listed for this day; type the session below." : "Choose the training day in section A to list its chapters."}</p>}
      <div className="flex flex-wrap gap-1.5">
        {items.map((a) => { const on = selected.includes(a.topic); return <button type="button" key={a.id ?? a.topic} onClick={() => toggle(a.topic)} className={clsx("rounded-full border px-3 py-1.5 text-left text-xs font-medium", on ? "border-navy bg-navy text-white" : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50")}>{a.topic}</button>; })}
        {selected.filter((s) => !items.some((a) => a.topic === s)).map((s) => <button type="button" key={s} onClick={() => toggle(s)} className="rounded-full border border-navy bg-navy px-3 py-1.5 text-xs font-medium text-white">{s} ✕</button>)}
      </div>
      <div className="mt-2 flex gap-2">
        <input className="pub-input py-2 text-sm" placeholder={placeholder} value={custom} onChange={(e) => setCustom(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); if (custom.trim()) { onChange([...selected, custom.trim()]); setCustom(""); } } }} />
        <button type="button" className="pub-btn-ghost py-2 text-sm" onClick={() => { if (custom.trim()) { onChange([...selected, custom.trim()]); setCustom(""); } }}>Add</button>
      </div>
    </div>
  );
}

export function FacReportForm({ spec, agenda, values: v, onChange, onSubmit, busy, submitLabel, errors }: { spec: MeFacReportSpec; agenda: MeFacAgendaItem[]; values: Values; onChange: (v: Values) => void; onSubmit: () => void; busy: boolean; submitLabel: string; errors: string[] }) {
  const set = (p: Partial<Values>) => onChange({ ...v, ...p });
  const day = Number(v.training_day) || 0;
  const needsWhy = v.delivered === "PARTLY" || v.delivered === "NO";
  const attendance = v.registered && v.present && Number(v.registered) > 0 ? Math.round((100 * Number(v.present)) / Number(v.registered)) : null;
  const note = (code: string) => spec.sections.find((s) => s.code === code)?.note ?? null;
  return (
    <form className="space-y-5" onSubmit={(e) => { e.preventDefault(); onSubmit(); }}>
      <Section code="A" title="Report identification">
        <div className="grid gap-4 sm:grid-cols-2">
          <L n="1" text="Date of training" req><input type="date" className="pub-input" max={today()} value={v.report_date} onChange={(e) => set({ report_date: e.target.value })} /></L>
          <L n="2" text="Training day" req>
            <div className="grid grid-cols-5 gap-1.5">{spec.days.map((d) => <button type="button" key={d} onClick={() => set({ training_day: String(d), missed_sessions: [], difficult_topics: [] })} className={clsx("rounded-xl border-2 py-2 text-sm font-bold", v.training_day === String(d) ? "border-navy bg-navy text-white" : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50")}>{d}</button>)}</div>
          </L>
          <L n="3" text="Training venue / location" req>
            <div className="flex flex-wrap gap-1.5">{[...spec.venues, "Other"].map((x) => <button type="button" key={x} onClick={() => set({ venue: x })} className={clsx("rounded-full border px-3 py-1.5 text-sm font-medium", v.venue === x ? "border-navy bg-navy text-white" : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50")}>{x}</button>)}</div>
            {v.venue === "Other" && <input className="pub-input mt-2" placeholder="Name of the venue" value={v.venue_other} onChange={(e) => set({ venue_other: e.target.value })} />}
          </L>
          <L n="4" text="Classroom / hall" req><input className="pub-input" placeholder="e.g. Hall 3" value={v.hall} onChange={(e) => set({ hall: e.target.value })} maxLength={80} /></L>
          <L n="5" text="Name of the Lead Facilitator completing this report" req><input className="pub-input" value={v.lead_facilitator} onChange={(e) => set({ lead_facilitator: e.target.value })} maxLength={160} /></L>
          <L n="6" text="Other facilitators who delivered sessions and supported in this classroom today" req hint="Names, separated by commas. N/A if none."><input className="pub-input" value={v.other_facilitators} onChange={(e) => set({ other_facilitators: e.target.value })} maxLength={2000} /></L>
          <L text="Your email address" req hint="Recorded with the report, as on the paper form."><input type="email" className="pub-input" value={v.email} onChange={(e) => set({ email: e.target.value })} maxLength={160} /></L>
          <L text="Phone (optional)"><input className="pub-input" inputMode="tel" value={v.phone} onChange={(e) => set({ phone: e.target.value })} maxLength={32} /></L>
        </div>
      </Section>

      <Section code="B" title="Attendance and participation" note={note("B")}>
        <div className="grid gap-4 sm:grid-cols-3">
          <L n="7" text="Participants registered in this classroom" req><input type="number" min={0} max={1000} inputMode="numeric" className="pub-input" value={v.registered} onChange={(e) => set({ registered: e.target.value })} /></L>
          <L n="8" text="Participants present today" req hint="Count those present for most of the combined session."><input type="number" min={0} max={1000} inputMode="numeric" className="pub-input" value={v.present} onChange={(e) => set({ present: e.target.value })} /></L>
          <div className="flex items-end"><div className="w-full rounded-xl bg-slate-50 px-4 py-3 text-sm"><div className="text-xs text-slate-500">Attendance</div><div className={clsx("text-2xl font-bold", attendance === null ? "text-slate-400" : attendance >= 90 ? "text-emerald-700" : attendance >= 75 ? "text-amber-700" : "text-red-700")}>{attendance === null ? "—" : `${attendance}%`}</div></div></div>
        </div>
      </Section>

      <Section code="C" title="Delivery and time management" note={note("C")}>
        <L n="9" text="Were today's sessions delivered as scheduled in the agenda?" req>
          <div className="grid gap-2 sm:grid-cols-3">{spec.delivery.map((d) => <button type="button" key={d.value} onClick={() => set({ delivered: d.value })} className={clsx("rounded-xl border-2 px-3 py-3 text-sm font-semibold", v.delivered === d.value ? (d.value === "FULL" ? "border-emerald-600 bg-emerald-600 text-white" : d.value === "PARTLY" ? "border-amber-500 bg-amber-500 text-white" : "border-red-600 bg-red-600 text-white") : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50")}>{d.label}</button>)}</div>
        </L>
        {needsWhy && (
          <div className="space-y-3 rounded-xl border border-amber-200 bg-amber-50/60 p-3">
            <L n="10" text="Which sessions were affected?" hint="Tick the chapters of the day on the agenda, or add a session."><ChapterPicker agenda={agenda} day={day} selected={v.missed_sessions} onChange={(s) => set({ missed_sessions: s })} placeholder="Other session, e.g. D4.2" /></L>
            <div className="grid gap-3 sm:grid-cols-3">
              <L text="Minutes lost"><input type="number" min={0} max={1440} inputMode="numeric" className="pub-input" value={v.minutes_lost} onChange={(e) => set({ minutes_lost: e.target.value })} /></L>
              <div className="sm:col-span-2"><L text="Why?" req><textarea className="pub-input" rows={2} value={v.missed_reason} onChange={(e) => set({ missed_reason: e.target.value })} maxLength={4000} /></L></div>
            </div>
          </div>
        )}
      </Section>

      <Section code="D" title="Class rating at a glance" note={note("D")}>
        <div className="mb-1 text-xs text-slate-500">1 = Poor · 2 = Fair · 3 = Good · 4 = Very good · 5 = Excellent</div>
        <div className="divide-y divide-slate-100">
          {spec.ratings.map((r, i) => (
            <div key={r.key} className="grid items-center gap-2 py-3 sm:grid-cols-2">
              <div className="text-sm font-medium text-slate-800"><span className="mr-1.5 inline-block min-w-[1.6rem] rounded-md bg-slate-100 px-1.5 text-center text-xs font-bold text-slate-600">11.{i + 1}</span>{r.label}<span className="text-red-600"> *</span></div>
              <Scale value={v.ratings[r.key] ?? ""} onChange={(x) => set({ ratings: { ...v.ratings, [r.key]: x } })} scale={spec.scale} compact />
            </div>
          ))}
        </div>
      </Section>

      <Section code="E" title="Connectivity, power and logistics" note="Rating or value, with details: who was affected, backup used.">
        <div className="grid gap-4 sm:grid-cols-2">
          <L text="Internet connectivity (1–5)"><Scale value={v.e_internet} onChange={(x) => set({ e_internet: x })} scale={spec.scale} compact /><input className="pub-input mt-2 py-2 text-sm" placeholder="Details: who was affected, backup used" value={v.e_internet_details} onChange={(e) => set({ e_internet_details: e.target.value })} /></L>
          <L text="Power supply (1–5)"><Scale value={v.e_power} onChange={(x) => set({ e_power: x })} scale={spec.scale} compact /><input className="pub-input mt-2 py-2 text-sm" placeholder="Details: who was affected, backup used" value={v.e_power_details} onChange={(e) => set({ e_power_details: e.target.value })} /></L>
          <L text="Device shortages"><input className="pub-input" placeholder="e.g. 3 tablets short, or None" value={v.e_devices} onChange={(e) => set({ e_devices: e.target.value })} maxLength={200} /><input className="pub-input mt-2 py-2 text-sm" placeholder="Details: who was affected, backup used" value={v.e_devices_details} onChange={(e) => set({ e_devices_details: e.target.value })} /></L>
          <L text="Food & beverages"><input className="pub-input" placeholder="e.g. On time, Late, Not provided" value={v.e_food} onChange={(e) => set({ e_food: e.target.value })} maxLength={200} /><input className="pub-input mt-2 py-2 text-sm" placeholder="Details" value={v.e_food_details} onChange={(e) => set({ e_food_details: e.target.value })} /></L>
        </div>
      </Section>

      <Section code="F" title="What went right" note={note("F")}>
        <L n="12" text="What worked well today?" req hint="Cite session codes where possible."><textarea className="pub-input" rows={3} value={v.went_right} onChange={(e) => set({ went_right: e.target.value })} maxLength={4000} /></L>
        <L n="13" text="Which approach, tool or practice should be repeated or shared with the other halls?"><textarea className="pub-input" rows={2} value={v.repeat_share} onChange={(e) => set({ repeat_share: e.target.value })} maxLength={4000} /></L>
      </Section>

      <Section code="G" title="What went wrong" note={note("G")}>
        <L n="14" text="What did not work well today?" req hint="Cite session codes where possible."><textarea className="pub-input" rows={3} value={v.went_wrong} onChange={(e) => set({ went_wrong: e.target.value })} maxLength={4000} /></L>
        <L n="15" text="Topics or skills the class found most difficult and that need reinforcement" req hint="Tick the chapters of the day, or add a topic. Write N/A below if none."><ChapterPicker agenda={agenda} day={day} selected={v.difficult_topics} onChange={(s) => set({ difficult_topics: s })} placeholder="Other topic or skill" /><input className="pub-input mt-2 py-2 text-sm" placeholder="Notes (or N/A)" value={v.difficult_notes} onChange={(e) => set({ difficult_notes: e.target.value })} maxLength={4000} /></L>
      </Section>

      <Section code="H" title="Recommendations" note={note("H")}>
        <L n="16a" text="Recommended actions (what should change, and when)" req hint="For example: before tomorrow's session, during the DQM session, or before the next training phase."><textarea className="pub-input" rows={3} value={v.recommendations} onChange={(e) => set({ recommendations: e.target.value })} maxLength={4000} /></L>
        <L n="16b" text="Highlight gaps, factual errors, redundancies, additional illustrations or examples or teaching aids" req hint="N/A if none."><textarea className="pub-input" rows={3} value={v.gaps} onChange={(e) => set({ gaps: e.target.value })} maxLength={4000} /></L>
        <L n="17" text="Who should act?" req>
          <div className="grid gap-1.5 sm:grid-cols-2">{spec.actors.map((a) => { const on = v.actors.includes(a.value); return <label key={a.value} className={clsx("flex cursor-pointer items-center gap-2 rounded-xl border px-3 py-2 text-sm", on ? "border-navy bg-sky-50 text-navy" : "border-slate-200 bg-white text-slate-700")}><input type="checkbox" checked={on} onChange={() => set({ actors: on ? v.actors.filter((x) => x !== a.value) : [...v.actors, a.value] })} />{a.label}</label>; })}</div>
          {v.actors.includes("OTHER") && <input className="pub-input mt-2" placeholder="Who else should act?" value={v.actor_other} onChange={(e) => set({ actor_other: e.target.value })} maxLength={160} />}
        </L>
      </Section>

      <Section code="I" title="Closing" note={note("I")}>
        <L n="18" text="Additional comments"><textarea className="pub-input" rows={2} value={v.comments} onChange={(e) => set({ comments: e.target.value })} maxLength={4000} /></L>
      </Section>

      {errors.length > 0 && <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"><div className="font-semibold">Please complete:</div><ul className="mt-1 list-disc pl-5">{errors.map((x) => <li key={x}>{x}</li>)}</ul></div>}
      <div className="flex flex-col items-start gap-2 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-xs text-slate-500">Submission confirms the report reflects the classroom's session. One report per hall per day.</p>
        <button className="pub-btn" disabled={busy}>{busy ? "Sending…" : submitLabel}</button>
      </div>
    </form>
  );
}

/* ---- the public page ----------------------------------------------------------------------------- */

export default function FacReportPage() {
  const { token = "" } = useParams();
  const key = `me-facrep-${token}`;
  const [round, setRound] = useState<Round | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [store, setStore] = useState<Store>(() => { try { const s = localStorage.getItem(key); return s ? (JSON.parse(s) as Store) : { draft: null, sent: [] }; } catch { return { draft: null, sent: [] }; } });
  const [values, setValues] = useState<Values | null>(null);
  const [editing, setEditing] = useState<Sent | null>(null);
  const [done, setDone] = useState<Sent | null>(null);
  const [busy, setBusy] = useState(false);
  const [touched, setTouched] = useState(false);
  const [serverErrors, setServerErrors] = useState<string[]>([]);

  useEffect(() => {
    api.get<Round>(`/public/facreport/${token}`).then((r) => { setRound(r); setValues(store.draft ? { ...emptyValues(), ...store.draft } : emptyValues()); }).catch((e) => setLoadError(e instanceof ApiError ? e.message : "This link is not valid."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);
  useEffect(() => { try { localStorage.setItem(key, JSON.stringify(store)); } catch { /* private mode */ } }, [store, key]);
  useEffect(() => { if (values && !editing) setStore((s) => ({ ...s, draft: values })); }, [values, editing]);

  const errors = useMemo(() => (round && values ? validate(values, round.form) : []), [round, values]);

  const submit = async () => {
    if (!round || !values) return;
    setTouched(true);
    if (errors.length) { window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" }); return; }
    setBusy(true); setServerErrors([]);
    try {
      const body = { ...toPayload(values), ...(editing ? { report_id: editing.report_id, edit_token: editing.edit_token } : {}) };
      const r = await api.post<{ report_id: number; edit_token: string; mean_rating: number; attendance_pct: number | null }>(`/public/facreport/${token}/submit`, body);
      const sent: Sent = { report_id: r.report_id, edit_token: r.edit_token, report_date: values.report_date, training_day: values.training_day, venue: values.venue === "Other" ? values.venue_other : values.venue, hall: values.hall, lead_facilitator: values.lead_facilitator, mean_rating: r.mean_rating, attendance_pct: r.attendance_pct, values, sent_at: new Date().toISOString() };
      setStore((s) => ({ draft: null, sent: [sent, ...s.sent.filter((x) => x.report_id !== sent.report_id)].slice(0, 30) }));
      setDone(sent); setEditing(null); setTouched(false);
      // tomorrow's report keeps the venue, hall, facilitator and contact details
      setValues({ ...emptyValues(), venue: values.venue, venue_other: values.venue_other, hall: values.hall, lead_facilitator: values.lead_facilitator, email: values.email, phone: values.phone, registered: values.registered });
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      const detail = err instanceof ApiError ? (err.body as { detail?: string } | undefined)?.detail : undefined;
      setServerErrors([typeof detail === "string" ? detail : err instanceof ApiError ? err.message : "Could not send the report. Check your connection and try again; your answers are kept on this device."]);
    } finally { setBusy(false); }
  };
  const startEdit = (s: Sent) => { setEditing(s); setValues(s.values); setDone(null); window.scrollTo({ top: 0, behavior: "smooth" }); };

  return (
    <div className="relative min-h-screen overflow-hidden bg-[radial-gradient(ellipse_at_top_left,_#2a6aa6_0%,_#1F4E79_45%,_#0f3557_100%)] px-3 py-6 text-slate-800 sm:px-6 sm:py-10">
      <PageWatermark />
      <div className="relative mx-auto max-w-3xl">
        <header className="mb-5 flex items-center gap-3 text-white">
          <img src="/statsl-logo.png" alt="Statistics Sierra Leone" className="h-12 w-12 rounded-full bg-white p-0.5 shadow" />
          <div><div className="text-xs uppercase tracking-[0.25em] text-sky-200">Statistics Sierra Leone · 2026 PHC</div><div className="text-lg font-bold leading-tight">Daily Facilitator's Report</div></div>
        </header>
        {loadError ? (
          <Card><h1 className="text-xl font-bold">Link not valid</h1><p className="mt-2 text-slate-600">{loadError}</p></Card>
        ) : !round || !values ? (
          <Card><div className="animate-pulse text-slate-500">Loading…</div></Card>
        ) : round.status !== "OPEN" ? (
          <Card><h1 className="text-xl font-bold">{round.title}</h1><p className="mt-2 text-slate-600">This training is closed; reports are no longer accepted. Thank you.</p></Card>
        ) : (
          <div className="space-y-4">
            {done && (
              <Card className="border-l-4 border-emerald-500">
                <div className="flex items-start gap-3">
                  <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-emerald-700"><CheckCircle2 size={26} /></div>
                  <div><h2 className="text-lg font-bold text-navy">Report received — thank you</h2><p className="text-sm text-slate-600"><b>{done.hall}</b>, {done.venue}, day {done.training_day}: class rating {done.mean_rating.toFixed(1)} / 5{done.attendance_pct !== null ? `, attendance ${Math.round(done.attendance_pct)}%` : ""}. You can correct it below from this device.</p></div>
                </div>
              </Card>
            )}
            <Card className="overflow-hidden p-0 sm:p-0">
              <div className="bg-gradient-to-br from-navy via-[#245a8c] to-[#1b7f6b] px-5 py-6 text-white sm:px-8">
                <div className="text-xs uppercase tracking-[0.3em] text-sky-100/80">{round.form.subtitle}</div>
                <h1 className="mt-1 text-2xl font-bold leading-tight sm:text-3xl">{round.form.title}</h1>
                <div className="mt-2 flex flex-wrap items-center gap-2 text-xs"><span className="rounded-full bg-white/15 px-3 py-1 font-semibold">{round.title}</span><span className="rounded-full bg-white/15 px-3 py-1 font-semibold">{PHASE_LABEL[round.phase] ?? round.phase}</span>{(round.period_start || round.period_end) && <span className="text-sky-100">{fmtDate(round.period_start)}{round.period_end ? ` – ${fmtDate(round.period_end)}` : ""}</span>}</div>
                <p className="mt-4 max-w-2xl text-sm text-sky-50/90"><b>Purpose.</b> {round.form.purpose}</p>
                <div className="mt-4 grid gap-2 sm:grid-cols-3">
                  {[
                    { icon: <Users size={18} />, title: "One report per hall per day", text: "Submitted by the Lead Facilitator of the hall. Not an individual facilitator report." },
                    { icon: <Clock size={18} />, title: "Same day, by 6:00 p.m.", text: "After the day's sessions. Be candid and objective: give evidence, not impressions." },
                    { icon: <ClipboardList size={18} />, title: "Scale 1 to 5", text: "1 Poor · 2 Fair · 3 Good · 4 Very good · 5 Excellent. Fields marked * are mandatory; write N/A where not applicable." },
                  ].map((b) => <div key={b.title} className="rounded-xl bg-white/10 p-3 backdrop-blur-sm"><div className="flex items-center gap-2 text-sm font-semibold">{b.icon} {b.title}</div><div className="mt-1 text-xs text-sky-50/85">{b.text}</div></div>)}
                </div>
                <p className="mt-3 text-xs text-sky-100/80"><b>Note:</b> {round.form.note}</p>
              </div>
              <div className="px-4 py-5 sm:px-6 sm:py-7">
                {editing && <div className="mb-4 flex items-center justify-between gap-3 rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-900"><span><Pencil size={14} className="mr-1 inline" /> Correcting the report of <b>{editing.hall}</b>, {editing.venue}, day {editing.training_day}.</span><button type="button" className="font-semibold underline" onClick={() => { setEditing(null); setValues(store.draft ?? emptyValues()); }}>Cancel</button></div>}
                {serverErrors.length > 0 && <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"><div className="font-semibold">The server could not accept the report</div><ul className="mt-1 list-disc pl-5">{serverErrors.map((x) => <li key={x}>{x}</li>)}</ul></div>}
                <FacReportForm spec={round.form} agenda={round.agenda} values={values} onChange={setValues} onSubmit={submit} busy={busy} submitLabel={editing ? "Send the correction" : "Submit today's report"} errors={touched ? errors : []} />
              </div>
            </Card>
            {store.sent.length > 0 && (
              <Card>
                <h2 className="text-base font-bold text-navy">My sent reports <span className="text-xs font-normal text-slate-400">(this device)</span></h2>
                <ul className="mt-2 divide-y divide-slate-100 text-sm">
                  {store.sent.map((s) => <li key={s.report_id} className="flex items-center justify-between gap-3 py-2"><span><b>{s.hall}</b> · {s.venue} · day {s.training_day} · {fmtDate(s.report_date)} · rating {s.mean_rating.toFixed(1)}/5</span><button type="button" className={clsx("pub-btn-ghost py-1.5 text-sm", editing?.report_id === s.report_id && "text-navy")} onClick={() => startEdit(s)}><Pencil size={14} /> Correct</button></li>)}
                </ul>
              </Card>
            )}
          </div>
        )}
        <p className="mt-6 text-center text-xs text-sky-100/70">Reports are seen only by the Training Coordinator, the CTA and the Monitoring &amp; Evaluation team.</p>
        <SiteFooter tone="dark" className="mt-8" />
      </div>
    </div>
  );
}

function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={clsx("rounded-2xl bg-white p-5 shadow-xl shadow-black/20 sm:p-8", className)}>{children}</div>;
}
