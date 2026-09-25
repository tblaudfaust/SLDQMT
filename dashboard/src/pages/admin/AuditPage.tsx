import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, fmt, qs } from "../../api/client";
import type { AuditRow } from "../../api/types";
import { Card, Empty, ErrorBox, Field, Spinner } from "../../components/ui";

const ENTITIES = ["", "error", "dqm_report", "exit_checkout", "user", "role", "device", "setting", "error_category", "error_source", "file", "report", "dqm_summary", "exit_summary"];

function Detail({ text }: { text: string | null }) {
  if (!text) return null;
  try {
    const obj = JSON.parse(text);
    if (obj && typeof obj === "object" && obj.changes && typeof obj.changes === "object") {
      const entries = Object.entries(obj.changes as Record<string, [unknown, unknown]>);
      return (
        <div className="text-xs">
          {entries.length === 0 && <span className="text-slate-400">no field changes</span>}
          {entries.map(([k, [a, b]]) => <div key={k}><span className="font-medium">{k}</span>: <span className="text-red-700 line-through">{String(a ?? "")}</span> → <span className="text-green-700">{String(b ?? "")}</span></div>)}
          {Object.entries(obj).filter(([k]) => k !== "changes").map(([k, v]) => <div key={k}><span className="font-medium">{k}</span>: {typeof v === "object" ? JSON.stringify(v) : String(v)}</div>)}
        </div>
      );
    }
    if (obj && typeof obj === "object") return <div className="text-xs">{Object.entries(obj).map(([k, v]) => <div key={k}><span className="font-medium">{k}</span>: {typeof v === "object" ? JSON.stringify(v) : String(v)}</div>)}</div>;
  } catch { /* plain text */ }
  return <span className="text-xs">{text}</span>;
}

export default function AuditPage() {
  const [params, setParams] = useSearchParams();
  const set = (k: string, v: string) => { const n = new URLSearchParams(params); if (v) n.set(k, v); else n.delete(k); setParams(n, { replace: true }); };
  const filters = { action: params.get("action") || undefined, entity: params.get("entity") || undefined, entity_id: params.get("entity_id") || undefined, date_from: params.get("date_from") || undefined, date_to: params.get("date_to") || undefined, limit: 500 };
  const q = qs(filters);
  const rows = useQuery({ queryKey: ["admin", "audit", q], queryFn: () => api.get<AuditRow[]>(`/admin/audit${q}`) });
  const actions = useQuery({ queryKey: ["admin", "audit-actions"], queryFn: () => api.get<string[]>("/admin/audit/actions") });
  const [who, setWho] = useState("");
  const shown = (rows.data ?? []).filter((r) => !who || (r.user_name ?? "").toLowerCase().includes(who.toLowerCase()) || (r.username ?? "").toLowerCase().includes(who.toLowerCase()));

  return (
    <div>
      <h1 className="text-2xl font-bold">Audit log</h1>
      <p className="mb-4 text-sm text-slate-500">Every sign-in, change, deletion, restore, export and rights change, with who did it, when, from which address, and what changed.</p>
      <div className="card mb-4 grid grid-cols-2 gap-3 md:grid-cols-6">
        <Field label="Who"><input className="input" placeholder="name or username" value={who} onChange={(e) => setWho(e.target.value)} /></Field>
        <Field label="Action">
          <select className="input" value={filters.action ?? ""} onChange={(e) => set("action", e.target.value)}>
            <option value="">All</option>
            {(actions.data ?? []).map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
        </Field>
        <Field label="Record type">
          <select className="input" value={filters.entity ?? ""} onChange={(e) => set("entity", e.target.value)}>
            {ENTITIES.map((e) => <option key={e} value={e}>{e || "All"}</option>)}
          </select>
        </Field>
        <Field label="Record ID"><input className="input" value={filters.entity_id ?? ""} onChange={(e) => set("entity_id", e.target.value)} /></Field>
        <Field label="From"><input type="date" className="input" value={filters.date_from ?? ""} onChange={(e) => set("date_from", e.target.value)} /></Field>
        <Field label="To"><input type="date" className="input" value={filters.date_to ?? ""} onChange={(e) => set("date_to", e.target.value)} /></Field>
      </div>
      <Card title={`${shown.length} entries${(rows.data?.length ?? 0) >= 500 ? " (latest 500; narrow the filters for more)" : ""}`}>
        <ErrorBox error={rows.error} />
        {rows.isLoading ? <Spinner /> : shown.length ? (
          <table className="table">
            <thead><tr><th>When</th><th>Who</th><th>Action</th><th>Record</th><th>Details</th><th>Address</th></tr></thead>
            <tbody>{shown.map((r) => <tr key={r.id}><td className="whitespace-nowrap">{fmt(r.at)}</td><td>{r.user_name ?? "system"}<div className="text-xs text-slate-400">{r.username}</div></td><td className="whitespace-nowrap">{r.action}</td><td className="whitespace-nowrap">{r.entity} {r.entity_id}</td><td className="max-w-lg"><Detail text={r.detail} /></td><td className="text-xs text-slate-400">{r.ip}</td></tr>)}</tbody>
          </table>
        ) : <Empty text="No entries match" />}
      </Card>
    </div>
  );
}
