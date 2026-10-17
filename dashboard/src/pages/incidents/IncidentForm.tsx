import clsx from "clsx";
import type { IncidentSpec } from "../../api/types";
import { SEV } from "./incidentUi";

/** The incident report fields shared by the public page (supervisors) and the signed-in form. */
export type IncidentValues = {
  phase: string; occurred_date: string; occurred_time: string; category: string; subcategory: string; severity: string; title: string; description: string; action_taken: string; help_needed: string;
  ea_code: string; locality: string; teams_affected: string; staff_affected: string; households_affected: string; days_lost: string; asset_tags: string; reference: string;
};

export const nowDate = () => new Date().toISOString().slice(0, 10);
export const nowTime = () => new Date().toTimeString().slice(0, 5);

export function emptyIncident(): IncidentValues {
  return { phase: "ENUMERATION", occurred_date: nowDate(), occurred_time: nowTime(), category: "", subcategory: "", severity: "", title: "", description: "", action_taken: "", help_needed: "", ea_code: "", locality: "", teams_affected: "", staff_affected: "", households_affected: "", days_lost: "", asset_tags: "", reference: "" };
}

export function incidentPayload(v: IncidentValues) {
  const n = (s: string) => (s.trim() === "" ? null : Number(s));
  const t = (s: string) => (s.trim() === "" ? null : s.trim());
  return {
    phase: v.phase, occurred_at: new Date(`${v.occurred_date}T${v.occurred_time || "00:00"}:00`).toISOString(), category: v.category, subcategory: v.subcategory || null, severity: v.severity,
    title: v.title.trim(), description: v.description.trim(), action_taken: t(v.action_taken), help_needed: t(v.help_needed), ea_code: t(v.ea_code), locality: t(v.locality),
    teams_affected: n(v.teams_affected), staff_affected: n(v.staff_affected), households_affected: n(v.households_affected), days_lost: n(v.days_lost), asset_tags: t(v.asset_tags), reference: t(v.reference),
  };
}

export function validateIncident(v: IncidentValues): string[] {
  const e: string[] = [];
  if (!v.category) e.push("Choose the category");
  if (!v.severity) e.push("Choose the severity");
  if (!v.phase) e.push("Choose the census phase");
  if (!v.occurred_date) e.push("Enter when it happened");
  if (v.title.trim().length < 3) e.push("Give the incident a short title");
  if (v.description.trim().length < 10) e.push("Describe what happened (at least 10 characters)");
  return e;
}

/** Field labels. Defined at module level: a component created inside the render would be a new type on every
 *  keystroke, so React would remount the input and the user would lose focus after each character. */
