import { useState } from "react";
import clsx from "clsx";
import { AlertTriangle, CheckCircle2, ClipboardList, GraduationCap, LifeBuoy, Users } from "lucide-react";

/* ------------------------------------------------------------------------------------------------
 * The Daily Trainer Class Evaluation form, rendered from the server's spec (app/core/me_daily_form.py).
 * Used by the public page (lead trainers) and by the dashboard's edit dialog (M&E staff).
 * ---------------------------------------------------------------------------------------------- */

export type Opt = { value: string; label: string };
export type DailySpec = {
  title: string; intro: string; phases: Opt[]; coverage: Opt[]; checks: Opt[]; ratings: Opt[]; rating_help: string;
  delivery_areas: Opt[]; support: Opt[]; districts: string[]; max_actions: number; urgent_note: string;
};
export type ActionValue = { issue: string; action: string; owner_due: string };
export type DailyValues = {
  report_date: string; training_day: string; class_hall: string; venue: string; lead_trainer: string; phase: string; district: string;
  expected: string; present: string; late: string; coverage: string; incomplete_topic: string; practice_minutes: string; practice_not_scheduled: boolean;
  checks: string[]; task_checked: string; number_checked: string; number_met: string; criterion: string; learning_gap: string; followup_count: string; followup_not_assessed: boolean;
  delivery_content: string; delivery_participation: string; delivery_time: string; support: string[]; support_other: string;
  actions: ActionValue[]; mgmt_help: boolean; raised_to: string;
};

export const today = () => new Date().toISOString().slice(0, 10);

export function emptyValues(phase = "FIELD"): DailyValues {
  return {
    report_date: today(), training_day: "", class_hall: "", venue: "", lead_trainer: "", phase, district: "",
    expected: "", present: "", late: "0", coverage: "", incomplete_topic: "", practice_minutes: "", practice_not_scheduled: false,
    checks: [], task_checked: "", number_checked: "", number_met: "", criterion: "", learning_gap: "", followup_count: "", followup_not_assessed: false,
    delivery_content: "", delivery_participation: "", delivery_time: "", support: [], support_other: "",
    actions: [{ issue: "", action: "", owner_due: "" }, { issue: "", action: "", owner_due: "" }], mgmt_help: false, raised_to: "",
  };
}

/** What the server expects (numbers as numbers, blanks as null). */
export function toPayload(v: DailyValues) {
  const n = (s: string) => (s.trim() === "" ? null : Number(s));
  const assessed = v.checks.length > 0 && !v.checks.includes("NOT_ASSESSED");
  return {
    report_date: v.report_date, training_day: Number(v.training_day), class_hall: v.class_hall.trim(), venue: v.venue.trim() || null, lead_trainer: v.lead_trainer.trim(), phase: v.phase, district: v.district || null,
    expected: Number(v.expected), present: Number(v.present), late: Number(v.late || 0), coverage: v.coverage, incomplete_topic: v.coverage === "ALL" ? null : v.incomplete_topic.trim() || null,
    practice_minutes: v.practice_not_scheduled ? null : n(v.practice_minutes), practice_not_scheduled: v.practice_not_scheduled,
    checks: v.checks, task_checked: assessed ? v.task_checked.trim() || null : null, number_checked: assessed ? n(v.number_checked) : null, number_met: assessed ? n(v.number_met) : null,
    criterion: assessed ? v.criterion.trim() || null : null, learning_gap: v.learning_gap.trim() || null, followup_count: v.followup_not_assessed ? null : n(v.followup_count), followup_not_assessed: v.followup_not_assessed,
    delivery_content: v.delivery_content, delivery_participation: v.delivery_participation, delivery_time: v.delivery_time, support: v.support, support_other: v.support.includes("OTHER") ? v.support_other.trim() || null : null,
    actions: v.actions.filter((a) => (a.issue + a.action + a.owner_due).trim()).map((a) => ({ issue: a.issue.trim(), action: a.action.trim(), owner_due: a.owner_due.trim() })),
    mgmt_help: v.mgmt_help, raised_to: v.mgmt_help ? v.raised_to.trim() || null : null,
  };
}

