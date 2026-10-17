import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import clsx from "clsx";
import { ArrowUpRight, CheckCircle2, Download, MessageSquare, Pencil, Play, RotateCcw, Siren, Trash2, UserCheck, X, XCircle } from "lucide-react";
import { ApiError, api, download, fmt, fmtDate, qs } from "../../api/client";
import type { District, Incident, IncidentPerson, IncidentSpec, Team } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { Card, Empty, ErrorBox, Field, Spinner } from "../../components/ui";
import { IncidentFields, emptyIncident, incidentPayload, validateIncident, type IncidentValues } from "./IncidentForm";
import { SEV, SeverityPill, StatusPill, ago, hours } from "./incidentUi";

/** The incident register: every incident in scope, with filters, the detail drawer and the handling actions. */
export default function IncidentsRegisterPage() {
  const { can, user } = useAuth();
  const qc = useQueryClient();
  const [params, setParams] = useSearchParams();
  const [f, setF] = useState({ status: params.get("status") ?? "", severity: "", category: "", district_id: params.get("district_id") ?? "", phase: "", overdue: false, search: "" });
  const query = qs(f);
  const list = useQuery({ queryKey: ["incidents", "list", query], queryFn: () => api.get<Incident[]>(`/incidents${query}`) });
  const spec = useQuery({ queryKey: ["incidents", "spec"], queryFn: () => api.get<IncidentSpec>("/incidents/spec") });
  const districts = useQuery({ queryKey: ["districts"], queryFn: () => api.get<District[]>("/admin/reference/districts") });
  const [openId, setOpenId] = useState<number | null>(params.get("open") ? Number(params.get("open")) : null);
  const [showNew, setShowNew] = useState(params.get("new") === "1");
  const [error, setError] = useState<unknown>(null);
  useEffect(() => { if (params.get("open") || params.get("new")) { const p = new URLSearchParams(params); p.delete("open"); p.delete("new"); setParams(p, { replace: true }); } }, [params, setParams]);
  const invalidate = () => qc.invalidateQueries({ queryKey: ["incidents"] });
  const rows = list.data ?? [];
  const exportFile = async (format: "xlsx" | "pdf") => { setError(null); try { await download(`/incidents/export${qs({ ...f, format })}`, `incidents.${format}`); } catch (err) { setError(err); } };

  return (
    <div className="max-w-7xl">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div><h1 className="text-2xl font-bold">Incident register</h1><p className="text-sm text-slate-500">Every incident in your scope. Click a row to see the full record and act on it.</p></div>
        <div className="flex flex-wrap gap-2">
          {can("incidents.report") && <button className="btn-primary" onClick={() => setShowNew(true)}><Siren size={16} /> Report an incident</button>}
          {can("incidents.export") && <button className="btn-outline" onClick={() => exportFile("xlsx")}><Download size={16} /> Excel</button>}
        </div>
      </div>
      <ErrorBox error={error instanceof ApiError ? error.message : error} />
      <Card className="mb-4">
        <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-7">
          <input className="input lg:col-span-2" placeholder="Search number, title, reporter, SA code…" value={f.search} onChange={(e) => setF({ ...f, search: e.target.value })} />
          <select className="input" value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })}><option value="">All statuses</option><option value="OPEN">Open (new, acknowledged, in progress)</option>{(spec.data?.statuses ?? []).map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}</select>
          <select className="input" value={f.severity} onChange={(e) => setF({ ...f, severity: e.target.value })}><option value="">All severities</option>{(spec.data?.severities ?? []).map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}</select>
          <select className="input" value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })}><option value="">All categories</option>{(spec.data?.categories ?? []).map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}</select>
          <select className="input" value={f.district_id} onChange={(e) => setF({ ...f, district_id: e.target.value })}><option value="">All districts</option>{(districts.data ?? []).filter((d) => !user?.district_ids?.length || user.district_ids.includes(d.id)).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.overdue} onChange={(e) => setF({ ...f, overdue: e.target.checked })} /> Overdue only</label>
        </div>
      </Card>
      <Card>
        {list.isLoading ? <Spinner /> : rows.length === 0 ? <Empty text="No incident matches" /> : (
          <div className="overflow-x-auto"><table className="table">
            <thead><tr><th>Number</th><th>Severity</th><th>Status</th><th>District · SA</th><th>Category</th><th>Title</th><th>Reporter</th><th>Reported</th><th>Owner</th><th>Due</th></tr></thead>
            <tbody>{rows.map((x) => (
              <tr key={x.id} className={clsx("cursor-pointer hover:bg-slate-50", x.overdue && "bg-amber-50/60", x.status === "NEW" && "font-medium")} onClick={() => setOpenId(x.id)}>
                <td className="font-mono text-navy">{x.number}</td><td><SeverityPill severity={x.severity} /></td><td><StatusPill status={x.status} label={x.status_label} /></td>
                <td>{x.district ?? <span className="text-amber-700">not set</span>}{x.sa_code ? <span className="block font-mono text-xs text-slate-500">{x.sa_code}</span> : x.team_code ? <span className="block text-xs text-slate-500">{x.team_code}</span> : null}</td>
                <td>{x.category_label}{x.subcategory_label && <span className="block text-xs text-slate-500">{x.subcategory_label}</span>}</td><td className="max-w-xs truncate" title={x.title}>{x.title}</td>
                <td>{x.reporter_name ?? x.reported_by_name}{x.reporter_role_label && <span className="block text-xs text-slate-500">{x.reporter_role_label}</span>}</td>
                <td className="whitespace-nowrap" title={fmt(x.reported_at)}>{ago(x.reported_at)}</td><td>{x.owner_name ?? <span className="text-red-700">unassigned</span>}</td>
                <td className={clsx("whitespace-nowrap", x.overdue && "font-semibold text-red-700")}>{x.due_at ? fmtDate(x.due_at) : ""}</td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </Card>
      {openId !== null && <IncidentDrawer id={openId} onClose={() => { setOpenId(null); invalidate(); }} />}
      {showNew && spec.data && <NewIncidentDialog spec={spec.data} districts={districts.data ?? []} onClose={() => setShowNew(false)} onSaved={(x) => { setShowNew(false); invalidate(); setOpenId(x.id); }} />}
    </div>
  );
}

function IncidentDrawer({ id, onClose }: { id: number; onClose: () => void }) {
  const { can } = useAuth();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["incidents", "detail", id], queryFn: () => api.get<Incident>(`/incidents/${id}`) });
  const people = useQuery({ queryKey: ["incidents", "people", q.data?.district_id], queryFn: () => api.get<IncidentPerson[]>(`/incidents/people${qs({ district_id: q.data?.district_id ?? undefined })}`), enabled: !!q.data && can("incidents.manage") });
  const districts = useQuery({ queryKey: ["districts"], queryFn: () => api.get<District[]>("/admin/reference/districts"), enabled: can("incidents.manage") });
  const [mode, setMode] = useState<null | "comment" | "assign" | "resolve" | "reject" | "reopen" | "escalate" | "district">(null);
  const [text, setText] = useState("");
  const [ownerId, setOwnerId] = useState("");
  const [districtId, setDistrictId] = useState("");
  const [fixed, setFixed] = useState<boolean | null>(null);
  const [error, setError] = useState<unknown>(null);
  const refresh = () => { qc.invalidateQueries({ queryKey: ["incidents"] }); setMode(null); setText(""); setError(null); };
  const act = useMutation({ mutationFn: (body: Record<string, unknown>) => api.post<Incident>(`/incidents/${id}/actions`, body), onSuccess: refresh, onError: setError });
  const comment = useMutation({ mutationFn: (t: string) => api.post<Incident>(`/incidents/${id}/comments`, { action: "comment", text: t }), onSuccess: refresh, onError: setError });
  const edit = useMutation({ mutationFn: (body: Record<string, unknown>) => api.patch<Incident>(`/incidents/${id}`, body), onSuccess: refresh, onError: setError });
  const remove = useMutation({ mutationFn: () => api.delete(`/incidents/${id}`), onSuccess: onClose, onError: setError });
  const x = q.data;
  const manage = can("incidents.manage");
  const open = x ? ["NEW", "ACKNOWLEDGED", "IN_PROGRESS"].includes(x.status) : false;
  const row = (label: string, value: React.ReactNode) => (value === null || value === undefined || value === "" ? null : <div className="grid grid-cols-[150px_1fr] gap-2 py-1 text-sm"><span className="text-slate-500">{label}</span><span>{value}</span></div>);
  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/40" onClick={onClose}>
      <div className="h-full w-full max-w-3xl overflow-y-auto bg-white shadow-2xl" onClick={(e) => e.stopPropagation()}>
        {!x ? <Spinner /> : (
          <>
            <div className="sticky top-0 z-10 border-b border-slate-200 bg-white px-5 py-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="flex flex-wrap items-center gap-2"><span className="font-mono text-lg font-bold text-navy">{x.number}</span><SeverityPill severity={x.severity} /><StatusPill status={x.status} label={x.status_label} />{x.overdue && <span className="rounded-full bg-red-600 px-2 py-0.5 text-xs font-semibold text-white">Overdue</span>}<span className="text-xs text-slate-500">{x.level === "DISTRICT" ? "District level" : x.level === "REGION" ? "Escalated to region" : "Escalated to national"}</span></div>
                  <h2 className="mt-1 text-lg font-semibold">{x.title}</h2>
                </div>
                <button className="text-slate-500 hover:text-slate-800" onClick={onClose}><X size={20} /></button>
              </div>
              {manage && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {x.status === "NEW" && <button className="btn-primary" onClick={() => act.mutate({ action: "acknowledge" })}><UserCheck size={16} /> Acknowledge</button>}
                  {(x.status === "NEW" || x.status === "ACKNOWLEDGED") && <button className="btn-outline" onClick={() => act.mutate({ action: "start" })}><Play size={16} /> Start work</button>}
                  {open && <button className="btn-outline" onClick={() => { setMode("assign"); setOwnerId(String(x.owner_id ?? "")); }}><UserCheck size={16} /> Assign</button>}
                  {open && <button className="btn-outline" onClick={() => setMode("resolve")}><CheckCircle2 size={16} /> Resolve</button>}
                  {x.status === "RESOLVED" && <button className="btn-primary" onClick={() => act.mutate({ action: "close" })}><CheckCircle2 size={16} /> Close</button>}
                  {open && can("incidents.escalate") && x.level !== "NATIONAL" && <button className="btn-outline" onClick={() => setMode("escalate")}><ArrowUpRight size={16} /> Escalate</button>}
                  {open && <button className="btn-outline" onClick={() => setMode("reject")}><XCircle size={16} /> Reject</button>}
                  {!open && <button className="btn-outline" onClick={() => setMode("reopen")}><RotateCcw size={16} /> Reopen</button>}
                  {(!x.district_id || !x.sa_recognised) && <button className="btn-outline" onClick={() => { setMode("district"); setDistrictId(String(x.district_id ?? "")); }}><Pencil size={16} /> Set district</button>}
                  <button className="btn-outline text-red-700" onClick={() => { if (confirm(`Delete ${x.number}? It disappears from the register and the dashboard.`)) remove.mutate(); }}><Trash2 size={16} /></button>
                </div>
              )}
              <ErrorBox error={error instanceof ApiError ? error.message : error} />
              {mode && (
                <div className="mt-3 rounded-md border border-slate-200 bg-slate-50 p-3">
                  {mode === "assign" && <Field label="Owner"><select className="input" value={ownerId} onChange={(e) => setOwnerId(e.target.value)}><option value="">Choose…</option>{(people.data ?? []).map((p) => <option key={p.id} value={p.id}>{p.full_name} · {p.role.replace(/_/g, " ").toLowerCase()}</option>)}</select></Field>}
                  {mode === "district" && <Field label="District"><select className="input" value={districtId} onChange={(e) => setDistrictId(e.target.value)}><option value="">Choose…</option>{(districts.data ?? []).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select></Field>}
                  {mode === "escalate" && <p className="mb-2 text-sm text-slate-600">Escalate to <b>{x.level === "DISTRICT" ? "region" : "national"}</b> level: say what decision or resource is needed.</p>}
                  {mode === "resolve" && <div className="mb-2 flex gap-2 text-sm"><span className="text-slate-600">Root cause fixed?</span>{[["yes", true], ["no, workaround", false]].map(([lb, val]) => <button key={String(lb)} className={clsx("rounded-md border px-2 py-0.5", fixed === val ? "border-navy bg-navy text-white" : "border-slate-300 bg-white")} onClick={() => setFixed(val as boolean)}>{String(lb)}</button>)}</div>}
                  {mode !== "assign" && mode !== "district" && <textarea className="input" rows={3} value={text} onChange={(e) => setText(e.target.value)} placeholder={mode === "resolve" ? "What was done, by whom, when" : mode === "reject" ? "Why this is not an incident (duplicate, not a census matter…)" : mode === "reopen" ? "Why it is reopened" : "Your comment"} />}
                  <div className="mt-2 flex justify-end gap-2">
                    <button className="btn-outline" onClick={() => setMode(null)}>Cancel</button>
                    <button className="btn-primary" onClick={() => {
                      if (mode === "comment") comment.mutate(text);
                      else if (mode === "assign") act.mutate({ action: "assign", owner_id: Number(ownerId) });
                      else if (mode === "district") edit.mutate({ district_id: Number(districtId) });
                      else if (mode === "resolve") act.mutate({ action: "resolve", text, root_cause_fixed: fixed });
                      else act.mutate({ action: mode, text });
                    }}>{mode === "comment" ? "Add comment" : mode === "assign" ? "Assign" : mode === "district" ? "Save" : mode === "resolve" ? "Mark resolved" : mode === "reject" ? "Reject" : mode === "reopen" ? "Reopen" : "Escalate"}</button>
                  </div>
                </div>
              )}
            </div>
            <div className="grid gap-4 p-5 lg:grid-cols-2">
              <div>
                <h3 className="mb-1 text-xs font-bold uppercase tracking-wide text-slate-500">What</h3>
                {row("Category", `${x.category_label}${x.subcategory_label ? ` · ${x.subcategory_label}` : ""}`)}
                {row("Severity", <span>{x.severity_label} · <span className="text-slate-500">{SEV[x.severity] ? "" : ""}</span></span>)}
                {row("Phase", x.phase_label)}
                {row("Description", <span className="whitespace-pre-wrap">{x.description}</span>)}
                {row("Action taken", x.action_taken)}
                {row("Help needed", x.help_needed)}
                {row("Impact", [x.teams_affected !== null && `${x.teams_affected} teams`, x.staff_affected !== null && `${x.staff_affected} staff`, x.households_affected !== null && `${x.households_affected} households`, x.days_lost !== null && `${x.days_lost} days lost`].filter(Boolean).join(" · "))}
                {row("Tablets", x.asset_tags)}
                {row("Reference", x.reference)}
                <h3 className="mb-1 mt-3 text-xs font-bold uppercase tracking-wide text-slate-500">Where and when</h3>
                {row("District", x.district ? `${x.district} (${x.region})` : <span className="text-amber-700">not set{x.sa_code ? ` · SA code ${x.sa_code} not recognised` : ""}</span>)}
                {row("SA", [x.sa_code, x.team_code].filter(Boolean).join(" · "))}
                {row("EA · locality", [x.ea_code, x.locality].filter(Boolean).join(" · "))}
                {row("GPS", x.lat !== null ? `${x.lat?.toFixed(5)}, ${x.lng?.toFixed(5)}` : null)}
                {row("Happened", fmt(x.occurred_at))}
                {row("Reported", `${fmt(x.reported_at)} · ${x.reported_by_name ?? "public page"}`)}
                {row("Reporter", [x.reporter_name, x.reporter_role_label, x.reporter_code && `code ${x.reporter_code}`, x.reporter_phone].filter(Boolean).join(" · "))}
                <h3 className="mb-1 mt-3 text-xs font-bold uppercase tracking-wide text-slate-500">Handling</h3>
                {row("Owner", x.owner_name ?? <span className="text-red-700">unassigned</span>)}
                {row("Due", x.due_at ? `${fmt(x.due_at)}${x.overdue ? " · overdue" : ""}` : null)}
                {row("Acknowledged", x.acknowledged_at ? `${fmt(x.acknowledged_at)} (${hours(x.hours_to_acknowledge)} after report)` : "not yet")}
                {row("Resolved", x.resolved_at ? `${fmt(x.resolved_at)} (${hours(x.hours_to_resolve)} after report)` : null)}
                {row("Resolution", x.resolution)}
                {row("Root cause", x.root_cause_fixed === null ? null : x.root_cause_fixed ? "fixed" : "workaround in place")}
                {row("Lessons", x.lessons)}
                {row("Rejected because", x.reject_reason)}
                {row("Closed", x.closed_at ? fmt(x.closed_at) : null)}
              </div>
              <div>
                <div className="mb-2 flex items-center justify-between"><h3 className="text-xs font-bold uppercase tracking-wide text-slate-500">Log</h3><button className="text-xs text-navy underline" onClick={() => setMode("comment")}><MessageSquare size={12} className="mr-1 inline" />Add comment</button></div>
                <ol className="relative border-l border-slate-200 pl-4">
                  {[...x.updates].reverse().map((u) => (
                    <li key={u.id} className="mb-3">
                      <span className={clsx("absolute -left-1.5 mt-1.5 h-3 w-3 rounded-full", u.type === "STATUS" || u.type === "REOPEN" ? "bg-navy" : u.type === "ESCALATE" ? "bg-red-600" : u.type === "ASSIGN" ? "bg-emerald-600" : "bg-slate-300")} />
                      <div className="text-xs text-slate-500">{fmt(u.at)} · {u.author ?? "system"} · {u.type_label}{u.old_value || u.new_value ? ` (${u.old_value ?? "—"} → ${u.new_value ?? "—"})` : ""}</div>
                      {u.text && <div className="text-sm whitespace-pre-wrap">{u.text}</div>}
                    </li>
                  ))}
                </ol>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function NewIncidentDialog({ spec, districts, onClose, onSaved }: { spec: IncidentSpec; districts: District[]; onClose: () => void; onSaved: (x: Incident) => void }) {
  const { user } = useAuth();
  const mine = districts.filter((d) => !user?.district_ids?.length || user.district_ids.includes(d.id));
  const [values, setValues] = useState<IncidentValues>(emptyIncident());
  const [districtId, setDistrictId] = useState(mine.length === 1 ? String(mine[0].id) : "");
  const [teamId, setTeamId] = useState("");
  const [saCode, setSaCode] = useState("");
  const [reporter, setReporter] = useState({ name: "", role: "", phone: "" });
  const [serverErrors, setServerErrors] = useState<string[]>([]);
  const teams = useQuery({ queryKey: ["teams", districtId], queryFn: () => api.get<Team[]>(`/admin/reference/teams?district_id=${districtId}`), enabled: !!districtId });
  const errors = validateIncident(values);
  const save = useMutation({
    mutationFn: () => api.post<Incident>("/incidents", { ...incidentPayload(values), district_id: districtId ? Number(districtId) : null, team_id: teamId ? Number(teamId) : null, sa_code: saCode.trim() || null, reporter_name: reporter.name.trim() || null, reporter_role: reporter.role || null, reporter_phone: reporter.phone.trim() || null }),
    onSuccess: onSaved,
    onError: (err) => { const detail = err instanceof ApiError ? (err.body as { detail?: { errors?: string[] } | string } | undefined)?.detail : undefined; setServerErrors(detail && typeof detail === "object" && Array.isArray(detail.errors) ? detail.errors : [err instanceof ApiError ? err.message : String(err)]); },
  });
  return (
    <div className="fixed inset-0 z-40 flex items-start justify-center overflow-y-auto bg-black/40 p-4" onClick={onClose}>
      <div className="w-full max-w-3xl rounded-lg bg-white p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="mb-3 flex items-center justify-between"><h2 className="text-lg font-semibold">Report an incident</h2><button className="btn-outline" onClick={onClose}>Close</button></div>
        <div className="mb-4 grid gap-3 sm:grid-cols-3">
          <Field label="District *"><select className="input" value={districtId} onChange={(e) => { setDistrictId(e.target.value); setTeamId(""); }}><option value="">Choose…</option>{mine.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select></Field>
          <Field label="Supervisory area"><select className="input" value={teamId} onChange={(e) => setTeamId(e.target.value)} disabled={!districtId}><option value="">Not specified</option>{(teams.data ?? []).map((t) => <option key={t.id} value={t.id}>{t.code} {t.name}</option>)}</select></Field>
          <Field label="SA code (12 digits, optional)"><input className="input" value={saCode} onChange={(e) => setSaCode(e.target.value.replace(/\D/g, "").slice(0, 12))} placeholder="000000000100" /></Field>
        </div>
        <div className="mb-4 grid gap-3 rounded-md border border-slate-200 bg-slate-50 p-3 sm:grid-cols-3">
          <Field label="Reported on behalf of (name)"><input className="input" value={reporter.name} onChange={(e) => setReporter({ ...reporter, name: e.target.value })} placeholder="Leave blank if it is you" /></Field>
          <Field label="Their role"><select className="input" value={reporter.role} onChange={(e) => setReporter({ ...reporter, role: e.target.value })}><option value="">—</option>{spec.reporter_roles.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}</select></Field>
          <Field label="Their phone"><input className="input" value={reporter.phone} onChange={(e) => setReporter({ ...reporter, phone: e.target.value })} /></Field>
        </div>
        <IncidentFields spec={spec} values={values} onChange={setValues} />
        {(serverErrors.length > 0 || (errors.length > 0 && values.title)) && <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900"><ul className="list-disc pl-5">{[...serverErrors, ...errors].map((e) => <li key={e}>{e}</li>)}</ul></div>}
        <div className="mt-4 flex justify-end gap-2"><button className="btn-outline" onClick={onClose}>Cancel</button><button className="btn-primary" disabled={save.isPending || errors.length > 0 || !districtId} onClick={() => save.mutate()}>{save.isPending ? "Saving…" : "Report"}</button></div>
      </div>
    </div>
  );
}
