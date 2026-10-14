import { useState } from "react";
import clsx from "clsx";
import { AlertTriangle, BookOpenCheck, CalendarClock, ClipboardList, Plug, Star, Users } from "lucide-react";
import type { MeDailyAgendaItem } from "../../api/types";

/* ------------------------------------------------------------------------------------------------
 * The Daily Facilitator Report form, rendered from the server's spec (app/core/me_daily_form.py).
 * Used by the public page (lead facilitators) and by the dashboard's edit dialog (M&E staff).
 * ---------------------------------------------------------------------------------------------- */

export type Opt = { value: string | number; label: string };
export type DailySpec = {
  title: string; subtitle: string; intro: string; instructions: string; scale_text: string;
  phases: Opt[]; scale: Opt[]; delivered: Opt[]; quality: Opt[]; issue_types: Opt[]; severities: Opt[]; escalation_status: Opt[]; logistics: Opt[]; districts: string[]; evidence_scores: number[];
};
export type SessionValue = { topic: string; planned_start: string; planned_end: string; actual_start: string; actual_end: string; delivered: string; reason: string; details?: string; responsible?: string; other?: boolean };
export type IssueValue = { item: string; type: string; severity: string; correction: string };
export type EscalationValue = { issue: string; raised_to: string; owner: string; needed_by: string; status: string };
export type DailyValues = {
  phase: string; platform_venue: string; class_hall: string; training_day: string; report_date: string; lead_facilitator: string; co_facilitators: string; district: string;
  sessions: SessionValue[]; carried_over: string[];
  quiz_administered: "" | "yes" | "no"; quiz_title: string; mean_score: string; pass_rate: string; quiz_comments: string; practice_minutes: string; practice_comments: string; hardest_topics: string[]; hardest_comments: string;
  q_content: string; q_content_evidence: string; q_engagement: string; q_engagement_evidence: string; q_time: string; q_time_evidence: string; q_illustrations: string; q_illustrations_evidence: string;
  material_issues: IssueValue[];
  g_internet: string; g_internet_details: string; g_power: string; g_power_details: string; g_devices: string; g_devices_details: string; g_food: string; g_food_details: string;
  escalations: EscalationValue[];
};
type QKey = "content" | "engagement" | "time" | "illustrations";

export const today = () => new Date().toISOString().slice(0, 10);
export const emptySession = (): SessionValue => ({ topic: "", planned_start: "", planned_end: "", actual_start: "", actual_end: "", delivered: "", reason: "" });
const emptyIssue = (): IssueValue => ({ item: "", type: "", severity: "", correction: "" });
const emptyEscalation = (): EscalationValue => ({ issue: "", raised_to: "", owner: "", needed_by: "", status: "OPEN" });

export function emptyValues(phase = "FIELD"): DailyValues {
  return {
    phase, platform_venue: "", class_hall: "", training_day: "", report_date: today(), lead_facilitator: "", co_facilitators: "", district: "",
    sessions: [], carried_over: [],
    quiz_administered: "", quiz_title: "", mean_score: "", pass_rate: "", quiz_comments: "", practice_minutes: "", practice_comments: "", hardest_topics: [], hardest_comments: "",
    q_content: "", q_content_evidence: "", q_engagement: "", q_engagement_evidence: "", q_time: "", q_time_evidence: "", q_illustrations: "", q_illustrations_evidence: "",
    material_issues: [], g_internet: "", g_internet_details: "", g_power: "", g_power_details: "", g_devices: "", g_devices_details: "", g_food: "", g_food_details: "",
    escalations: [],
  };
}

/** The agenda rows of a training day, as pre-filled session rows. */
export function sessionsForDay(agenda: MeDailyAgendaItem[], day: number): SessionValue[] {
  return agenda.filter((a) => a.day === day).map((a) => ({ topic: a.topic, planned_start: a.planned_start ?? "", planned_end: a.planned_end ?? "", actual_start: "", actual_end: "", delivered: "", reason: "", details: a.details ?? undefined, responsible: a.responsible ?? undefined }));
}

const mins = (t: string) => (/^([01]\d|2[0-3]):[0-5]\d$/.test(t) ? Number(t.slice(0, 2)) * 60 + Number(t.slice(3)) : null);
export const sessionDelta = (s: SessionValue): number | null => {
  const ps = mins(s.planned_start), pe = mins(s.planned_end), as = mins(s.actual_start), ae = mins(s.actual_end);
  return ps === null || pe === null || as === null || ae === null ? null : (ae - as) - (pe - ps);
};

