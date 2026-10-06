import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import clsx from "clsx";
import { ApiError, api, fmt, qs, tokens } from "../../api/client";
import type { District, Named, Role, User, UserActivity, UserImportResult, UserStats } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { Card, Empty, ErrorBox, Field, KpiTile, Spinner } from "../../components/ui";
import UserRightsDialog from "./UserRightsDialog";

export const ROLES: { value: Role; label: string; scope: "district" | "region" | "none"; level: string }[] = [
  { value: "FIELD_MONITOR", label: "Field Monitor (tablet)", scope: "district", level: "District" },
  { value: "DISTRICT_DQM", label: "District DQM", scope: "district", level: "District" },
  { value: "REGIONAL", label: "Regional staff", scope: "region", level: "Region" },
  { value: "NATIONAL_DQM", label: "National DQM", scope: "none", level: "National" },
  { value: "ADMIN", label: "Administrator", scope: "none", level: "National" },
];
const roleLabel = (r: Role) => ROLES.find((x) => x.value === r)?.label ?? r;

interface Form { id?: number; username: string; password: string; full_name: string; phone: string; role: Role; staff_code: string; district_ids: number[]; region_ids: number[]; active: boolean }
const empty: Form = { username: "", password: "", full_name: "", phone: "", role: "DISTRICT_DQM", staff_code: "", district_ids: [], region_ids: [], active: true };

function Modal({ title, onClose, children, wide }: { title: string; onClose: () => void; children: React.ReactNode; wide?: boolean }) {
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div className={clsx("max-h-[90vh] w-full overflow-auto rounded-lg bg-white p-5 shadow-xl", wide ? "max-w-4xl" : "max-w-2xl")} onClick={(e) => e.stopPropagation()}>
        <h2 className="mb-3 text-lg font-bold">{title}</h2>
        {children}
      </div>
    </div>
  );
}

