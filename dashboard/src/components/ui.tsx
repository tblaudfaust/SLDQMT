import clsx from "clsx";
import type { ReactNode } from "react";

export function KpiTile({ label, value, tone = "navy", sub, onClick }: { label: string; value: string | number; tone?: "navy" | "green" | "amber" | "red"; sub?: string; onClick?: () => void }) {
  const tones = {
    navy: "border-navy/30 text-navy",
    green: "border-green-600/30 text-green-700",
    amber: "border-amber/60 text-amber-700",
    red: "border-red-600/30 text-red-700",
  };
  return (
    <button onClick={onClick} className={clsx("card text-left border-l-4 hover:shadow transition", tones[tone], onClick ? "cursor-pointer" : "cursor-default")}>
      <div className="text-3xl font-bold">{value}</div>
      <div className="text-sm text-slate-600">{label}</div>
      {sub && <div className="text-xs text-slate-400 mt-1">{sub}</div>}
    </button>
  );
}

export function Badge({ status, overdue }: { status: string; overdue?: boolean }) {
  const cls = status === "RESOLVED" ? "bg-green-100 text-green-800" : overdue ? "bg-red-100 text-red-800" : "bg-amber/30 text-amber-900";
  const label = status === "RESOLVED" ? "Resolved" : overdue ? "Overdue" : "Unresolved";
  return <span className={clsx("inline-block rounded-full px-2 py-0.5 text-xs font-semibold", cls)}>{label}</span>;
}

export function Card({ title, children, action, className }: { title?: string; children: ReactNode; action?: ReactNode; className?: string }) {
  return (
    <section className={clsx("card", className)}>
      {(title || action) && (
        <header className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-700">{title}</h2>
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

export function Empty({ text = "No records" }: { text?: string }) {
  return <p className="py-6 text-center text-sm text-slate-400">{text}</p>;
}

export function Spinner() {
  return <div className="py-10 text-center text-sm text-slate-400">Loading…</div>;
}

export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null;
  const message = error instanceof Error ? error.message : String(error);
  return <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{message}</div>;
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block text-xs font-medium text-slate-600">{label}</span>
      {children}
    </label>
  );
}