/** What the server expects (numbers as numbers, blanks as null). */
export function toPayload(v: DailyValues) {
  const n = (s: string) => (s.trim() === "" ? null : Number(s));
  const t = (s: string) => (s.trim() === "" ? null : s.trim());
  return {
    phase: v.phase, platform_venue: v.platform_venue.trim(), class_hall: v.class_hall.trim(), training_day: Number(v.training_day), report_date: v.report_date,
    lead_facilitator: v.lead_facilitator.trim(), co_facilitators: t(v.co_facilitators), district: v.district || null,
    sessions: v.sessions.filter((s) => s.topic.trim() || s.delivered || s.actual_start).map((s) => ({ topic: s.topic.trim(), planned_start: t(s.planned_start), planned_end: t(s.planned_end), actual_start: t(s.actual_start), actual_end: t(s.actual_end), delivered: s.delivered || null, reason: t(s.reason) })),
    carried_over: v.carried_over,
    quiz_administered: v.quiz_administered === "" ? null : v.quiz_administered === "yes", quiz_title: t(v.quiz_title), mean_score: n(v.mean_score), pass_rate: n(v.pass_rate), quiz_comments: t(v.quiz_comments),
    practice_minutes: n(v.practice_minutes), practice_comments: t(v.practice_comments), hardest_topics: v.hardest_topics, hardest_comments: t(v.hardest_comments),
    q_content: n(v.q_content), q_content_evidence: t(v.q_content_evidence), q_engagement: n(v.q_engagement), q_engagement_evidence: t(v.q_engagement_evidence),
    q_time: n(v.q_time), q_time_evidence: t(v.q_time_evidence), q_illustrations: n(v.q_illustrations), q_illustrations_evidence: t(v.q_illustrations_evidence),
    material_issues: v.material_issues.filter((m) => (m.item + m.correction).trim() || m.type || m.severity).map((m) => ({ item: m.item.trim(), type: m.type || null, severity: m.severity || null, correction: t(m.correction) })),
    g_internet: n(v.g_internet), g_internet_details: t(v.g_internet_details), g_power: n(v.g_power), g_power_details: t(v.g_power_details), g_devices: n(v.g_devices), g_devices_details: t(v.g_devices_details), g_food: n(v.g_food), g_food_details: t(v.g_food_details),
    escalations: v.escalations.filter((x) => (x.issue + x.raised_to + x.owner).trim()).map((x) => ({ issue: x.issue.trim(), raised_to: t(x.raised_to), owner: t(x.owner), needed_by: t(x.needed_by), status: x.status || "OPEN" })),
  };
}