export default function UsersPage() {
  const qc = useQueryClient();
  const { can, user: me } = useAuth();
  const [params, setParams] = useSearchParams();
  const set = (k: string, v: string) => { const n = new URLSearchParams(params); if (v) n.set(k, v); else n.delete(k); setParams(n, { replace: true }); };
  const filters = { search: params.get("search") || undefined, role: params.get("role") || undefined, district_id: params.get("district_id") || undefined, region_id: params.get("region_id") || undefined, active: params.get("active") || undefined };
  const q = qs(filters);
  const users = useQuery({ queryKey: ["admin", "users", q], queryFn: () => api.get<User[]>(`/admin/users${q}`) });
  const stats = useQuery({ queryKey: ["admin", "user-stats"], queryFn: () => api.get<UserStats>("/admin/users/stats") });
  const districts = useQuery({ queryKey: ["ref", "districts"], queryFn: () => api.get<District[]>("/admin/reference/districts"), staleTime: 300_000 });
  const regions = useQuery({ queryKey: ["ref", "regions"], queryFn: () => api.get<Named[]>("/admin/reference/regions"), staleTime: 300_000 });
  const [form, setForm] = useState<Form | null>(null);
  const [rightsFor, setRightsFor] = useState<User | null>(null);
  const [resetFor, setResetFor] = useState<User | null>(null);
  const [resetPassword, setResetPassword] = useState("");
  const [resetResult, setResetResult] = useState<string | null>(null);
  const [activityFor, setActivityFor] = useState<User | null>(null);
  const [showImport, setShowImport] = useState(false);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importResult, setImportResult] = useState<UserImportResult | null>(null);
  const [error, setError] = useState<unknown>(null);
  const invalidate = () => { qc.invalidateQueries({ queryKey: ["admin", "users"] }); qc.invalidateQueries({ queryKey: ["admin", "user-stats"] }); };

  const save = useMutation({
    mutationFn: async (f: Form) => {
      const body: Record<string, unknown> = { full_name: f.full_name, phone: f.phone || null, role: f.role, staff_code: f.staff_code.trim(), district_ids: f.district_ids, region_ids: f.region_ids };
      if (f.id) { body.active = f.active; if (f.password) body.password = f.password; return api.patch(`/admin/users/${f.id}`, body); }
      return api.post("/admin/users", { ...body, username: f.username, password: f.password });
    },
    onSuccess: () => { invalidate(); setForm(null); setError(null); },
    onError: setError,
  });
  const toggleActive = useMutation({
    mutationFn: (u: User) => api.post(`/admin/users/${u.id}/${u.active ? "deactivate" : "activate"}`),
    onSuccess: () => { invalidate(); setError(null); },
    onError: setError,
  });
  const reset = useMutation({
    mutationFn: (u: User) => api.post<{ temporary_password: string | null }>(`/admin/users/${u.id}/reset-password`, { password: resetPassword || null }),
    onSuccess: (r) => { setResetResult(r.temporary_password ? `Temporary password: ${r.temporary_password}` : "Password changed."); setResetPassword(""); setError(null); },
    onError: setError,
  });
  const resetPin = useMutation({
    mutationFn: (u: User) => api.post(`/admin/users/${u.id}/reset-pin`),
    onSuccess: () => { invalidate(); setError(null); },
    onError: setError,
  });
  const importUsers = useMutation({
    mutationFn: async () => { const fd = new FormData(); fd.append("file", importFile!); return api.post<UserImportResult>("/admin/users/import", fd); },
    onSuccess: (r) => { setImportResult(r); invalidate(); setError(null); },
    onError: setError,
  });
  const activity = useQuery({ queryKey: ["admin", "user-activity", activityFor?.id], queryFn: () => api.get<UserActivity>(`/admin/users/${activityFor!.id}/activity`), enabled: !!activityFor });

  const submit = (e: FormEvent) => { e.preventDefault(); if (form) save.mutate(form); };
  const roleScope = (r: Role) => ROLES.find((x) => x.value === r)?.scope ?? "none";
  const districtName = (id: number | null) => districts.data?.find((d) => d.id === id)?.name ?? "";
  const regionName = (id: number | null) => regions.data?.find((d) => d.id === id)?.name ?? "";
  const scopeText = (u: User) => u.scopes.map((s) => s.district_id ? districtName(s.district_id) : regionName(s.region_id)).join(", ") || (u.role === "NATIONAL_DQM" || u.role === "ADMIN" ? "National" : "none");
  const downloadTemplate = async () => {
    const res = await fetch("/api/v1/admin/users/template.csv", { headers: { Authorization: `Bearer ${tokens.access ?? ""}` } });
    const url = URL.createObjectURL(await res.blob()); const a = document.createElement("a"); a.href = url; a.download = "users-template.csv"; a.click(); URL.revokeObjectURL(url);
  };
  const s = stats.data;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">User management</h1>
          <p className="text-sm text-slate-500">Accounts for every level: district, regional and national. Every action here is recorded in the audit log.</p>
        </div>
        <div className="flex gap-2">
          <button className="btn-outline" onClick={() => { setShowImport(true); setImportResult(null); }}>Import from CSV</button>
          <button className="btn-primary" onClick={() => setForm(empty)}>New user</button>
        </div>
      </div>
      {s && (
        <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
          <KpiTile label="Users" value={s.total} onClick={() => setParams(new URLSearchParams())} />
          <KpiTile label="Active" value={s.active} tone="green" onClick={() => set("active", "true")} />
          <KpiTile label="Deactivated" value={s.inactive} tone="red" onClick={() => set("active", "false")} />
          <KpiTile label="Locked (failed logins)" value={s.locked} tone="amber" />
          <KpiTile label="Never signed in" value={s.never_logged_in} tone="amber" />
          <KpiTile label="Field Monitors" value={s.by_role.FIELD_MONITOR ?? 0} onClick={() => set("role", "FIELD_MONITOR")} />
          <KpiTile label="District DQM" value={s.by_role.DISTRICT_DQM ?? 0} onClick={() => set("role", "DISTRICT_DQM")} />
          <KpiTile label="Regional · National · Admin" value={`${s.by_role.REGIONAL ?? 0} · ${s.by_role.NATIONAL_DQM ?? 0} · ${s.by_role.ADMIN ?? 0}`} />
        </div>
      )}
      <div className="card mb-4 grid grid-cols-2 gap-3 md:grid-cols-5">
        <Field label="Search"><input className="input" placeholder="name, username, phone" defaultValue={filters.search ?? ""} onKeyDown={(e) => { if (e.key === "Enter") set("search", (e.target as HTMLInputElement).value); }} /></Field>
        <Field label="Role"><select className="input" value={filters.role ?? ""} onChange={(e) => set("role", e.target.value)}><option value="">All</option>{ROLES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}</select></Field>
        <Field label="Region"><select className="input" value={filters.region_id ?? ""} onChange={(e) => set("region_id", e.target.value)}><option value="">All</option>{regions.data?.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}</select></Field>
        <Field label="District"><select className="input" value={filters.district_id ?? ""} onChange={(e) => set("district_id", e.target.value)}><option value="">All</option>{districts.data?.filter((d) => !filters.region_id || String(d.region_id) === filters.region_id).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select></Field>
        <Field label="Status"><select className="input" value={filters.active ?? ""} onChange={(e) => set("active", e.target.value)}><option value="">All</option><option value="true">Active</option><option value="false">Deactivated</option></select></Field>
      </div>
      <ErrorBox error={error instanceof ApiError ? error.message : error} />

      <Card title={`${users.data?.length ?? 0} users`}>
        {users.isLoading ? <Spinner /> : users.data?.length ? (
          <div className="overflow-x-auto">
            <table className="table">
              <thead><tr><th>Name</th><th>Role</th><th>Scope</th><th>Phone</th><th>Last sign-in</th><th>Status</th><th>Actions</th></tr></thead>
              <tbody>
                {users.data.map((u) => (
                  <tr key={u.id} className={clsx(!u.active && "text-slate-400")}>
                    <td className="font-medium">{u.full_name}<div className="text-xs font-normal text-slate-400">{u.username}{u.staff_code ? ` · ${u.staff_code}` : ""}</div></td>
                    <td>{roleLabel(u.role)}<div className="text-xs text-slate-400">{ROLES.find((r) => r.value === u.role)?.level}</div></td>
                    <td>{scopeText(u)}</td>
                    <td>{u.phone}</td>
                    <td className="whitespace-nowrap">{u.last_login_at ? fmt(u.last_login_at) : <span className="text-amber-800">never</span>}</td>
                    <td>
                      {u.active ? <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-semibold text-green-800">Active</span> : <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-800">Deactivated</span>}
                      {u.pin_reset_requested_at && <div className="mt-1 text-xs text-amber-800" title={`Requested ${fmt(u.pin_reset_requested_at)}; clears when the monitor signs in again`}>PIN reset pending</div>}
                    </td>
                    <td className="whitespace-nowrap text-sm">
                      <button className="text-navy" onClick={() => setForm({ id: u.id, username: u.username, password: "", full_name: u.full_name, phone: u.phone ?? "", role: u.role, staff_code: u.staff_code ?? "", district_ids: u.scopes.map((s) => s.district_id).filter((x): x is number => !!x), region_ids: u.scopes.map((s) => s.region_id).filter((x): x is number => !!x), active: u.active })}>Edit</button>
                      {can("roles.manage") && <button className="ml-3 text-navy" onClick={() => setRightsFor(u)}>Rights</button>}
                      <button className="ml-3 text-navy" onClick={() => { setResetFor(u); setResetResult(null); setResetPassword(""); }}>Reset password</button>
                      {u.role === "FIELD_MONITOR" && (
                        <button className="ml-3 text-navy" onClick={() => { if (confirm(`Reset the tablet PIN for ${u.full_name}?\n\nThe tablet forgets its PIN at its next sync. The monitor then signs in again with the password and chooses a new PIN. Records on the tablet are kept.`)) resetPin.mutate(u); }}>Reset tablet PIN</button>
                      )}
                      <button className="ml-3 text-navy" onClick={() => setActivityFor(u)}>Activity</button>
                      {u.id !== me?.id && <button className={clsx("ml-3", u.active ? "text-red-700" : "text-green-700")} onClick={() => { if (confirm(`${u.active ? "Deactivate" : "Reactivate"} ${u.full_name}?`)) toggleActive.mutate(u); }}>{u.active ? "Deactivate" : "Reactivate"}</button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <Empty text="No users match" />}
      </Card>

      {form && (
        <Modal title={form.id ? `Edit ${form.username}` : "New user"} onClose={() => setForm(null)}>
          <form onSubmit={submit} className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {!form.id && <Field label="Username"><input className="input" required value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} /></Field>}
            <Field label={form.id ? "New password (leave blank to keep)" : "Password (min 8)"}><input className="input" type="password" required={!form.id} minLength={8} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></Field>
            <Field label="Full name"><input className="input" required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></Field>
            <Field label="Phone"><input className="input" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></Field>
            {(form.role === "FIELD_MONITOR" || form.role === "DISTRICT_DQM") && (
              <Field label="Staff code from the workload frame"><input className="input" placeholder={form.role === "FIELD_MONITOR" ? "FM-11-001" : "DQM-11-001"} value={form.staff_code} onChange={(e) => setForm({ ...form, staff_code: e.target.value.toUpperCase() })} /></Field>
            )}
            <Field label="Role (level)">
              <select className="input" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as Role, district_ids: [], region_ids: [] })}>
                {ROLES.map((r) => <option key={r.value} value={r.value}>{r.label} · {r.level}</option>)}
              </select>
            </Field>
            {roleScope(form.role) === "district" && (
              <Field label="District(s) (Ctrl-click for several)">
                <select className="input h-32" multiple value={form.district_ids.map(String)} onChange={(e) => setForm({ ...form, district_ids: Array.from(e.target.selectedOptions).map((o) => Number(o.value)) })}>
                  {districts.data?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
                </select>
              </Field>
            )}
            {roleScope(form.role) === "region" && (
              <Field label="Region">
                <select className="input" value={form.region_ids[0] ?? ""} onChange={(e) => setForm({ ...form, region_ids: e.target.value ? [Number(e.target.value)] : [] })}>
                  <option value="">Select…</option>
                  {regions.data?.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
                </select>
              </Field>
            )}
            {roleScope(form.role) === "none" && <p className="text-sm text-slate-500 md:col-span-2">National scope: sees every region and district.</p>}
            <div className="md:col-span-2 flex justify-end gap-2">
              <button type="button" className="btn-outline" onClick={() => setForm(null)}>Cancel</button>
              <button className="btn-primary" disabled={save.isPending}>Save</button>
            </div>
          </form>
        </Modal>
      )}

      {resetFor && (
        <Modal title={`Reset password for ${resetFor.full_name}`} onClose={() => setResetFor(null)}>
          {resetResult ? (
            <div>
              <p className="rounded-md border border-green-200 bg-green-50 p-3 text-sm text-green-800">{resetResult}{resetResult.startsWith("Temporary") && " — shown once; give it to the user and ask them to change it after signing in."}</p>
              <div className="mt-3 flex justify-end"><button className="btn-primary" onClick={() => setResetFor(null)}>Close</button></div>
            </div>
          ) : (
            <div className="space-y-3">
              <p className="text-sm text-slate-600">Enter a new password, or leave it blank to generate a temporary one. The user is signed out everywhere.</p>
              <input className="input" type="text" placeholder="New password (optional, min 8)" value={resetPassword} onChange={(e) => setResetPassword(e.target.value)} />
              <div className="flex justify-end gap-2"><button className="btn-outline" onClick={() => setResetFor(null)}>Cancel</button><button className="btn-primary" disabled={reset.isPending || (resetPassword.length > 0 && resetPassword.length < 8)} onClick={() => reset.mutate(resetFor)}>Reset</button></div>
            </div>
          )}
        </Modal>
      )}

      {activityFor && (
        <Modal title={`${activityFor.full_name} · activity`} onClose={() => setActivityFor(null)} wide>
          {activity.isLoading || !activity.data ? <Spinner /> : (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <KpiTile label="Sign-ins" value={activity.data.counts.logins} />
                <KpiTile label="Errors logged (tablet)" value={activity.data.counts.errors_logged} />
                <KpiTile label="Daily reports created" value={activity.data.counts.daily_reports} />
                <KpiTile label="Check-outs created" value={activity.data.counts.checkouts} />
              </div>
              {activity.data.devices.length > 0 && (
                <div>
                  <div className="mb-1 text-sm font-semibold">Tablets</div>
                  <table className="table"><thead><tr><th>Model</th><th>App</th><th>Last sync</th><th>Status</th></tr></thead><tbody>{activity.data.devices.map((d) => <tr key={d.id}><td>{d.model}</td><td>{d.app_version}</td><td>{d.last_sync_at ? fmt(d.last_sync_at) : "never"}</td><td>{d.status}</td></tr>)}</tbody></table>
                </div>
              )}
              <div>
                <div className="mb-1 text-sm font-semibold">Recent actions</div>
                {activity.data.recent.length === 0 ? <Empty text="No actions recorded" /> : (
                  <table className="table"><thead><tr><th>When</th><th>Action</th><th>Record</th><th>Address</th></tr></thead><tbody>{activity.data.recent.map((a) => <tr key={a.id}><td className="whitespace-nowrap">{fmt(a.at)}</td><td>{a.action}</td><td>{a.entity} {a.entity_id}</td><td className="text-xs text-slate-400">{a.ip}</td></tr>)}</tbody></table>
                )}
              </div>
            </div>
          )}
        </Modal>
      )}

      {showImport && (
        <Modal title="Import users from CSV" onClose={() => setShowImport(false)}>
          <p className="mb-2 text-sm text-slate-600">Columns: username, password (blank = generated, shown nowhere: reset it afterwards), full_name, phone, role (FIELD_MONITOR, DISTRICT_DQM, REGIONAL, NATIONAL_DQM, ADMIN), districts (names or codes separated by ;), region, staff_code (FM-11-001 or DQM-11-001 from the workload frame). Existing usernames are skipped.</p>
          <button className="mb-3 text-sm text-navy" onClick={downloadTemplate}>Download template</button>
          <div className="flex flex-wrap items-center gap-3">
            <input type="file" accept=".csv" onChange={(e) => setImportFile(e.target.files?.[0] ?? null)} />
            <button className="btn-primary" disabled={!importFile || importUsers.isPending} onClick={() => importUsers.mutate()}>{importUsers.isPending ? "Importing…" : "Import"}</button>
          </div>
          {importResult && (
            <div className="mt-3 text-sm">
              <p>Created {importResult.created}, skipped {importResult.skipped} existing, {importResult.errors.length} errors.</p>
              {importResult.errors.length > 0 && <ul className="mt-1 list-disc pl-5 text-red-700">{importResult.errors.map((e, i) => <li key={i}>{e}</li>)}</ul>}
            </div>
          )}
        </Modal>
      )}

      {rightsFor && <UserRightsDialog user={rightsFor} onClose={() => setRightsFor(null)} />}
    </div>
  );
}
