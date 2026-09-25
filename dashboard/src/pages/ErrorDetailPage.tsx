import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, api, download, fmt, fmtDate } from "../api/client";
import type { ErrorDetail, Status } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { useReference } from "../components/FiltersBar";
import { Badge, Card, ErrorBox, Field, Spinner } from "../components/ui";

function Row({ label, value }: { label: string; value?: string | number | null }) {
  if (value === null || value === undefined || value === "") return null;
  return (
    <div className="flex py-1 text-sm">
      <div className="w-44 shrink-0 text-slate-500">{label}</div>
      <div className="whitespace-pre-wrap">{value}</div>
    </div>
  );
}

interface EditForm { description: string; category_id: number; supervisor_name: string; enumerator_name: string; action_taken: string; comments: string; status: Status; support_method: "REMOTE" | "ONSITE"; date_received: string; note: string }

export default function ErrorDetailPage() {
  const { id = "" } = useParams();
  const qc = useQueryClient();
  const { can } = useAuth();
  const { districts, teams, categories } = useReference();
  const q = useQuery({ queryKey: ["error", id], queryFn: () => api.get<ErrorDetail>(`/errors/${id}`) });
  const [editing, setEditing] = useState<EditForm | null>(null);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<unknown>(null);
  const refresh = () => { qc.invalidateQueries({ queryKey: ["error", id] }); qc.invalidateQueries({ queryKey: ["errors"] }); qc.invalidateQueries({ queryKey: ["summary"] }); setError(null); };
  const save = useMutation({ mutationFn: (f: EditForm) => api.patch<ErrorDetail>(`/errors/${id}`, { ...f, comments: f.comments || null, note: f.note || null }), onSuccess: () => { refresh(); setEditing(null); }, onError: setError });
  const del = useMutation({ mutationFn: () => api.delete<ErrorDetail>(`/errors/${id}`, { reason }), onSuccess: () => { refresh(); setReason(""); }, onError: setError });
  const restore = useMutation({ mutationFn: () => api.post<ErrorDetail>(`/errors/${id}/restore`), onSuccess: refresh, onError: setError });
  const e = q.data;
  if (q.isLoading) return <Spinner />;
  if (q.error || !e) return <ErrorBox error={q.error ?? "Not found"} />;
  const overdue = e.status === "UNRESOLVED" && !!e.next_follow_up_at && new Date(e.next_follow_up_at) < new Date();
  const team = teams.find((t) => t.id === e.team_id);
  const deleted = !!e.deleted_at;

  return (
    <div className="max-w-5xl">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <Link to="/errors" className="text-sm text-navy">← All errors</Link>
          <h1 className="text-2xl font-bold">{e.display_id} <Badge status={e.status} overdue={overdue} /></h1>
          <p className="text-slate-600">{categories.find((c) => c.id === e.category_id)?.name}</p>
        </div>
        <div className="flex gap-2">
          {can("errors.edit") && !deleted && !editing && (
            <button className="btn-primary" onClick={() => setEditing({ description: e.description, category_id: e.category_id, supervisor_name: e.supervisor_name ?? "", enumerator_name: e.enumerator_name ?? "", action_taken: e.action_taken ?? "", comments: e.comments ?? "", status: e.status, support_method: e.support_method, date_received: e.date_received, note: "" })}>Edit</button>
          )}
          <button className="btn-outline" onClick={() => download(`/reports/error_detail?format=pdf&error_id=${e.id}`, `${e.display_id}.pdf`)}>Detail sheet (PDF)</button>
          {e.lat && e.lng && <a className="btn-outline" target="_blank" rel="noreferrer" href={`https://www.openstreetmap.org/?mlat=${e.lat}&mlon=${e.lng}#map=16/${e.lat}/${e.lng}`}>Map</a>}
        </div>
      </div>
      <ErrorBox error={error instanceof ApiError ? error.message : error} />
      {deleted && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          <span><strong>Deleted</strong> {fmt(e.deleted_at)}: {e.delete_reason}. It is hidden from the dashboard and removed from the tablet at its next sync.</span>
          {can("errors.delete") && <button className="btn-outline" disabled={restore.isPending} onClick={() => restore.mutate()}>Restore</button>}
        </div>
      )}

      {editing && (
        <Card title="Edit error record" className="mb-4">
          <p className="-mt-2 mb-3 text-xs text-slate-500">The change is written to the activity history, recorded in the audit log with the old and new values, and sent to the Field Monitor's tablet at its next sync.</p>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            <Field label="Status"><select className="input" value={editing.status} onChange={(ev) => setEditing({ ...editing, status: ev.target.value as Status })}><option value="UNRESOLVED">Unresolved</option><option value="RESOLVED">Resolved</option></select></Field>
            <Field label="Category"><select className="input" value={editing.category_id} onChange={(ev) => setEditing({ ...editing, category_id: Number(ev.target.value) })}>{categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>
            <Field label="Support method"><select className="input" value={editing.support_method} onChange={(ev) => setEditing({ ...editing, support_method: ev.target.value as "REMOTE" | "ONSITE" })}><option value="REMOTE">Remote</option><option value="ONSITE">Onsite</option></select></Field>
            <Field label="Supervisor"><input className="input" value={editing.supervisor_name} onChange={(ev) => setEditing({ ...editing, supervisor_name: ev.target.value })} /></Field>
            <Field label="Enumerator"><input className="input" value={editing.enumerator_name} onChange={(ev) => setEditing({ ...editing, enumerator_name: ev.target.value })} /></Field>
            <Field label="Date received"><input type="date" className="input" value={editing.date_received} onChange={(ev) => setEditing({ ...editing, date_received: ev.target.value })} /></Field>
            <div className="md:col-span-3"><Field label="Description"><textarea className="input" rows={2} value={editing.description} onChange={(ev) => setEditing({ ...editing, description: ev.target.value })} /></Field></div>
            <div className="md:col-span-3"><Field label="Action taken"><textarea className="input" rows={2} value={editing.action_taken} onChange={(ev) => setEditing({ ...editing, action_taken: ev.target.value })} /></Field></div>
            <div className="md:col-span-2"><Field label="Comments"><input className="input" value={editing.comments} onChange={(ev) => setEditing({ ...editing, comments: ev.target.value })} /></Field></div>
            <Field label="Reason for this change (goes to history and audit)"><input className="input" value={editing.note} onChange={(ev) => setEditing({ ...editing, note: ev.target.value })} /></Field>
          </div>
          <div className="mt-3 flex gap-2">
            <button className="btn-primary" disabled={save.isPending} onClick={() => save.mutate(editing)}>Save changes</button>
            <button className="btn-outline" onClick={() => setEditing(null)}>Cancel</button>
          </div>
        </Card>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card title="Error">
          <Row label="Description" value={e.description} />
          <Row label="District" value={districts.find((d) => d.id === e.district_id)?.name} />
          <Row label="Team" value={team ? `${team.code} ${team.name}` : null} />
          <Row label="Supervisor" value={e.supervisor_name} />
          <Row label="Enumerator" value={e.enumerator_name} />
          <Row label="Date received" value={fmtDate(e.date_received)} />
          <Row label="Support method" value={e.support_method === "ONSITE" ? "Onsite visit" : "Remote"} />
          <Row label="Action taken" value={e.action_taken} />
          <Row label="Comments" value={e.comments} />
          <Row label="Last action" value={fmt(e.last_action_at)} />
          <Row label={e.status === "RESOLVED" ? "Resolved at" : overdue ? "Follow-up was due" : "Next follow-up"} value={fmt(e.status === "RESOLVED" ? e.resolved_at : e.next_follow_up_at)} />
          <Row label="GPS" value={e.lat ? `${e.lat.toFixed(5)}, ${e.lng?.toFixed(5)} (±${e.accuracy_m ?? 0} m)` : null} />
          <Row label="Record version" value={e.version} />
        </Card>
        <Card title={`Follow-ups (${e.follow_ups.length})`}>
          {e.follow_ups.length === 0 && <p className="text-sm text-slate-400">None recorded</p>}
          {[...e.follow_ups].sort((a, b) => b.at.localeCompare(a.at)).map((f) => (
            <div key={f.id} className="border-b border-slate-100 py-2 text-sm last:border-0">
              <div className="font-medium">{fmt(f.at)} · {f.method === "ONSITE" ? "Onsite" : "Remote"}{f.contacted ? ` · ${f.contacted}` : ""}</div>
              {f.outcome && <div>{f.outcome}</div>}
              {f.comments && <div className="text-slate-500">{f.comments}</div>}
              {f.lat && <div className="text-xs text-slate-400">GPS {f.lat.toFixed(5)}, {f.lng?.toFixed(5)}</div>}
            </div>
          ))}
        </Card>
        <Card title="Activity history" className="lg:col-span-2">
          <table className="table">
            <thead><tr><th>When</th><th>Status</th><th>Action taken</th><th>Comments</th></tr></thead>
            <tbody>
              {[...e.activity].sort((a, b) => b.client_at.localeCompare(a.client_at)).map((a) => (
                <tr key={a.id}><td className="whitespace-nowrap">{fmt(a.client_at)}</td><td>{a.previous_status ? `${a.previous_status} → ` : ""}{a.new_status}</td><td>{a.action_taken}</td><td>{a.comments}</td></tr>
              ))}
            </tbody>
          </table>
        </Card>
        {can("errors.delete") && !deleted && (
          <Card title="Delete this error" className="lg:col-span-2">
            <p className="mb-2 text-sm text-slate-600">Deleting hides the error from every dashboard, report and summary and removes it from the Field Monitor's tablet at its next sync. The record is kept and can be restored; the deletion and its reason are recorded in the audit log.</p>
            <div className="flex flex-wrap gap-2">
              <input className="input md:w-96" placeholder="Reason (required)" value={reason} onChange={(ev) => setReason(ev.target.value)} />
              <button className="btn-outline text-red-700" disabled={!reason.trim() || del.isPending} onClick={() => { if (confirm(`Delete ${e.display_id}?`)) del.mutate(); }}>Delete</button>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