/** The same checks as the server, so the facilitator sees them before sending. */
export function validate(v: DailyValues, spec: DailySpec): string[] {
  const e: string[] = [];
  if (!v.phase) e.push("A: tick the training phase / mode");
  if (!v.platform_venue.trim()) e.push("A: enter the platform / venue");
  if (!v.class_hall.trim()) e.push("A: enter the class / hall");
  if (!v.training_day || Number(v.training_day) < 1) e.push("A: enter the training day number");
  if (!v.report_date) e.push("A: enter the date");
  if (v.report_date > today()) e.push("A: the date cannot be in the future");
  if (v.lead_facilitator.trim().length < 2) e.push("A: enter the lead facilitator's name");
  const sessions = v.sessions.filter((s) => s.topic.trim() || s.delivered || s.actual_start);
  if (sessions.length === 0) e.push("C: add the day's sessions (at least one)");
  sessions.forEach((s, i) => {
    if (!s.topic.trim()) e.push(`Session ${i + 1}: give the topic`);
    if (!s.delivered) e.push(`Session ${i + 1}: tick Delivered Y, P or N`);
    for (const [k, label] of [["planned_start", "planned start"], ["planned_end", "planned end"], ["actual_start", "actual start"], ["actual_end", "actual end"]] as const) if (s[k] && mins(s[k]) === null) e.push(`Session ${i + 1}: ${label} must be HH:MM`);
    if ((s.delivered === "P" || s.delivered === "N") && !s.reason.trim()) e.push(`Session ${i + 1}: give the reason when a session is partly or not delivered`);
    const ps = mins(s.planned_start), pe = mins(s.planned_end), as = mins(s.actual_start), ae = mins(s.actual_end);
    if (ps !== null && pe !== null && pe <= ps) e.push(`Session ${i + 1}: planned end must be after planned start`);
    if (as !== null && ae !== null && ae <= as) e.push(`Session ${i + 1}: actual end must be after actual start`);
    if (s.delivered === "Y" && (as === null || ae === null)) e.push(`Session ${i + 1}: give the actual start and end of a delivered session`);
  });
  if (v.quiz_administered === "") e.push("D: say whether a quiz / assessment was administered");
  else if (v.quiz_administered === "yes") {
    if (!v.quiz_title.trim()) e.push("D: give the quiz / assessment title");
    if (v.mean_score.trim() === "" || v.pass_rate.trim() === "") e.push("D: give the mean score and the pass rate (%)");
  }
  if (v.practice_minutes.trim() === "" && !v.practice_comments.trim()) e.push("D: give the practical / CAPI hands-on minutes, or N/A with the reason in Comments");
  for (const q of spec.quality) {
    const key = q.value as QKey;
    const score = Number(v[`q_${key}`]);
    const name = String(q.label).replace(/^\d+\.\s*/, "").toLowerCase();
    if (!v[`q_${key}`]) e.push(`E: rate ${name} from 1 to 5`);
    else if (spec.evidence_scores.includes(score) && !v[`q_${key}_evidence`].trim()) e.push(`E: evidence / justification is required for a score of ${score} on ${name}`);
  }
  v.material_issues.filter((m) => (m.item + m.correction).trim() || m.type || m.severity).forEach((m, i) => {
    if (!m.item.trim()) e.push(`F issue ${i + 1}: give the item (manual chapter, quiz, questionnaire ref.)`);
    if (!m.type) e.push(`F issue ${i + 1}: choose the type`);
    if (!m.severity) e.push(`F issue ${i + 1}: choose the severity H, M or L`);
  });
  for (const [k, label] of [["g_internet", "internet connectivity"], ["g_power", "power supply"], ["g_food", "food & beverages"]] as const) if (!v[k]) e.push(`G: rate ${label} from 1 to 5`);
  if (v.g_devices.trim() === "") e.push("G: give the number of devices short (0 if none)");
  v.escalations.filter((x) => (x.issue + x.raised_to + x.owner).trim()).forEach((x, i) => {
    if (!x.issue.trim()) e.push(`H escalation ${i + 1}: describe the issue requiring management / CCIT action`);
    if (!x.raised_to.trim()) e.push(`H escalation ${i + 1}: say who it was raised to`);
  });
  return e;
}

