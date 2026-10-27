import clsx from "clsx";
import type { ReactNode } from "react";

/* Shared visual pieces of the M&E KPI dashboard and reports: scorecards, status colours, heat cells. */

export const NAVY = "#1F4E79", GREEN = "#15803d", LIME = "#65a30d", AMBER = "#d97706", RED = "#b91c1c", SKY = "#0ea5e9", SLATE = "#94a3b8";
export const PHASES: [string, string][] = [["MT", "Master trainers' practice"], ["TOT", "ToT practice"], ["TOE", "ToE practice"], ["L", "Listing"], ["E", "Enumeration"]];
export const phaseLabel = (code: string) => PHASES.find(([v]) => v === code)?.[1] ?? code;
export const phaseShort = (code: string) => ({ MT: "MT", TOT: "ToT", TOE: "ToE", L: "Listing", E: "Enumeration" } as Record<string, string>)[code] ?? code;
export const pct = (v: number | null | undefined, digits = 0) => (v === null || v === undefined ? "—" : `${digits ? v.toFixed(digits) : Math.round(v)}%`);
export const ratingLabel = (v: number | null | undefined) => (v === null || v === undefined ? "—" : v >= 3.5 ? "Very good" : v >= 2.5 ? "Good" : v >= 1.5 ? "Weak" : "Poor");

export type Status = "good" | "warn" | "bad" | "none";
/** Status of a percentage against a target: `invert` for metrics where lower is better (error rate). */
export function status(v: number | null | undefined, good: number, warn: number, invert = false): Status {
  if (v === null || v === undefined) return "none";
  if (!invert) return v >= good ? "good" : v >= warn ? "warn" : "bad";
  return v <= good ? "good" : v <= warn ? "warn" : "bad";
}
export const statusColor: Record<Status, string> = { good: GREEN, warn: AMBER, bad: RED, none: SLATE };
export const statusBg: Record<Status, string> = { good: "bg-emerald-50 text-emerald-800", warn: "bg-amber-50 text-amber-800", bad: "bg-red-50 text-red-800", none: "bg-slate-50 text-slate-400" };
export const statusText: Record<Status, string> = { good: "On target", warn: "Watch", bad: "Off target", none: "No data" };

/** KPI definitions: thresholds shared by the scorecards, the heat table and the district report. */
export const KPIS = {
  coverage: { label: "EA coverage", good: 80, warn: 50, invert: false, help: "Households listed / enumerated ÷ expected" },
  synced: { label: "Synced to HQ", good: 95, warn: 80, invert: false, help: "Cases synced ÷ completed" },
  error: { label: "Error rate", good: 5, warn: 10, invert: true, help: "Households with errors ÷ reviewed" },
  tablets: { label: "Tablets working", good: 95, warn: 90, invert: false, help: "Working ÷ issued" },
  schedule: { label: "On schedule", good: 90, warn: 70, invert: false, help: "Teams on the calendar" },
  informed: { label: "Community informed", good: 85, warn: 60, invert: false, help: "Community prepared before the visit" },
  support: { label: "Leaders support", good: 85, warn: 60, invert: false, help: "Leaders support participation" },
} as const;

export function Scorecard({ label, value, raw, good, warn, invert, help, count, targetText }: { label: string; value: string; raw: number | null | undefined; good: number; warn: number; invert?: boolean; help?: string; count?: ReactNode; targetText?: string }) {
  const st = status(raw, good, warn, invert);
  const width = raw === null || raw === undefined ? 0 : Math.max(2, Math.min(100, invert ? 100 - raw : raw));
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1 truncate text-xs font-semibold uppercase tracking-wide text-slate-500" title={label}>{label}</div>
        <span className={clsx("shrink-0 whitespace-nowrap rounded-full px-2 py-0.5 text-[10px] font-bold", statusBg[st])}>{statusText[st]}</span>
      </div>
      <div className="mt-1 text-3xl font-extrabold tabular-nums" style={{ color: statusColor[st] === SLATE ? NAVY : statusColor[st] }}>{value}</div>
      <div className="mt-2 h-1.5 rounded-full bg-slate-100"><div className="h-1.5 rounded-full" style={{ width: `${width}%`, background: statusColor[st] }} /></div>
      <div className="mt-1 text-[11px] leading-tight text-slate-400"><div className="truncate" title={help}>{help}</div><div className="font-semibold text-slate-500">{targetText ?? `target ${invert ? "≤" : "≥"} ${good}%`}</div></div>
      {count !== undefined && <div className="mt-1 text-xs text-slate-500">{count}</div>}
    </div>
  );
}