/** The same checks as the server, so the trainer sees them before sending. */
export function validate(v: DailyValues, spec: DailySpec): string[] {
  const e: string[] = [];
  const num = (s: string) => (s.trim() === "" ? null : Number(s));
  if (!v.report_date) e.push("Enter the date");
  if (v.report_date > today()) e.push("The report date cannot be in the future");
  if (!v.training_day || Number(v.training_day) < 1) e.push("Enter the training day (1, 2, 3…)");
  if (!v.class_hall.trim()) e.push("Enter the class / hall");
  if (v.lead_trainer.trim().length < 2) e.push("Enter the lead trainer's name");
  if (!v.phase) e.push("Tick the phase");
  const expected = num(v.expected), present = num(v.present), late = num(v.late);
  if (expected === null || present === null) e.push("Enter the expected and present trainees");
  else {
    if (present > expected) e.push("Present cannot exceed the expected trainees");
    if (late !== null && late > present) e.push("Arrived late cannot exceed the trainees present");
  }
  if (!v.coverage) e.push("Tick the agenda coverage");
  else if (v.coverage !== "ALL" && !v.incomplete_topic.trim()) e.push("Give the topic and reason when the agenda was not fully covered");
  if (!v.practice_not_scheduled && num(v.practice_minutes) === null) e.push("Enter the practical / CAPI practice minutes, or tick Not scheduled");
  if (v.checks.length === 0) e.push("Tick the check used, or Not assessed");
  const assessed = v.checks.length > 0 && !v.checks.includes("NOT_ASSESSED");
  if (assessed) {
    const c = num(v.number_checked), m = num(v.number_met);
    if (c === null || m === null) e.push("Enter the number checked and the number meeting the criterion");
    else if (m > c) e.push("The number meeting the criterion cannot exceed the number checked");
    if (!v.task_checked.trim()) e.push("Say which task or topic was checked");
    if (!v.criterion.trim()) e.push("Give the pass / success criterion used");
  }
  if (!v.followup_not_assessed && num(v.followup_count) === null) e.push("Enter the trainees needing follow-up, or tick Not assessed");
  for (const a of spec.delivery_areas) if (!v[`delivery_${a.value}` as "delivery_content"]) e.push(`Rate ${a.label.toLowerCase()}`);
  if (v.support.length === 0) e.push("Tick the support problems, or None");
  if (v.support.includes("OTHER") && !v.support_other.trim()) e.push("Describe the other support problem");
  v.actions.forEach((a, i) => {
    if ((a.issue + a.action + a.owner_due).trim()) {
      if (!a.issue.trim()) e.push(`Action ${i + 1}: describe the issue and its impact`);
      if (!a.action.trim()) e.push(`Action ${i + 1}: give the next action`);
    }
  });
  if (v.mgmt_help && !v.raised_to.trim()) e.push("Say who the management / CCIT request was raised to");
  return e;
}