export function DailyReportForm({ spec, agenda, values, onChange, onSubmit, busy, submitLabel, errors, compact }: {
  spec: DailySpec; agenda: MeDailyAgendaItem[]; values: DailyValues; onChange: (v: DailyValues) => void; onSubmit: () => void; busy: boolean; submitLabel: string; errors: string[]; compact?: boolean;
}) {
  const v = values;
  const set = <K extends keyof DailyValues>(k: K, val: DailyValues[K]) => onChange({ ...v, [k]: val });
  const [touched, setTouched] = useState(false);
  const day = Number(v.training_day);
  const dayAgenda = agenda.filter((a) => a.day === day);
  const agendaDays = Array.from(new Set(agenda.map((a) => a.day))).sort((a, b) => a - b);
  const groups: { label: string; topics: string[] }[] = [
    ...(day >= 1 && dayAgenda.length ? [{ label: `Day ${day} (today)`, topics: Array.from(new Set(dayAgenda.map((a) => a.topic))) }] : []),
    ...agendaDays.filter((d) => d !== day || !dayAgenda.length).map((d) => ({ label: `Day ${d}`, topics: Array.from(new Set(agenda.filter((a) => a.day === d).map((a) => a.topic))) })),
  ];
  const typed = v.sessions.map((s) => s.topic.trim()).filter((t) => t && !agenda.some((a) => a.topic === t));
  if (typed.length) groups.push({ label: "Typed on this form", topics: Array.from(new Set(typed)) });
  const pickSession = (i: number, topic: string) => {
    if (topic === "__other") { setSession(i, { topic: "", other: true, details: undefined, responsible: undefined }); return; }
    const a = agenda.find((x) => x.topic === topic && x.day === day) ?? agenda.find((x) => x.topic === topic);
    setSession(i, { topic, other: false, planned_start: a?.planned_start ?? v.sessions[i].planned_start, planned_end: a?.planned_end ?? v.sessions[i].planned_end, details: a?.details ?? undefined, responsible: a?.responsible ?? undefined });
  };
  const setSession = (i: number, patch: Partial<SessionValue>) => set("sessions", v.sessions.map((s, j) => (j === i ? { ...s, ...patch } : s)));
  const setDay = (d: string) => {
    const n = Number(d);
    const next = { ...v, training_day: d };
    if (n >= 1 && v.sessions.every((s) => !s.actual_start && !s.delivered && !s.reason)) next.sessions = sessionsForDay(agenda, n);
    onChange(next);
  };
  const toggleIn = (k: "carried_over" | "hardest_topics", topic: string) => set(k, v[k].includes(topic) ? v[k].filter((x) => x !== topic) : [...v[k], topic]);

  return (
    <form className={compact ? "space-y-5" : "space-y-7"} onSubmit={(e) => { e.preventDefault(); setTouched(true); onSubmit(); }}>
      <p className="rounded-xl bg-sky-50 px-4 py-3 text-xs text-sky-900">{spec.scale_text}</p>

      <Section icon={<ClipboardList size={18} />} code="A" title="Identification">
        <Choice label="Training phase / mode *" options={spec.phases} value={v.phase} onPick={(x) => set("phase", String(x))} />
        <div className="grid gap-3 sm:grid-cols-2">
          <L label="Platform / venue *"><input className="pub-input" value={v.platform_venue} onChange={(e) => set("platform_venue", e.target.value)} placeholder="e.g. Bo Teachers College or Zoom" /></L>
          <L label="Class / hall *"><input className="pub-input" value={v.class_hall} onChange={(e) => set("class_hall", e.target.value)} placeholder="e.g. Hall 2" /></L>
          <L label="Training day no. *"><input className="pub-input" type="number" min={1} max={60} inputMode="numeric" value={v.training_day} onChange={(e) => setDay(e.target.value)} placeholder="1, 2, 3…" /></L>
          <L label="Date *"><input className="pub-input" type="date" max={today()} value={v.report_date} onChange={(e) => set("report_date", e.target.value)} /></L>
          <L label="Lead *"><input className="pub-input" value={v.lead_facilitator} onChange={(e) => set("lead_facilitator", e.target.value)} placeholder="Your name or ID" autoComplete="name" /></L>
          <L label="Co-facilitators ID"><input className="pub-input" value={v.co_facilitators} onChange={(e) => set("co_facilitators", e.target.value)} placeholder="IDs, separated by commas" /></L>
          <L label="District">
            <select className="pub-input" value={v.district} onChange={(e) => set("district", e.target.value)}>
              <option value="">National / HQ</option>
              {spec.districts.map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
          </L>
        </div>
      </Section>

      <Section icon={<CalendarClock size={18} />} code="C" title="Schedule and content coverage *">
        <p className="text-xs text-slate-500">{dayAgenda.length ? `The agenda for day ${day} is filled in. Enter the actual times and tick Delivered for each session; minutes over (+) or under (−) are computed.` : "No agenda is loaded for this day: add each session with its planned and actual times."}</p>
        <div className="space-y-3">
          {v.sessions.map((s, i) => {
            const delta = sessionDelta(s);
            return (
              <div key={i} className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                <div className="mb-2 flex items-start gap-2">
                  <div className="flex-1">
                    <span className="mb-1 block text-xs font-medium text-slate-600">Session / topic {i + 1}</span>
                    {agenda.length > 0 && (
                      <select className="pub-input bg-white" value={s.other || (s.topic && !agenda.some((a) => a.topic === s.topic)) ? "__other" : s.topic} onChange={(e) => pickSession(i, e.target.value)}>
                        <option value="">Choose the session from the agenda…</option>
                        {groups.filter((g) => g.label !== "Typed on this form").map((g) => <optgroup key={g.label} label={g.label}>{g.topics.map((t) => <option key={t} value={t}>{t}</option>)}</optgroup>)}
                        <option value="__other">Other (not on the agenda)</option>
                      </select>
                    )}
                    {(agenda.length === 0 || s.other || (s.topic && !agenda.some((a) => a.topic === s.topic))) && (
                      <input className="pub-input mt-1 bg-white" value={s.topic} onChange={(e) => setSession(i, { topic: e.target.value })} placeholder={agenda.length ? "Type the topic" : "Topic"} />
                    )}
                    {(s.details || s.responsible) && <div className="mt-1 text-xs text-slate-500">{s.details}{s.details && s.responsible ? " · " : ""}{s.responsible && <span className="text-slate-400">Responsible: {s.responsible}</span>}</div>}
                  </div>
                  <button type="button" className="mt-5 text-sm text-red-700" onClick={() => set("sessions", v.sessions.filter((_, j) => j !== i))}>Remove</button>
                </div>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
                  <L small label="Planned start"><input className="pub-input bg-white py-2" type="time" value={s.planned_start} onChange={(e) => setSession(i, { planned_start: e.target.value })} /></L>
                  <L small label="Planned end"><input className="pub-input bg-white py-2" type="time" value={s.planned_end} onChange={(e) => setSession(i, { planned_end: e.target.value })} /></L>
                  <L small label="Actual start"><input className="pub-input bg-white py-2" type="time" value={s.actual_start} onChange={(e) => setSession(i, { actual_start: e.target.value })} /></L>
                  <L small label="Actual end"><input className="pub-input bg-white py-2" type="time" value={s.actual_end} onChange={(e) => setSession(i, { actual_end: e.target.value })} /></L>
                  <div>
                    <span className="mb-1 block text-xs font-medium text-slate-600">Minutes over / under</span>
                    <div className={clsx("rounded-xl border px-3 py-2 text-center font-semibold", delta === null ? "border-slate-200 bg-white text-slate-400" : delta > 0 ? "border-amber-300 bg-amber-50 text-amber-800" : delta < 0 ? "border-sky-300 bg-sky-50 text-sky-800" : "border-emerald-300 bg-emerald-50 text-emerald-800")}>{delta === null ? "—" : delta > 0 ? `+${delta}` : delta}</div>
                  </div>
                </div>
                <div className="mt-2 grid gap-2 sm:grid-cols-[auto_1fr] sm:items-end">
                  <div>
                    <span className="mb-1 block text-xs font-medium text-slate-600">Delivered</span>
                    <div className="flex gap-1">
                      {spec.delivered.map((o) => (
                        <button type="button" key={String(o.value)} onClick={() => setSession(i, { delivered: String(o.value) })} title={o.label}
                          className={clsx("h-10 w-12 rounded-xl border text-sm font-bold", s.delivered === o.value ? (o.value === "Y" ? "border-emerald-600 bg-emerald-600 text-white" : o.value === "P" ? "border-amber-500 bg-amber-500 text-white" : "border-red-600 bg-red-600 text-white") : "border-slate-300 bg-white text-slate-700")}>{o.value}</button>
                      ))}
                    </div>
                  </div>
                  <L small label="Reason (carry-over, delay, why partly or not delivered)"><input className="pub-input bg-white py-2" value={s.reason} onChange={(e) => setSession(i, { reason: e.target.value })} /></L>
                </div>
              </div>
            );
          })}
          <div className="flex flex-wrap gap-2">
            <button type="button" className="pub-btn-ghost border border-slate-300" onClick={() => set("sessions", [...v.sessions, emptySession()])}>+ Add session</button>
            {dayAgenda.length > 0 && v.sessions.length === 0 && <button type="button" className="pub-btn-ghost border border-slate-300" onClick={() => set("sessions", sessionsForDay(agenda, day))}>Load day {day} agenda</button>}
          </div>
        </div>
        <TopicPicker label="Content carried to next day" groups={groups} values={v.carried_over} onToggle={(t) => toggleIn("carried_over", t)} />
      </Section>

      <Section icon={<BookOpenCheck size={18} />} code="D" title="Participant performance and learning">
        <div className="grid gap-3 sm:grid-cols-[auto_1fr] sm:items-end">
          <div>
            <span className="mb-1 block text-sm font-medium text-slate-700">Quiz / assessment administered</span>
            <div className="flex gap-2">{(["yes", "no"] as const).map((x) => <button type="button" key={x} onClick={() => set("quiz_administered", x)} className={clsx("rounded-xl border px-5 py-2 text-sm font-semibold", v.quiz_administered === x ? "border-navy bg-navy text-white" : "border-slate-300 bg-white text-slate-700")}>{x === "yes" ? "Y" : "N"}</button>)}</div>
          </div>
          {v.quiz_administered === "yes" && <L label="Title"><input className="pub-input" value={v.quiz_title} onChange={(e) => set("quiz_title", e.target.value)} placeholder="e.g. Day 1 quiz" /></L>}
        </div>
        {v.quiz_administered === "yes" && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <L label="Mean score (%)"><input className="pub-input" type="number" min={0} max={100} step="0.1" inputMode="decimal" value={v.mean_score} onChange={(e) => set("mean_score", e.target.value)} /></L>
            <L label="Pass rate (%)"><input className="pub-input" type="number" min={0} max={100} step="0.1" inputMode="decimal" value={v.pass_rate} onChange={(e) => set("pass_rate", e.target.value)} /></L>
            <L label="Comments"><input className="pub-input" value={v.quiz_comments} onChange={(e) => set("quiz_comments", e.target.value)} /></L>
          </div>
        )}
        <div className="grid gap-3 sm:grid-cols-[1fr_2fr]">
          <L label="Practical / CAPI hands-on time (minutes)"><input className="pub-input" type="number" min={0} inputMode="numeric" value={v.practice_minutes} onChange={(e) => set("practice_minutes", e.target.value)} /></L>
          <L label="Comments (write N/A and the reason if none)"><input className="pub-input" value={v.practice_comments} onChange={(e) => set("practice_comments", e.target.value)} /></L>
        </div>
        <TopicPicker label="Topics participants found hardest" groups={groups} values={v.hardest_topics} onToggle={(t) => toggleIn("hardest_topics", t)} />
        <L label="Comments"><input className="pub-input" value={v.hardest_comments} onChange={(e) => set("hardest_comments", e.target.value)} placeholder="What made them hard" /></L>
      </Section>

      <Section icon={<Star size={18} />} code="E" title="Facilitation quality (rate 1–5; evidence required for scores of 1, 2 or 5) *">
        {spec.quality.map((q) => {
          const key = q.value as QKey;
          const score = v[`q_${key}`];
          const needs = spec.evidence_scores.includes(Number(score));
          return (
            <div key={key} className="rounded-xl border border-slate-200 p-3">
              <div className="mb-2 text-sm font-medium text-slate-700">{q.label}</div>
              <Scale value={score} onPick={(x) => set(`q_${key}`, x)} />
              <L small label={needs ? "Evidence / justification (required for this score)" : "Evidence / justification"}><input className={clsx("pub-input py-2", needs && !v[`q_${key}_evidence`].trim() && "border-amber-400")} value={v[`q_${key}_evidence`]} onChange={(e) => set(`q_${key}_evidence`, e.target.value)} /></L>
            </div>
          );
        })}
        {(() => {
          const xs = (["content", "engagement", "time", "illustrations"] as QKey[]).map((k) => Number(v[`q_${k}`])).filter((x) => x > 0);
          const mean = xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null;
          return (
            <div className="flex items-center justify-between rounded-xl bg-navy px-4 py-3 text-white">
              <div>
                <div className="text-sm font-medium">Overall class rating (mean of 1–5)</div>
                <div className="text-xs text-sky-100/80">{xs.length === 4 ? "Computed from the four scores above." : `Computed automatically: ${xs.length} of 4 criteria rated so far.`}</div>
              </div>
              <span className="text-2xl font-bold">{mean === null ? "—" : mean.toFixed(2)}</span>
            </div>
          );
        })()}
      </Section>

      <Section icon={<AlertTriangle size={18} />} code="F" title="Materials and assessment issues log">
        {v.material_issues.map((m, i) => (
          <div key={i} className="grid gap-2 rounded-xl border border-slate-200 bg-slate-50 p-3 sm:grid-cols-[auto_2fr_1fr_1fr_2fr_auto] sm:items-end">
            <div className="text-sm font-semibold text-slate-500">#{i + 1}</div>
            <L small label="Item (manual chapter, quiz, questionnaire ref.)"><input className="pub-input bg-white py-2" value={m.item} onChange={(e) => set("material_issues", v.material_issues.map((x, j) => (j === i ? { ...x, item: e.target.value } : x)))} /></L>
            <L small label="Type"><select className="pub-input bg-white py-2" value={m.type} onChange={(e) => set("material_issues", v.material_issues.map((x, j) => (j === i ? { ...x, type: e.target.value } : x)))}><option value="">Choose…</option>{spec.issue_types.map((o) => <option key={String(o.value)} value={String(o.value)}>{o.label}</option>)}</select></L>
            <L small label="Severity"><select className="pub-input bg-white py-2" value={m.severity} onChange={(e) => set("material_issues", v.material_issues.map((x, j) => (j === i ? { ...x, severity: e.target.value } : x)))}><option value="">H / M / L</option>{spec.severities.map((o) => <option key={String(o.value)} value={String(o.value)}>{o.value} · {o.label}</option>)}</select></L>
            <L small label="Proposed correction"><input className="pub-input bg-white py-2" value={m.correction} onChange={(e) => set("material_issues", v.material_issues.map((x, j) => (j === i ? { ...x, correction: e.target.value } : x)))} /></L>
            <button type="button" className="pb-2 text-sm text-red-700" onClick={() => set("material_issues", v.material_issues.filter((_, j) => j !== i))}>Remove</button>
          </div>
        ))}
        <button type="button" className="pub-btn-ghost border border-slate-300" onClick={() => set("material_issues", [...v.material_issues, emptyIssue()])}>+ Add issue</button>
        {v.material_issues.length === 0 && <p className="text-xs text-slate-400">No materials or assessment issue today.</p>}
      </Section>

      <Section icon={<Plug size={18} />} code="G" title="Connectivity, power and logistics">
        {([["internet", "Internet connectivity"], ["power", "Power supply"], ["food", "Food & beverages"]] as const).map(([k, label]) => (
          <div key={k} className="grid gap-2 rounded-xl border border-slate-200 p-3 sm:grid-cols-[1fr_1fr]">
            <div><div className="mb-1 text-sm font-medium text-slate-700">{label} (1–5)</div><Scale value={v[`g_${k}`]} onPick={(x) => set(`g_${k}`, x)} /></div>
            <L small label="Details (who was affected, backup used)"><input className="pub-input py-2" value={v[`g_${k}_details`]} onChange={(e) => set(`g_${k}_details`, e.target.value)} /></L>
          </div>
        ))}
        <div className="grid gap-2 rounded-xl border border-slate-200 p-3 sm:grid-cols-[1fr_1fr]">
          <L small label="Device shortages (number of devices short; 0 if none)"><input className="pub-input py-2" type="number" min={0} inputMode="numeric" value={v.g_devices} onChange={(e) => set("g_devices", e.target.value)} /></L>
          <L small label="Details (who was affected, backup used)"><input className="pub-input py-2" value={v.g_devices_details} onChange={(e) => set("g_devices_details", e.target.value)} /></L>
        </div>
      </Section>

      <Section icon={<Users size={18} />} code="H" title="Escalations and decisions needed">
        {v.escalations.map((x, i) => (
          <div key={i} className="grid gap-2 rounded-xl border border-slate-200 bg-slate-50 p-3 sm:grid-cols-[auto_2fr_1fr_1fr_1fr_1fr_auto] sm:items-end">
            <div className="text-sm font-semibold text-slate-500">#{i + 1}</div>
            <L small label="Issue requiring management / CCIT action"><input className="pub-input bg-white py-2" value={x.issue} onChange={(e) => set("escalations", v.escalations.map((y, j) => (j === i ? { ...y, issue: e.target.value } : y)))} /></L>
            <L small label="Raised to"><input className="pub-input bg-white py-2" value={x.raised_to} onChange={(e) => set("escalations", v.escalations.map((y, j) => (j === i ? { ...y, raised_to: e.target.value } : y)))} /></L>
            <L small label="Proposed owner"><input className="pub-input bg-white py-2" value={x.owner} onChange={(e) => set("escalations", v.escalations.map((y, j) => (j === i ? { ...y, owner: e.target.value } : y)))} /></L>
            <L small label="Needed by"><input className="pub-input bg-white py-2" value={x.needed_by} onChange={(e) => set("escalations", v.escalations.map((y, j) => (j === i ? { ...y, needed_by: e.target.value } : y)))} placeholder="e.g. tomorrow 08:00" /></L>
            <L small label="Status"><select className="pub-input bg-white py-2" value={x.status} onChange={(e) => set("escalations", v.escalations.map((y, j) => (j === i ? { ...y, status: e.target.value } : y)))}>{spec.escalation_status.map((o) => <option key={String(o.value)} value={String(o.value)}>{o.label}</option>)}</select></L>
            <button type="button" className="pb-2 text-sm text-red-700" onClick={() => set("escalations", v.escalations.filter((_, j) => j !== i))}>Remove</button>
          </div>
        ))}
        <button type="button" className="pub-btn-ghost border border-slate-300" onClick={() => set("escalations", [...v.escalations, emptyEscalation()])}>+ Add escalation</button>
        {v.escalations.length === 0 && <p className="text-xs text-slate-400">Nothing needs management / CCIT action today.</p>}
      </Section>

      {touched && errors.length > 0 && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          <div className="font-semibold">Please complete before sending ({errors.length})</div>
          <ul className="mt-1 list-disc pl-5">{errors.map((x) => <li key={x}>{x}</li>)}</ul>
        </div>
      )}
      <button className="pub-btn w-full" disabled={busy}>{busy ? "Sending…" : submitLabel}</button>
    </form>
  );
}