export function CountCard({ label, value, sub, tone = "navy", icon }: { label: string; value: ReactNode; sub?: ReactNode; tone?: "navy" | "red" | "amber" | "green"; icon?: ReactNode }) {
  const tones = { navy: "from-navy to-[#2f6fa8]", red: "from-red-700 to-red-500", amber: "from-[#b45309] to-[#f59e0b]", green: "from-emerald-700 to-emerald-500" };
  return (
    <div className={clsx("rounded-xl bg-gradient-to-br p-4 text-white shadow-sm", tones[tone])}>
      <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wide opacity-80"><span>{label}</span>{icon}</div>
      <div className="mt-1 text-3xl font-extrabold tabular-nums">{value}</div>
      {sub && <div className="mt-1 text-xs opacity-80">{sub}</div>}
    </div>
  );
}

/** A table cell coloured by status. */
export function HeatCell({ v, good, warn, invert, suffix = "%" }: { v: number | null | undefined; good: number; warn: number; invert?: boolean; suffix?: string }) {
  const st = status(v, good, warn, invert);
  return <td className={clsx("text-right font-semibold tabular-nums", statusBg[st])}>{v === null || v === undefined ? "—" : `${Math.round(v)}${suffix}`}</td>;
}

export function Bars({ rows, color, max }: { rows: { label: string; count: number; pct: number | null }[]; color: string; max?: number }) {
  const data = rows.filter((r) => r.count).sort((a, b) => b.count - a.count);
  const top = max ?? Math.max(1, ...data.map((d) => d.count));
  if (!data.length) return <p className="py-6 text-center text-sm text-slate-400">Nothing reported</p>;
  return (
    <ul className="space-y-2">
      {data.map((r) => (
        <li key={r.label}>
          <div className="mb-0.5 flex justify-between text-xs"><span className="text-slate-700">{r.label}</span><span className="font-semibold tabular-nums text-slate-600">{r.count}{r.pct !== null ? <span className="font-normal text-slate-400"> · {Math.round(r.pct)}%</span> : null}</span></div>
          <div className="h-2 rounded-full bg-slate-100"><div className="h-2 rounded-full" style={{ width: `${(100 * r.count) / top}%`, background: color }} /></div>
        </li>
      ))}
    </ul>
  );
}

export function Progress({ label, v, good = 80, warn = 60 }: { label: string; v: number | null; good?: number; warn?: number }) {
  const st = status(v, good, warn);
  return (
    <li>
      <div className="flex justify-between text-sm"><span>{label}</span><span className="font-semibold tabular-nums">{pct(v)}</span></div>
      <div className="h-2.5 rounded-full bg-slate-100"><div className="h-2.5 rounded-full" style={{ width: `${v ?? 0}%`, background: statusColor[st] }} /></div>
    </li>
  );
}

export function Panel({ title, subtitle, children, action, className }: { title: string; subtitle?: string; children: ReactNode; action?: ReactNode; className?: string }) {
  return (
    <section className={clsx("rounded-xl border border-slate-200 bg-white p-4 shadow-sm", className)}>
      <header className="mb-3 flex items-start justify-between gap-2">
        <div><h2 className="text-sm font-bold text-slate-800">{title}</h2>{subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}</div>
        {action}
      </header>
      {children}
    </section>
  );
}
