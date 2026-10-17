import clsx from "clsx";
import type { Incident } from "../../api/types";

/** Colours and small badges shared by the incident pages. */
export const SEV = {
  CRITICAL: { label: "Critical", color: "#b91c1c", cls: "bg-red-100 text-red-800 ring-red-200", dot: "bg-red-600" },
  MAJOR: { label: "Major", color: "#d97706", cls: "bg-amber-100 text-amber-800 ring-amber-200", dot: "bg-amber-500" },
  MINOR: { label: "Minor", color: "#0ea5e9", cls: "bg-sky-100 text-sky-800 ring-sky-200", dot: "bg-sky-500" },
} as const;
export const STATUS_CLS: Record<string, string> = {
  NEW: "bg-red-600 text-white", ACKNOWLEDGED: "bg-amber-500 text-white", IN_PROGRESS: "bg-navy text-white", RESOLVED: "bg-emerald-600 text-white", CLOSED: "bg-slate-500 text-white", REJECTED: "bg-slate-300 text-slate-700",
};
export const STATUS_COLOR: Record<string, string> = { NEW: "#b91c1c", ACKNOWLEDGED: "#d97706", IN_PROGRESS: "#1F4E79", RESOLVED: "#15803d", CLOSED: "#64748b", REJECTED: "#cbd5e1" };
export const CAT_COLOR: Record<string, string> = { SECURITY: "#b91c1c", STAFF: "#7c3aed", EQUIPMENT: "#1F4E79", MAPS: "#0891b2", COMMUNITY: "#d97706", DATA: "#be185d", LOGISTICS: "#65a30d", ENVIRONMENT: "#0d9488", TRAINING: "#4f46e5", OTHER: "#64748b" };

export function SeverityPill({ severity }: { severity: Incident["severity"] }) {
  const s = SEV[severity] ?? SEV.MINOR;
  return <span className={clsx("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ring-1", s.cls)}><span className={clsx("h-1.5 w-1.5 rounded-full", s.dot)} />{s.label}</span>;
}

export function StatusPill({ status, label }: { status: string; label: string }) {
  return <span className={clsx("inline-block rounded-full px-2 py-0.5 text-xs font-semibold", STATUS_CLS[status] ?? "bg-slate-200")}>{label}</span>;
}

export function ago(iso: string | null): string {
  if (!iso) return "";
  const h = (Date.now() - new Date(iso).getTime()) / 36e5;
  if (h < 1) return `${Math.max(1, Math.round(h * 60))} min ago`;
  if (h < 48) return `${Math.round(h)} h ago`;
  return `${Math.round(h / 24)} d ago`;
}

export function hours(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return v < 48 ? `${v} h` : `${(v / 24).toFixed(1)} d`;
}