function Scale({ value, onPick }: { value: string; onPick: (v: string) => void }) {
  const colors: Record<number, string> = { 1: "border-red-600 bg-red-600", 2: "border-orange-500 bg-orange-500", 3: "border-amber-400 bg-amber-400", 4: "border-lime-600 bg-lime-600", 5: "border-emerald-600 bg-emerald-600" };
  const titles: Record<number, string> = { 1: "Serious problems, session not effective", 2: "Below expectations, major gaps", 3: "Acceptable, some gaps", 4: "Good, minor gaps", 5: "Excellent, no gaps and evidence cited" };
  return (
    <div className="flex gap-1">
      {[1, 2, 3, 4, 5].map((n) => (
        <button type="button" key={n} onClick={() => onPick(String(n))} title={titles[n]} className={clsx("h-10 w-11 rounded-xl border-2 text-sm font-bold transition", Number(value) === n ? `${colors[n]} text-white` : "border-slate-300 bg-white text-slate-700 hover:border-navy")}>{n}</button>
      ))}
    </div>
  );
}

function Section({ icon, code, title, children }: { icon: React.ReactNode; code: string; title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="flex items-center gap-2 border-b border-slate-200 pb-2 text-base font-bold text-navy">{icon} {code}. {title}</h2>
      {children}
    </section>
  );
}