export function DailyReportForm({ spec, values, onChange, onSubmit, busy, submitLabel, errors, compact }: {
  spec: DailySpec; values: DailyValues; onChange: (v: DailyValues) => void; onSubmit: () => void; busy: boolean; submitLabel: string; errors: string[]; compact?: boolean;
}) {
  const v = values;
  const set = <K extends keyof DailyValues>(k: K, val: DailyValues[K]) => onChange({ ...v, [k]: val });
  const assessed = v.checks.length > 0 && !v.checks.includes("NOT_ASSESSED");
  const toggleMulti = (k: "checks" | "support", code: string, exclusive: string) => {
    const cur = v[k];
    const next = cur.includes(code) ? cur.filter((x) => x !== code) : code === exclusive ? [code] : [...cur.filter((x) => x !== exclusive), code];
    set(k, next);
  };
  const [touched, setTouched] = useState(false);
  const cls = compact ? "space-y-5" : "space-y-7";
  return (
    <form className={cls} onSubmit={(e) => { e.preventDefault(); setTouched(true); onSubmit(); }}>
      <Section icon={<ClipboardList size={18} />} title="Class and day" n={0}>
        <div className="grid gap-3 sm:grid-cols-3">
          <L label="Date"><input className="pub-input" type="date" max={today()} value={v.report_date} onChange={(e) => set("report_date", e.target.value)} /></L>
          <L label="Training day"><input className="pub-input" type="number" min={1} max={60} inputMode="numeric" value={v.training_day} onChange={(e) => set("training_day", e.target.value)} placeholder="1, 2, 3…" /></L>
          <L label="Class / hall"><input className="pub-input" value={v.class_hall} onChange={(e) => set("class_hall", e.target.value)} placeholder="e.g. Hall 2" /></L>
          <L label="Venue / platform"><input className="pub-input" value={v.venue} onChange={(e) => set("venue", e.target.value)} placeholder="e.g. Bo Teachers College" /></L>
          <L label="Lead trainer"><input className="pub-input" value={v.lead_trainer} onChange={(e) => set("lead_trainer", e.target.value)} placeholder="Your name" autoComplete="name" /></L>
          <L label="District">
            <select className="pub-input" value={v.district} onChange={(e) => set("district", e.target.value)}>
              <option value="">National / HQ</option>
              {spec.districts.map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
          </L>
        </div>
        <Choice label="Phase" options={spec.phases} value={v.phase} onPick={(x) => set("phase", x)} />
      </Section>

      <Section icon={<Users size={18} />} title="Attendance and delivery" n={1}>
        <div className="grid grid-cols-3 gap-3">
          <L label="Expected trainees"><input className="pub-input" type="number" min={0} inputMode="numeric" value={v.expected} onChange={(e) => set("expected", e.target.value)} /></L>
          <L label="Present"><input className="pub-input" type="number" min={0} inputMode="numeric" value={v.present} onChange={(e) => set("present", e.target.value)} /></L>
          <L label="Arrived late"><input className="pub-input" type="number" min={0} inputMode="numeric" value={v.late} onChange={(e) => set("late", e.target.value)} /></L>
        </div>
        <Choice label="Agenda coverage" options={spec.coverage} value={v.coverage} onPick={(x) => set("coverage", x)} />
        {v.coverage && v.coverage !== "ALL" && (
          <L label="Only if incomplete — topic and reason"><textarea className="pub-input" rows={2} value={v.incomplete_topic} onChange={(e) => set("incomplete_topic", e.target.value)} placeholder="Which topic was not completed, and why" /></L>
        )}
        <div className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
          <L label="Practical / CAPI practice time (minutes)"><input className="pub-input" type="number" min={0} inputMode="numeric" value={v.practice_minutes} disabled={v.practice_not_scheduled} onChange={(e) => set("practice_minutes", e.target.value)} /></L>
          <Check label="Not scheduled" checked={v.practice_not_scheduled} onChange={(c) => onChange({ ...v, practice_not_scheduled: c, practice_minutes: c ? "" : v.practice_minutes })} />
        </div>
      </Section>

      <Section icon={<GraduationCap size={18} />} title="Learning evidence" n={2}>
        <MultiChoice label="Check used" options={spec.checks} values={v.checks} onToggle={(x) => toggleMulti("checks", x, "NOT_ASSESSED")} />
        {assessed && (
          <>
            <L label="Task / topic checked"><input className="pub-input" value={v.task_checked} onChange={(e) => set("task_checked", e.target.value)} /></L>
            <div className="grid grid-cols-2 gap-3">
              <L label="Number checked"><input className="pub-input" type="number" min={0} inputMode="numeric" value={v.number_checked} onChange={(e) => set("number_checked", e.target.value)} /></L>
              <L label="Number meeting the stated criterion"><input className="pub-input" type="number" min={0} inputMode="numeric" value={v.number_met} onChange={(e) => set("number_met", e.target.value)} /></L>
            </div>
            <L label="Pass / success criterion used"><input className="pub-input" value={v.criterion} onChange={(e) => set("criterion", e.target.value)} placeholder="e.g. 8 of 10 quiz items correct" /></L>
          </>
        )}
        <L label="Main learning gap or common error"><textarea className="pub-input" rows={2} value={v.learning_gap} onChange={(e) => set("learning_gap", e.target.value)} placeholder="Write None if no issue" /></L>
        <div className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
          <L label="Trainees needing follow-up"><input className="pub-input" type="number" min={0} inputMode="numeric" value={v.followup_count} disabled={v.followup_not_assessed} onChange={(e) => set("followup_count", e.target.value)} /></L>
          <Check label="Not assessed" checked={v.followup_not_assessed} onChange={(c) => onChange({ ...v, followup_not_assessed: c, followup_count: c ? "" : v.followup_count })} />
        </div>
      </Section>

      <Section icon={<LifeBuoy size={18} />} title="Delivery and support" n={3}>
        <p className="text-xs text-slate-500">Tick one per line: {spec.rating_help}</p>
        <div className="overflow-hidden rounded-xl border border-slate-200">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-3 py-2 text-left">Area</th>{spec.ratings.map((r) => <th key={r.value} className="px-2 py-2 text-center">{r.label}</th>)}</tr></thead>
            <tbody>
              {spec.delivery_areas.map((a) => {
                const k = `delivery_${a.value}` as "delivery_content";
                return (
                  <tr key={a.value} className="border-t border-slate-100">
                    <td className="px-3 py-2 font-medium text-slate-700">{a.label}</td>
                    {spec.ratings.map((r) => (
                      <td key={r.value} className="px-2 py-2 text-center">
                        <button type="button" onClick={() => set(k, r.value)} aria-label={`${a.label}: ${r.label}`}
                          className={clsx("h-9 w-9 rounded-full border-2 transition", v[k] === r.value ? (r.value === "GOOD" ? "border-emerald-600 bg-emerald-600" : r.value === "SOME" ? "border-amber-500 bg-amber-500" : "border-red-600 bg-red-600") : "border-slate-300 bg-white hover:border-navy")}>
                          {v[k] === r.value && <CheckCircle2 size={20} className="mx-auto text-white" />}
                        </button>
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <MultiChoice label="Support problems" options={spec.support} values={v.support} onToggle={(x) => toggleMulti("support", x, "NONE")} />
        {v.support.includes("OTHER") && <L label="Other support problem"><input className="pub-input" value={v.support_other} onChange={(e) => set("support_other", e.target.value)} /></L>}
      </Section>

      <Section icon={<AlertTriangle size={18} />} title="Priority actions" n={4}>
        <p className="text-xs text-slate-500">Record only the two most important gaps or issues above. For an error, give the item reference; for a disruption, give trainees affected or minutes lost. Leave blank if no action is needed.</p>
        {v.actions.slice(0, spec.max_actions).map((a, i) => (
          <div key={i} className="grid gap-2 rounded-xl border border-slate-200 bg-slate-50 p-3 sm:grid-cols-3">
            <L label={`Issue and impact ${i + 1}`}><textarea className="pub-input bg-white" rows={2} value={a.issue} onChange={(e) => set("actions", v.actions.map((x, j) => (j === i ? { ...x, issue: e.target.value } : x)))} /></L>
            <L label="Next action"><textarea className="pub-input bg-white" rows={2} value={a.action} onChange={(e) => set("actions", v.actions.map((x, j) => (j === i ? { ...x, action: e.target.value } : x)))} /></L>
            <L label="Owner and due time"><textarea className="pub-input bg-white" rows={2} value={a.owner_due} onChange={(e) => set("actions", v.actions.map((x, j) => (j === i ? { ...x, owner_due: e.target.value } : x)))} placeholder="e.g. Logistics, tonight" /></L>
          </div>
        ))}
        <div className="grid gap-3 sm:grid-cols-[auto_1fr] sm:items-end">
          <div>
            <span className="mb-1 block text-sm font-medium text-slate-700">Management / CCIT help needed</span>
            <div className="flex gap-2">
              {[["no", "No"], ["yes", "Yes"]].map(([val, label]) => (
                <button type="button" key={val} onClick={() => set("mgmt_help", val === "yes")} className={clsx("rounded-xl border px-4 py-2 text-sm font-semibold", (val === "yes") === v.mgmt_help ? "border-navy bg-navy text-white" : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50")}>{label}</button>
              ))}
            </div>
          </div>
          {v.mgmt_help && <L label="Raised to"><input className="pub-input" value={v.raised_to} onChange={(e) => set("raised_to", e.target.value)} placeholder="e.g. District coordinator" /></L>}
        </div>
        <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm font-medium text-amber-900">{spec.urgent_note}</p>
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

function Section({ icon, title, n, children }: { icon: React.ReactNode; title: string; n: number; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="flex items-center gap-2 border-b border-slate-200 pb-2 text-base font-bold text-navy">{icon} {n ? `${n} ` : ""}{title}</h2>
      {children}
    </section>
  );
}

function L({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="block"><span className="mb-1 block text-sm font-medium text-slate-700">{label}</span>{children}</label>;
}

function Check({ label, checked, onChange }: { label: string; checked: boolean; onChange: (c: boolean) => void }) {
  return (
    <label className={clsx("inline-flex cursor-pointer items-center gap-2 rounded-xl border px-4 py-3 text-sm font-medium", checked ? "border-navy bg-sky-50 text-navy" : "border-slate-300 bg-white text-slate-700")}>
      <input type="checkbox" className="h-4 w-4" checked={checked} onChange={(e) => onChange(e.target.checked)} /> {label}
    </label>
  );
}

function Choice({ label, options, value, onPick }: { label: string; options: Opt[]; value: string; onPick: (v: string) => void }) {
  return (
    <div>
      <span className="mb-1 block text-sm font-medium text-slate-700">{label}</span>
      <div className="flex flex-wrap gap-2">
        {options.map((o) => (
          <button type="button" key={o.value} onClick={() => onPick(o.value)} className={clsx("rounded-xl border px-4 py-2 text-sm font-semibold transition", value === o.value ? "border-navy bg-navy text-white shadow" : "border-slate-300 bg-white text-slate-700 hover:border-navy/50 hover:bg-sky-50")}>{o.label}</button>
        ))}
      </div>
    </div>
  );
}

function MultiChoice({ label, options, values, onToggle }: { label: string; options: Opt[]; values: string[]; onToggle: (v: string) => void }) {
  return (
    <div>
      <span className="mb-1 block text-sm font-medium text-slate-700">{label} <span className="text-xs font-normal text-slate-400">(tick all that apply)</span></span>
      <div className="flex flex-wrap gap-2">
        {options.map((o) => (
          <button type="button" key={o.value} onClick={() => onToggle(o.value)} className={clsx("rounded-xl border px-4 py-2 text-sm font-semibold transition", values.includes(o.value) ? "border-navy bg-navy text-white shadow" : "border-slate-300 bg-white text-slate-700 hover:border-navy/50 hover:bg-sky-50")}>{o.label}</button>
        ))}
      </div>
    </div>
  );
}