function PublicLabel({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return <label className="block"><span className="mb-1 block text-sm font-medium text-slate-700">{label}</span>{children}{hint && <span className="mt-1 block text-xs text-slate-400">{hint}</span>}</label>;
}
function CompactLabel({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return <label className="block"><span className="mb-1 block text-xs font-medium text-slate-700">{label}</span>{children}{hint && <span className="mt-1 block text-xs text-slate-400">{hint}</span>}</label>;
}

export function IncidentFields({ spec, values, onChange, publicStyle, hideEa }: { spec: IncidentSpec; values: IncidentValues; onChange: (v: IncidentValues) => void; publicStyle?: boolean; hideEa?: boolean }) {
  const v = values;
  const set = <K extends keyof IncidentValues>(k: K, val: IncidentValues[K]) => onChange({ ...v, [k]: val });
  const input = publicStyle ? "pub-input" : "input";
  const cat = spec.categories.find((c) => c.value === v.category);
  const L = publicStyle ? PublicLabel : CompactLabel;
  return (
    <div className="space-y-4">
      <div>
        <span className={clsx("mb-1 block font-medium text-slate-700", publicStyle ? "text-sm" : "text-xs")}>What kind of incident? *</span>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
          {spec.categories.map((c) => (
            <button type="button" key={c.value} onClick={() => onChange({ ...v, category: c.value, subcategory: "", severity: v.severity || c.default_severity })}
              className={clsx("rounded-xl border px-3 py-2 text-left text-sm font-medium transition", v.category === c.value ? "border-navy bg-navy text-white shadow" : "border-slate-300 bg-white text-slate-700 hover:border-navy/50 hover:bg-sky-50")}>{c.label}</button>
          ))}
        </div>
      </div>
      {cat && (
        <L label="More precisely">
          <select className={input} value={v.subcategory} onChange={(e) => set("subcategory", e.target.value)}>
            <option value="">Choose…</option>
            {cat.subcategories.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
        </L>
      )}
      <div>
        <span className={clsx("mb-1 block font-medium text-slate-700", publicStyle ? "text-sm" : "text-xs")}>How serious? *</span>
        <div className="grid gap-2 sm:grid-cols-3">
          {spec.severities.map((s) => (
            <button type="button" key={s.value} onClick={() => set("severity", s.value)}
              className={clsx("rounded-xl border-2 px-3 py-2 text-left transition", v.severity === s.value ? "text-white" : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50")}
              style={v.severity === s.value ? { background: SEV[s.value as keyof typeof SEV].color, borderColor: SEV[s.value as keyof typeof SEV].color } : undefined}>
              <div className="text-sm font-bold">{s.label}</div><div className={clsx("text-xs", v.severity === s.value ? "text-white/85" : "text-slate-500")}>{s.help}</div>
            </button>
          ))}
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <L label="Census phase *"><select className={input} value={v.phase} onChange={(e) => set("phase", e.target.value)}>{spec.phases.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}</select></L>
        <L label="Date it happened *"><input className={input} type="date" max={nowDate()} value={v.occurred_date} onChange={(e) => set("occurred_date", e.target.value)} /></L>
        <L label="Time"><input className={input} type="time" value={v.occurred_time} onChange={(e) => set("occurred_time", e.target.value)} /></L>
      </div>
      <L label="Short title *"><input className={input} value={v.title} onChange={(e) => set("title", e.target.value)} placeholder="e.g. Tablet stolen at Tower Hill" maxLength={200} /></L>
      <L label="What happened? *" hint="Who, what, where, when; names of staff involved; what was lost or damaged."><textarea className={input} rows={4} value={v.description} onChange={(e) => set("description", e.target.value)} /></L>
      <div className="grid gap-3 sm:grid-cols-2">
        <L label="Action already taken"><textarea className={input} rows={2} value={v.action_taken} onChange={(e) => set("action_taken", e.target.value)} placeholder="e.g. Reported to police; team moved to the next structure" /></L>
        <L label="Help needed"><textarea className={input} rows={2} value={v.help_needed} onChange={(e) => set("help_needed", e.target.value)} placeholder="e.g. Replacement tablet; transport; a decision from HQ" /></L>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {!hideEa && <L label="EA code (if one EA)"><input className={input} value={v.ea_code} onChange={(e) => set("ea_code", e.target.value)} placeholder="10-digit EA code" /></L>}
        <L label="Locality / place"><input className={input} value={v.locality} onChange={(e) => set("locality", e.target.value)} placeholder="Village, street or landmark" /></L>
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <L label="Teams affected"><input className={input} type="number" min={0} inputMode="numeric" value={v.teams_affected} onChange={(e) => set("teams_affected", e.target.value)} /></L>
        <L label="Staff affected"><input className={input} type="number" min={0} inputMode="numeric" value={v.staff_affected} onChange={(e) => set("staff_affected", e.target.value)} /></L>
        <L label="Households affected"><input className={input} type="number" min={0} inputMode="numeric" value={v.households_affected} onChange={(e) => set("households_affected", e.target.value)} /></L>
        <L label="Days lost"><input className={input} type="number" min={0} inputMode="numeric" value={v.days_lost} onChange={(e) => set("days_lost", e.target.value)} /></L>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <L label="Tablets involved (asset tags)"><input className={input} value={v.asset_tags} onChange={(e) => set("asset_tags", e.target.value)} placeholder="e.g. SL-TAB-0412, SL-TAB-0413" /></L>
        <L label="Reference (error id, visit, report)"><input className={input} value={v.reference} onChange={(e) => set("reference", e.target.value)} /></L>
      </div>
    </div>
  );
}