function L({ label, small, children }: { label: string; small?: boolean; children: React.ReactNode }) {
  return <label className="block"><span className={clsx("mb-1 block font-medium", small ? "text-xs text-slate-600" : "text-sm text-slate-700")}>{label}</span>{children}</label>;
}

function Choice({ label, options, value, onPick }: { label: string; options: Opt[]; value: string; onPick: (v: string | number) => void }) {
  return (
    <div>
      <span className="mb-1 block text-sm font-medium text-slate-700">{label}</span>
      <div className="flex flex-wrap gap-2">
        {options.map((o) => (
          <button type="button" key={String(o.value)} onClick={() => onPick(o.value)} className={clsx("rounded-xl border px-4 py-2 text-sm font-semibold transition", value === String(o.value) ? "border-navy bg-navy text-white shadow" : "border-slate-300 bg-white text-slate-700 hover:border-navy/50 hover:bg-sky-50")}>{o.label}</button>
        ))}
      </div>
    </div>
  );
}

function TopicPicker({ label, groups, values, onToggle }: { label: string; groups: { label: string; topics: string[] }[]; values: string[]; onToggle: (v: string) => void }) {
  const [other, setOther] = useState("");
  const available = groups.map((g) => ({ ...g, topics: g.topics.filter((t) => !values.includes(t)) })).filter((g) => g.topics.length);
  return (
    <div>
      <span className="mb-1 block text-sm font-medium text-slate-700">{label}</span>
      {values.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-2">
          {values.map((t) => <span key={t} className="inline-flex items-center gap-1 rounded-xl bg-navy px-3 py-1.5 text-sm font-medium text-white">{t}<button type="button" className="ml-1 text-sky-200 hover:text-white" onClick={() => onToggle(t)} aria-label={`Remove ${t}`}>×</button></span>)}
        </div>
      )}
      <select className="pub-input" value="" onChange={(e) => { if (e.target.value === "__other") { setOther(" "); return; } if (e.target.value) onToggle(e.target.value); }}>
        <option value="">{values.length ? "Add another topic from the agenda…" : "None · choose a topic from the agenda to add it"}</option>
        {available.map((g) => <optgroup key={g.label} label={g.label}>{g.topics.map((t) => <option key={t} value={t}>{t}</option>)}</optgroup>)}
        <option value="__other">Other (not on the agenda)</option>
      </select>
      {other !== "" && (
        <div className="mt-2 flex gap-2">
          <input className="pub-input" value={other.trim()} onChange={(e) => setOther(e.target.value || " ")} placeholder="Type the topic" />
          <button type="button" className="pub-btn px-4" onClick={() => { if (other.trim()) onToggle(other.trim()); setOther(""); }}>Add</button>
        </div>
      )}
    </div>
  );
}
