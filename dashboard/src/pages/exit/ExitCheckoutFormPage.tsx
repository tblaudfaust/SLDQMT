import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import clsx from "clsx";
import { ApiError, api, download, fmt, fmtDate } from "../../api/client";
import type { ApprovalRow, Checkout, CheckoutIn, ChecklistRow, ClearanceDecision, District, ExitOptions, ItemRow, Team } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { Card, ErrorBox, Field, Spinner } from "../../components/ui";
import { CheckoutStatusPill } from "./ExitCheckoutsPage";

const emptyForm = (): CheckoutIn => ({ district_id: null, team_id: null, staff_name: "", login_id: "", role: "ENUMERATOR", sa_ea_codes: "", checklist: [], enumerator_conduct: "", items: [], supervisor_conduct: "", approvals: [] });

export default function ExitCheckoutFormPage() {
  const { id } = useParams();
  const isNew = id === "new";
  const nav = useNavigate();
  const qc = useQueryClient();
  const { user } = useAuth();
  const options = useQuery({ queryKey: ["exit-options"], queryFn: () => api.get<ExitOptions>("/exit-checkouts/options") });
  const districts = useQuery({ queryKey: ["ref", "districts"], queryFn: () => api.get<District[]>("/admin/reference/districts"), staleTime: 300_000 });
  const existing = useQuery({ queryKey: ["exit-checkout", id], queryFn: () => api.get<Checkout>(`/exit-checkouts/${id}`), enabled: !isNew });
  const [form, setForm] = useState<CheckoutIn>(emptyForm());
  const teams = useQuery({ queryKey: ["ref", "teams", form.district_id], queryFn: () => api.get<Team[]>(`/admin/reference/teams?district_id=${form.district_id}`), enabled: !!form.district_id, staleTime: 300_000 });
  const [error, setError] = useState<unknown>(null);
  const [comment, setComment] = useState("");
  const [decision, setDecision] = useState<ClearanceDecision | "">("");
  const [issues, setIssues] = useState("");
  const [deadline, setDeadline] = useState("");
  const [decidedName, setDecidedName] = useState("Director, Data Science Division");

  useEffect(() => {
    if (existing.data) {
      const e = existing.data;
      setForm({ district_id: e.district_id, team_id: e.team_id, staff_name: e.staff_name, login_id: e.login_id, role: e.role, sa_ea_codes: e.sa_ea_codes, checklist: e.checklist, enumerator_conduct: e.enumerator_conduct, items: e.items, supervisor_conduct: e.supervisor_conduct, approvals: e.approvals });
    }
  }, [existing.data]);
  useEffect(() => {
    if (isNew && user?.role === "DISTRICT_DQM" && user.district_ids?.length === 1) setForm((f) => ({ ...f, district_id: user.district_ids![0] }));
  }, [isNew, user]);

  const c = existing.data;
  const opts = options.data;
  const deleted = !!c?.deleted_at;
  const editable = (isNew ? !!opts?.can_create : !!opts?.can_edit) && !deleted && c?.status !== "CLEARED" && !(c?.status === "NATIONAL_SIGNED" && !opts?.can_sign);
  const ro = !editable;
  const canSubmit = editable && !!opts?.can_submit && (isNew || c?.status === "DRAFT");
  const canSign = !!opts?.can_sign && !deleted && c?.status === "SUBMITTED";
  const canClear = !!opts?.can_clear && !deleted && (c?.status === "SUBMITTED" || c?.status === "NATIONAL_SIGNED");
  const [reason, setReason] = useState("");
  const del = useMutation({ mutationFn: () => api.delete<Checkout>(`/exit-checkouts/${id}`, { reason }), onSuccess: () => { qc.invalidateQueries({ queryKey: ["exit-checkouts"] }); qc.invalidateQueries({ queryKey: ["exit-checkout", id] }); setReason(""); setError(null); }, onError: setError });
  const restore = useMutation({ mutationFn: () => api.post<Checkout>(`/exit-checkouts/${id}/restore`), onSuccess: () => { qc.invalidateQueries({ queryKey: ["exit-checkouts"] }); qc.invalidateQueries({ queryKey: ["exit-checkout", id] }); setError(null); }, onError: setError });

  const save = useMutation({
    mutationFn: async (submitAfter: boolean) => {
      const body = { ...form, login_id: form.login_id || null, sa_ea_codes: form.sa_ea_codes || null, enumerator_conduct: form.enumerator_conduct || null, supervisor_conduct: form.supervisor_conduct || null };
      const saved = isNew ? await api.post<Checkout>("/exit-checkouts", body) : await api.put<Checkout>(`/exit-checkouts/${id}`, body);
      return submitAfter ? api.post<Checkout>(`/exit-checkouts/${saved.id}/submit`) : saved;
    },
    onSuccess: (saved) => { qc.invalidateQueries({ queryKey: ["exit-checkouts"] }); qc.invalidateQueries({ queryKey: ["exit-checkout", String(saved.id)] }); setError(null); if (isNew) nav(`/dqm/exit/${saved.id}`, { replace: true }); },
    onError: setError,
  });
  const sign = useMutation({ mutationFn: () => api.post<Checkout>(`/exit-checkouts/${id}/national-sign`, { comment: comment || null }), onSuccess: () => { qc.invalidateQueries({ queryKey: ["exit-checkouts"] }); qc.invalidateQueries({ queryKey: ["exit-checkout", id] }); setError(null); }, onError: setError });
  const clear = useMutation({ mutationFn: () => api.post<Checkout>(`/exit-checkouts/${id}/clearance`, { decision, outstanding_issues: issues || null, deadline: deadline || null, decided_name: decidedName || null }), onSuccess: () => { qc.invalidateQueries({ queryKey: ["exit-checkouts"] }); qc.invalidateQueries({ queryKey: ["exit-checkout", id] }); setError(null); }, onError: setError });

  if (!isNew && existing.isLoading) return <Spinner />;
  if (!isNew && existing.error) return <ErrorBox error={existing.error} />;
  if (!opts) return <Spinner />;

  const upd = (patch: Partial<CheckoutIn>) => setForm((f) => ({ ...f, ...patch }));
  const check = (n: number): ChecklistRow => form.checklist.find((r) => r.n === n) ?? { n, answer: null, remarks: "" };
  const setCheck = (n: number, patch: Partial<ChecklistRow>) => upd({ checklist: [...form.checklist.filter((r) => r.n !== n), { ...check(n), ...patch }].sort((a, b) => a.n - b.n) });
  const item = (code: string): ItemRow => form.items.find((r) => r.item === code) ?? { item: code, returned: null, condition: "", clearance: "" };
  const setItem = (code: string, patch: Partial<ItemRow>) => upd({ items: [...form.items.filter((r) => r.item !== code), { ...item(code), ...patch }] });
  const approval = (role: string): ApprovalRow => form.approvals.find((r) => r.role === role) ?? { role, name: "", comment: "", signed_on: null };
  const setApproval = (role: string, patch: Partial<ApprovalRow>) => upd({ approvals: [...form.approvals.filter((r) => r.role !== role), { ...approval(role), ...patch }] });
  const cell = "input px-2 py-1";
  const yesNo = (value: boolean | null | "YES" | "NO", onChange: (v: "YES" | "NO") => void, disabled: boolean) => (
    <div className="flex gap-1">
      {(["YES", "NO"] as const).map((v) => (
        <button key={v} type="button" disabled={disabled} onClick={() => onChange(v)} className={clsx("rounded px-2 py-0.5 text-xs font-semibold border", (value === v || (v === "YES" && value === true) || (v === "NO" && value === false)) ? (v === "YES" ? "bg-green-600 text-white border-green-600" : "bg-red-600 text-white border-red-600") : "bg-white text-slate-600 border-slate-300")}>{v === "YES" ? "Yes" : "No"}</button>
      ))}
    </div>
  );

  return (
    <div className="max-w-6xl">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link to="/dqm/exit" className="text-sm text-navy">← Field exit protocol</Link>
          <h1 className="text-2xl font-bold">{isNew ? "New check-out" : `${c?.staff_name} · ${c?.role === "SUPERVISOR" ? "Supervisor" : "Enumerator"} · ${c?.district}`} {c && <CheckoutStatusPill status={c.status} decision={c.decision} />}</h1>
          <p className="text-sm text-slate-500">Data Quality Manager check-out form for supervisors and enumerators.</p>
        </div>
        {!isNew && <div className="flex gap-2"><button className="btn-outline" onClick={() => download(`/exit-checkouts/${id}/export?format=pdf`, "checkout.pdf")}>PDF</button><button className="btn-outline" onClick={() => download(`/exit-checkouts/${id}/export?format=xlsx`, "checkout.xlsx")}>Excel</button></div>}
      </div>
      <ErrorBox error={error instanceof ApiError ? error.message : error} />
      {deleted && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          <span><strong>Deleted</strong> {fmt(c!.deleted_at)}: {c!.delete_reason}. Excluded from the summaries.</span>
          {opts.can_delete && <button className="btn-outline" disabled={restore.isPending} onClick={() => restore.mutate()}>Restore</button>}
        </div>
      )}

      <Card title="A. Field staff details" className="mb-4">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Field label="Name of field staff"><input className="input" disabled={ro} value={form.staff_name} onChange={(e) => upd({ staff_name: e.target.value })} /></Field>
          <Field label="Login ID"><input className="input" disabled={ro} value={form.login_id ?? ""} onChange={(e) => upd({ login_id: e.target.value })} /></Field>
          <Field label="Role"><select className="input" disabled={ro} value={form.role} onChange={(e) => upd({ role: e.target.value as CheckoutIn["role"] })}><option value="ENUMERATOR">Enumerator</option><option value="SUPERVISOR">Supervisor</option></select></Field>
          <Field label="District">
            <select className="input" disabled={ro || !isNew || (user?.role === "DISTRICT_DQM" && (user.district_ids?.length ?? 0) <= 1)} value={form.district_id ?? ""} onChange={(e) => upd({ district_id: e.target.value ? Number(e.target.value) : null, team_id: null })}>
              <option value="">Select…</option>
              {districts.data?.filter((d) => !user?.district_ids || user.district_ids.includes(d.id)).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          </Field>
          <Field label="Team (supervisory area)">
            <select className="input" disabled={ro || !form.district_id} value={form.team_id ?? ""} onChange={(e) => upd({ team_id: e.target.value ? Number(e.target.value) : null })}>
              <option value="">Not specified</option>
              {teams.data?.map((t) => <option key={t.id} value={t.id}>{t.code} {t.name}</option>)}
            </select>
          </Field>
          <div className="md:col-span-3"><Field label="SA / EA code(s)"><input className="input" disabled={ro} value={form.sa_ea_codes ?? ""} onChange={(e) => upd({ sa_ea_codes: e.target.value })} /></Field></div>
        </div>
      </Card>

      <Card title="B. Workload completion and data validation" className="mb-4">
        <table className="table">
          <thead><tr><th className="w-8">#</th><th>Clearance requirement</th><th className="w-28">Yes / No</th><th>Remarks</th></tr></thead>
          <tbody>
            {opts.checklist.map(({ n, text }) => (
              <tr key={n}>
                <td>{n}</td><td>{text}</td>
                <td>{yesNo(check(n).answer, (v) => setCheck(n, { answer: v }), ro)}</td>
                <td><input className={cell} disabled={ro} value={check(n).remarks} onChange={(e) => setCheck(n, { remarks: e.target.value })} /></td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="mt-3"><Field label="Comment on the integrity, conduct and attitude of the enumerator"><textarea className="input" rows={2} disabled={ro} value={form.enumerator_conduct ?? ""} onChange={(e) => upd({ enumerator_conduct: e.target.value })} /></Field></div>
      </Card>

      <Card title="C. Supervisor final sync and retrieval of tablet and accessories" className="mb-4">
        <p className="mb-3 text-sm text-slate-600"><strong>Certification.</strong> The assigned workload has been completed in accordance with census methodology; all data-quality issues are resolved; final synchronisation is confirmed; and all census property has been returned.</p>
        <table className="table">
          <thead><tr><th>Item issued</th><th className="w-28">Returned</th><th>Condition / remarks</th><th>Final clearance status</th></tr></thead>
          <tbody>
            {opts.items.map(({ code, text }) => (
              <tr key={code}>
                <td>{text}</td>
                <td>{yesNo(item(code).returned, (v) => setItem(code, { returned: v === "YES" }), ro)}</td>
                <td><input className={cell} disabled={ro} value={item(code).condition} onChange={(e) => setItem(code, { condition: e.target.value })} /></td>
                <td><input className={cell} disabled={ro} value={item(code).clearance} onChange={(e) => setItem(code, { clearance: e.target.value })} /></td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="mt-3"><Field label="Comment on the integrity, conduct and attitude of the supervisor"><textarea className="input" rows={2} disabled={ro} value={form.supervisor_conduct ?? ""} onChange={(e) => upd({ supervisor_conduct: e.target.value })} /></Field></div>
      </Card>

      <Card title="Certification and approval" className="mb-4">
        <table className="table">
          <thead><tr><th>Role</th><th>Name</th><th>Comment</th><th className="w-40">Signed on</th></tr></thead>
          <tbody>
            {opts.approvals.map(({ role, text }) => {
              const inApp = role === "DISTRICT_DQM" || role === "NATIONAL_DQM";
              const a = approval(role);
              return (
                <tr key={role}>
                  <td>{text}{inApp && <div className="text-xs text-slate-400">signed in the system</div>}</td>
                  <td><input className={cell} disabled={ro || inApp} value={a.name} onChange={(e) => setApproval(role, { name: e.target.value })} /></td>
                  <td><input className={cell} disabled={ro || inApp} value={a.comment} onChange={(e) => setApproval(role, { comment: e.target.value })} /></td>
                  <td><input type="date" className={cell} disabled={ro || inApp} value={a.signed_on ?? ""} onChange={(e) => setApproval(role, { signed_on: e.target.value || null })} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {editable && <button className="btn-outline" disabled={save.isPending} onClick={() => save.mutate(false)}>{isNew ? "Save draft" : "Save"}</button>}
          {canSubmit && <button className="btn-primary" disabled={save.isPending} onClick={() => save.mutate(true)}>Save and certify (submit)</button>}
          {c?.submitted_at && <span className="text-sm text-slate-500">Certified by District DQM {fmt(c.submitted_at)}</span>}
          {c?.national_signed_at && <span className="text-sm text-slate-500">· Countersigned by {c.national_signed_name} {fmt(c.national_signed_at)}{c.national_comment ? ` (${c.national_comment})` : ""}</span>}
        </div>
        {canSign && (
          <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3">
            <input className="input md:w-80" placeholder="National DQM comment (optional)" value={comment} onChange={(e) => setComment(e.target.value)} />
            <button className="btn-primary" disabled={sign.isPending} onClick={() => sign.mutate()}>Countersign as National DQM</button>
          </div>
        )}
      </Card>

      <Card title="D. Clearance: decision and approval by Director, Data Science Division" className="mb-4">
        {c?.decision ? (
          <div className="text-sm">
            <div className="mb-1"><CheckoutStatusPill status="CLEARED" decision={c.decision} /> <span className="ml-2">{opts.decisions[c.decision]}</span></div>
            {c.outstanding_issues && <div><span className="text-slate-500">Outstanding issues or conditions:</span> {c.outstanding_issues}</div>}
            {c.deadline && <div><span className="text-slate-500">Deadline:</span> {fmtDate(c.deadline)}</div>}
            <div><span className="text-slate-500">Decided by:</span> {c.decided_name}, recorded {fmt(c.decided_at)}</div>
          </div>
        ) : canClear ? (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <Field label="Decision">
              <select className="input" value={decision} onChange={(e) => setDecision(e.target.value as ClearanceDecision)}>
                <option value="">Select…</option>
                {Object.entries(opts.decisions).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </Field>
            <Field label="Decided by"><input className="input" value={decidedName} onChange={(e) => setDecidedName(e.target.value)} /></Field>
            <Field label="Outstanding issues or conditions"><textarea className="input" rows={2} value={issues} onChange={(e) => setIssues(e.target.value)} /></Field>
            <Field label="Deadline for resolving outstanding issues"><input type="date" className="input" value={deadline} onChange={(e) => setDeadline(e.target.value)} /></Field>
            <div className="md:col-span-2"><button className="btn-primary" disabled={!decision || clear.isPending} onClick={() => clear.mutate()}>Record clearance decision</button></div>
          </div>
        ) : (
          <p className="text-sm text-slate-500">{c?.status === "DRAFT" || isNew ? "Recorded by National DQM after the district has certified the check-out." : "Awaiting the Director's decision, recorded by National DQM."}</p>
        )}
      </Card>
      {!isNew && opts.can_delete && !deleted && (
        <Card title="Delete this check-out" className="mb-4">
          <p className="mb-2 text-sm text-slate-600">The check-out is hidden from lists and summaries but kept for the audit trail and can be restored. The deletion and its reason are recorded in the audit log.</p>
          <div className="flex flex-wrap gap-2">
            <input className="input md:w-96" placeholder="Reason (required)" value={reason} onChange={(e) => setReason(e.target.value)} />
            <button className="btn-outline text-red-700" disabled={!reason.trim() || del.isPending} onClick={() => { if (confirm(`Delete the check-out for ${c?.staff_name}?`)) del.mutate(); }}>Delete</button>
          </div>
        </Card>
      )}
    </div>
  );
}
