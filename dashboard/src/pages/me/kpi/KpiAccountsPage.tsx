import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import clsx from "clsx";
import { Copy, KeyRound, Plus, Smartphone, UserCheck, UserX } from "lucide-react";
import { ApiError, api, fmtDate } from "../../../api/client";
import type { MeKpiFieldAccount, MeKpiFieldAccountOptions } from "../../../api/types";
import { Card, Empty, ErrorBox, Field, KpiTile, Spinner } from "../../../components/ui";

type Form = { username: string; full_name: string; phone: string; role: "ME_DISTRICT" | "ME_REGIONAL"; district_ids: number[]; region_ids: number[] };
const empty: Form = { username: "", full_name: "", phone: "", role: "ME_DISTRICT", district_ids: [], region_ids: [] };

/** The M&E lead creates and manages the District and Regional M&E Officers who use the field tool app. */
export default function KpiAccountsPage() {
  const qc = useQueryClient();
  const list = useQuery({ queryKey: ["me-kpi", "accounts"], queryFn: () => api.get<MeKpiFieldAccount[]>("/me/kpi/accounts") });
  const options = useQuery({ queryKey: ["me-kpi", "account-options"], queryFn: () => api.get<MeKpiFieldAccountOptions>("/me/kpi/accounts/options") });
  const [form, setForm] = useState<Form | null>(null);
  const [edit, setEdit] = useState<MeKpiFieldAccount | null>(null);
  const [editDistricts, setEditDistricts] = useState<number[]>([]);
  const [created, setCreated] = useState<MeKpiFieldAccount | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [copied, setCopied] = useState(false);
  const invalidate = () => qc.invalidateQueries({ queryKey: ["me-kpi", "accounts"] });
  const create = useMutation({ mutationFn: (f: Form) => api.post<MeKpiFieldAccount>("/me/kpi/accounts", { username: f.username.trim(), full_name: f.full_name.trim(), phone: f.phone || null, role: f.role, district_ids: f.role === "ME_DISTRICT" ? f.district_ids : [], region_ids: f.role === "ME_REGIONAL" ? f.region_ids : [] }), onSuccess: (a) => { invalidate(); setForm(null); setCreated(a); setError(null); }, onError: setError });
  const toggle = useMutation({ mutationFn: (a: MeKpiFieldAccount) => api.patch(`/me/kpi/accounts/${a.id}`, { active: !a.active }), onSuccess: invalidate, onError: setError });
  const saveDistricts = useMutation({ mutationFn: (a: MeKpiFieldAccount) => api.patch(`/me/kpi/accounts/${a.id}`, { district_ids: editDistricts }), onSuccess: () => { invalidate(); setEdit(null); }, onError: setError });
  const reset = useMutation({ mutationFn: (a: MeKpiFieldAccount) => api.post<MeKpiFieldAccount>(`/me/kpi/accounts/${a.id}/reset-password`), onSuccess: (a) => { invalidate(); setCreated(a); }, onError: setError });
  const data = list.data ?? [];
  const districts = options.data?.districts ?? [];
  const regions = options.data?.regions ?? [];
  const copyText = async (t: string) => { try { await navigator.clipboard.writeText(t); setCopied(true); setTimeout(() => setCopied(false), 2000); } catch { prompt("Copy", t); } };

  return (
    <div className="max-w-6xl">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link to="/me/kpi" className="text-sm text-navy">← M&amp;E Field Tool</Link>
          <h1 className="text-2xl font-bold">Field accounts</h1>
          <p className="text-sm text-slate-500">The M&amp;E officers who use the field tool app. A District M&amp;E Officer collects for one or more districts; a Regional M&amp;E Officer for a whole region. Each account gets a temporary password to read out, changed at the first sign-in.</p>
        </div>
        <button className="btn-primary" onClick={() => { setForm(empty); setError(null); }}><Plus size={16} /> New field officer</button>
      </div>
      <ErrorBox error={error instanceof ApiError ? error.message : error} />
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <KpiTile label="Field accounts" value={data.length} sub={`${data.filter((a) => a.active).length} active`} />
        <KpiTile label="District officers" value={data.filter((a) => a.role === "ME_DISTRICT").length} />
        <KpiTile label="Regional officers" value={data.filter((a) => a.role === "ME_REGIONAL").length} />
        <KpiTile label="Signed in at least once" value={data.filter((a) => a.last_login_at).length} tone="green" sub={`${data.filter((a) => a.must_change_password).length} still on the temporary password`} />
      </div>
      {created && (
        <Card className="mb-4 border-l-4 border-emerald-500">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="font-semibold text-navy"><Smartphone size={16} className="mr-1 inline" />{created.full_name} can now sign in to the app</div>
              <div className="mt-1 text-sm">Username <span className="rounded bg-slate-100 px-1.5 font-mono">{created.username}</span> · temporary password <span className="rounded bg-amber-100 px-1.5 font-mono">{created.temporary_password}</span></div>
              <div className="mt-1 text-xs text-slate-500">Shown once. Give it to the officer; the app asks for a new password at the first sign-in. App download: {window.location.origin}/api/v1/public/app/fieldtool.apk</div>
            </div>
            <div className="flex gap-2">
              <button className="btn-outline" onClick={() => copyText(`M&E Field Tool\nUsername: ${created.username}\nTemporary password: ${created.temporary_password}\nApp: ${window.location.origin}/api/v1/public/app/fieldtool.apk`)}><Copy size={16} /> {copied ? "Copied" : "Copy details"}</button>
              <button className="btn-outline" onClick={() => setCreated(null)}>Close</button>
            </div>
          </div>
        </Card>
      )}
      <Card>
        {list.isLoading ? <Spinner /> : data.length === 0 ? <Empty text="No field officer yet. Create the District M&E Officers who will use the app." /> : (
          <div className="overflow-x-auto">
            <table className="table">
              <thead><tr><th>Officer</th><th>Role</th><th>Area</th><th>Phone</th><th>Last sign-in</th><th className="text-right">Reports</th><th>Status</th><th /></tr></thead>
              <tbody>
                {data.map((a) => (
                  <tr key={a.id} className={clsx(!a.active && "text-slate-400")}>
                    <td className="font-medium">{a.full_name}<div className="text-xs font-normal text-slate-400">{a.username}</div></td>
                    <td>{a.role_label}</td>
                    <td className="text-sm">{a.role === "ME_DISTRICT" ? a.districts.join(", ") || "—" : a.regions.join(", ") || "—"}</td>
                    <td>{a.phone ?? "—"}</td>
                    <td className="text-sm">{a.last_login_at ? fmtDate(a.last_login_at.slice(0, 10)) : <span className="text-amber-700">never</span>}{a.must_change_password && <div className="text-xs text-amber-700">temporary password</div>}</td>
                    <td className="text-right">{a.reports}</td>
                    <td><span className={clsx("rounded-full px-2 py-0.5 text-xs font-semibold", a.active ? "bg-green-100 text-green-800" : "bg-slate-200 text-slate-700")}>{a.active ? "Active" : "Deactivated"}</span></td>
                    <td className="whitespace-nowrap text-right text-sm">
                      {a.role === "ME_DISTRICT" && <button className="mr-2 text-navy" onClick={() => { setEdit(a); setEditDistricts(a.district_ids); }}>Districts</button>}
                      <button className="mr-2 text-navy" onClick={() => { if (confirm(`Give ${a.full_name} a new temporary password?`)) reset.mutate(a); }}><KeyRound size={14} className="mr-0.5 inline" />Reset password</button>
                      <button className={a.active ? "text-red-700" : "text-green-700"} onClick={() => toggle.mutate(a)}>{a.active ? <><UserX size={14} className="mr-0.5 inline" />Deactivate</> : <><UserCheck size={14} className="mr-0.5 inline" />Activate</>}</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {form && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 p-4" onClick={() => setForm(null)}>
          <form className="w-full max-w-lg rounded-lg bg-white p-5 shadow-xl" onClick={(e) => e.stopPropagation()} onSubmit={(e) => { e.preventDefault(); create.mutate(form); }}>
            <h2 className="mb-3 text-lg font-semibold">New field officer</h2>
            <div className="grid gap-3">
              <Field label="Role">
                <div className="grid grid-cols-2 gap-2">
                  {([["ME_DISTRICT", "District M&E Officer"], ["ME_REGIONAL", "Regional M&E Officer"]] as const).map(([v, l]) => <button type="button" key={v} onClick={() => setForm({ ...form, role: v })} className={clsx("rounded-md border px-3 py-2 text-sm font-medium", form.role === v ? "border-navy bg-navy text-white" : "border-slate-300 bg-white text-slate-700")}>{l}</button>)}
                </div>
              </Field>
              <Field label="Full name"><input className="input" required minLength={2} value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Username"><input className="input" required minLength={3} value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} placeholder="e.g. me.bo.hawa" /></Field>
                <Field label="Phone"><input className="input" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></Field>
              </div>
              {form.role === "ME_DISTRICT" ? (
                <Field label="District(s) · tap to select">
                  <div className="grid max-h-56 grid-cols-2 gap-1 overflow-auto rounded-md border border-slate-200 p-2 sm:grid-cols-3">
                    {districts.map((d) => { const on = form.district_ids.includes(d.id); return <button type="button" key={d.id} onClick={() => setForm({ ...form, district_ids: on ? form.district_ids.filter((x) => x !== d.id) : [...form.district_ids, d.id] })} className={clsx("rounded-md border px-2 py-1.5 text-left text-sm", on ? "border-navy bg-navy text-white" : "border-slate-200 bg-white text-slate-700")}>{d.name}<span className={clsx("block text-[11px]", on ? "text-sky-100" : "text-slate-400")}>{d.region}</span></button>; })}
                  </div>
                </Field>
              ) : (
                <Field label="Region"><select className="input" required value={form.region_ids[0] ?? ""} onChange={(e) => setForm({ ...form, region_ids: e.target.value ? [Number(e.target.value)] : [] })}><option value="">Choose…</option>{regions.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}</select></Field>
              )}
              <p className="text-xs text-slate-500">A temporary password is generated and shown once after saving.</p>
            </div>
            <ErrorBox error={error instanceof ApiError ? error.message : error} />
            <div className="mt-4 flex justify-end gap-2">
              <button type="button" className="btn-outline" onClick={() => setForm(null)}>Cancel</button>
              <button className="btn-primary" disabled={create.isPending || (form.role === "ME_DISTRICT" && form.district_ids.length === 0)}>{create.isPending ? "Creating…" : "Create account"}</button>
            </div>
          </form>
        </div>
      )}
      {edit && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 p-4" onClick={() => setEdit(null)}>
          <div className="w-full max-w-lg rounded-lg bg-white p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h2 className="mb-3 text-lg font-semibold">Districts of {edit.full_name}</h2>
            <div className="grid max-h-64 grid-cols-2 gap-1 overflow-auto rounded-md border border-slate-200 p-2 sm:grid-cols-3">
              {districts.map((d) => { const on = editDistricts.includes(d.id); return <button type="button" key={d.id} onClick={() => setEditDistricts(on ? editDistricts.filter((x) => x !== d.id) : [...editDistricts, d.id])} className={clsx("rounded-md border px-2 py-1.5 text-left text-sm", on ? "border-navy bg-navy text-white" : "border-slate-200 bg-white text-slate-700")}>{d.name}</button>; })}
            </div>
            <div className="mt-4 flex justify-end gap-2"><button className="btn-outline" onClick={() => setEdit(null)}>Cancel</button><button className="btn-primary" disabled={editDistricts.length === 0 || saveDistricts.isPending} onClick={() => saveDistricts.mutate(edit)}>Save</button></div>
          </div>
        </div>
      )}
    </div>
  );
}
