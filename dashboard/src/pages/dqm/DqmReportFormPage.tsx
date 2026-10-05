import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError, api, download, fmt } from "../../api/client";
import type { District, DqmOptions, DqmReport, DqmReportIn, ErrorProfileRow, LessonRow, SaPerformanceRow, SystemIssueRow } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { Card, ErrorBox, Field, Spinner } from "../../components/ui";
import { StatusPill } from "./DqmReportsPage";

const today = () => new Date().toISOString().slice(0, 10);

const emptyForm = (): DqmReportIn => ({
  district_id: null, report_date: today(), period: "ENUMERATION", day_number: 1,
  teams_reviewed: null, teams_certified: null, teams_pending: null, executive_summary: "",
  reinterviews_received: null, reinterviews_received_pending: null, reinterviews_received_remarks: "",
  reinterviews_certified: null, reinterviews_certified_pending: null, reinterviews_certified_remarks: "",
  error_profile: [], system_issues: [], lessons: [], sa_performance: [], prepared_name: null,
});

const BAND_GUIDANCE: Record<string, string> = {
  LOW: "No further action needed; such enumerators and supervisors can be earmarked to support lagging or difficult areas.",
  MEDIUM: "DCO/DQM must speak with both enumerator and supervisor to find where the problem lies and coach them, sitting in on their next interviews if needed.",
  HIGH: "DCO/DQM must investigate thoroughly and, if coaching cannot bring improvement, recommend replacing the enumerator, the supervisor, or both.",
};

function num(v: string): number | null { return v === "" ? null : Number(v); }

export default function DqmReportFormPage() {
  const { id } = useParams();
  const isNew = id === "new";
  const nav = useNavigate();
  const qc = useQueryClient();
  const { user } = useAuth();
  const options = useQuery({ queryKey: ["dqm-options"], queryFn: () => api.get<DqmOptions>("/dqm-reports/options") });
  const districts = useQuery({ queryKey: ["ref", "districts"], queryFn: () => api.get<District[]>("/admin/reference/districts"), staleTime: 300_000 });
  const existing = useQuery({ queryKey: ["dqm-report", id], queryFn: () => api.get<DqmReport>(`/dqm-reports/${id}`), enabled: !isNew });
  const [form, setForm] = useState<DqmReportIn>(emptyForm());
  const [error, setError] = useState<unknown>(null);
  const [comment, setComment] = useState("");

  useEffect(() => {
    if (existing.data) {
      const { id: _i, district, region_id: _r, region: _g, status: _s, prepared_by: _p, submitted_at: _sa, received_by: _rb, received_name: _rn, received_at: _ra, receiver_comment: _rc, created_at: _c, updated_at: _u, ...rest } = existing.data;
      void _i; void district; void _r; void _g; void _s; void _p; void _sa; void _rb; void _rn; void _ra; void _rc; void _c; void _u;
      setForm(rest);
    }
  }, [existing.data]);
  useEffect(() => {
    if (isNew && user?.role === "DISTRICT_DQM" && user.district_ids?.length === 1) setForm((f) => ({ ...f, district_id: user.district_ids![0] }));
  }, [isNew, user]);

  const report = existing.data;
  const deleted = !!report?.deleted_at;
  const locked = report?.status === "RECEIVED" || deleted;
  const editable = (isNew ? !!options.data?.can_create : !!options.data?.can_edit) && !locked;
  const canSubmit = !!options.data?.can_submit;
  const canReceive = !!options.data?.can_receive && report?.status === "SUBMITTED";
  const [reason, setReason] = useState("");
  const del = useMutation({ mutationFn: () => api.delete<DqmReport>(`/dqm-reports/${id}`, { reason }), onSuccess: () => { qc.invalidateQueries({ queryKey: ["dqm-reports"] }); qc.invalidateQueries({ queryKey: ["dqm-report", id] }); setReason(""); setError(null); }, onError: setError });
  const restore = useMutation({ mutationFn: () => api.post<DqmReport>(`/dqm-reports/${id}/restore`), onSuccess: () => { qc.invalidateQueries({ queryKey: ["dqm-reports"] }); qc.invalidateQueries({ queryKey: ["dqm-report", id] }); setError(null); }, onError: setError });

  const save = useMutation({
    mutationFn: async (submitAfter: boolean) => {
      const body = { ...form, executive_summary: form.executive_summary || null };
      const saved = isNew ? await api.post<DqmReport>("/dqm-reports", body) : await api.put<DqmReport>(`/dqm-reports/${id}`, body);
      if (submitAfter) return api.post<DqmReport>(`/dqm-reports/${saved.id}/submit`);
      return saved;
    },
    onSuccess: (saved) => { qc.invalidateQueries({ queryKey: ["dqm-reports"] }); qc.invalidateQueries({ queryKey: ["dqm-report", String(saved.id)] }); setError(null); if (isNew) nav(`/dqm/reports/${saved.id}`, { replace: true }); },
    onError: setError,
  });
  const receive = useMutation({
    mutationFn: () => api.post<DqmReport>(`/dqm-reports/${id}/receive`, { comment: comment || null }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["dqm-reports"] }); qc.invalidateQueries({ queryKey: ["dqm-report", id] }); },
    onError: setError,
  });

  if (!isNew && existing.isLoading) return <Spinner />;
  if (!isNew && existing.error) return <ErrorBox error={existing.error} />;

  const upd = (patch: Partial<DqmReportIn>) => setForm((f) => ({ ...f, ...patch }));
  const rowsOf = <K extends "error_profile" | "system_issues" | "lessons" | "sa_performance">(key: K) => form[key] as DqmReportIn[K];
  const setRow = <K extends "error_profile" | "system_issues" | "lessons" | "sa_performance">(key: K, i: number, patch: Partial<DqmReportIn[K][number]>) =>
    upd({ [key]: (form[key] as unknown[]).map((r, j) => (j === i ? { ...(r as object), ...patch } : r)) } as Partial<DqmReportIn>);
  const addRow = <K extends "error_profile" | "system_issues" | "lessons" | "sa_performance">(key: K, row: DqmReportIn[K][number]) => upd({ [key]: [...(form[key] as unknown[]), row] } as Partial<DqmReportIn>);
  const delRow = (key: keyof DqmReportIn, i: number) => upd({ [key]: (form[key] as unknown[]).filter((_, j) => j !== i) } as Partial<DqmReportIn>);
  const ro = !editable;
  const errText = error instanceof Error ? error.message : typeof error === "string" ? error : "";
  const existingId = errText.match(/already exists \(id (\d+)\)/)?.[1];
  const cell = "input px-2 py-1";

  return (
    <div className="max-w-6xl">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link to="/dqm/reports" className="text-sm text-navy">← DQM reports</Link>
          <h1 className="text-2xl font-bold">{isNew ? "New daily report" : `${report?.district} · ${report?.report_date}`} {report && <StatusPill status={report.status} />}</h1>
          <p className="text-sm text-slate-500">2026 SLPHC Data Quality Management Daily Reporting Tool. Submitted to the National Data Quality Manager (NDQM).</p>
        </div>
        {!isNew && (
          <div className="flex gap-2">
            <button className="btn-outline" onClick={() => download(`/dqm-reports/${id}/export?format=pdf`, "report.pdf")}>PDF</button>
            <button className="btn-outline" onClick={() => download(`/dqm-reports/${id}/export?format=xlsx`, "report.xlsx")}>Excel</button>
          </div>
        )}
      </div>
      <p className="mb-4 rounded-md border border-slate-200 bg-white p-3 text-sm text-slate-600">
        <strong>Completion standard.</strong> Enter a response in every applicable field. If an item does not apply, write "Not applicable". If evidence is pending, state the source, responsible person and expected completion date.
      </p>
      <ErrorBox error={error instanceof ApiError ? error.message : error} />
      {existingId && (
        <div className="mb-4 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          Each DQM officer sends one report per district per day, and you already have one for this day.{" "}
          <button className="font-semibold underline" onClick={() => nav(`/dqm/reports/${existingId}`)}>Open the existing report</button>{" "}
          to read it or continue it. If it has already been submitted and something must change, ask the National DQM to delete it with a reason so a new one can be entered.
        </div>
      )}
      {deleted && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          <span><strong>Deleted</strong> {fmt(report!.deleted_at)}: {report!.delete_reason}. Excluded from summaries and analytics.</span>
          {options.data?.can_delete && <button className="btn-outline" disabled={restore.isPending} onClick={() => restore.mutate()}>Restore</button>}
        </div>
      )}

      <Card title="Report header" className="mb-4">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Field label="District">
            <select className="input" disabled={ro || (user?.role === "DISTRICT_DQM" && (user.district_ids?.length ?? 0) <= 1) || !isNew} value={form.district_id ?? ""} onChange={(e) => upd({ district_id: e.target.value ? Number(e.target.value) : null })}>
              <option value="">Select…</option>
              {districts.data?.filter((d) => !user?.district_ids || user.district_ids.includes(d.id)).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          </Field>
          <Field label="Report date"><input type="date" className="input" disabled={ro} value={form.report_date} onChange={(e) => upd({ report_date: e.target.value })} /></Field>
          <Field label="Period">
            <select className="input" disabled={ro} value={form.period} onChange={(e) => upd({ period: e.target.value as DqmReportIn["period"] })}>
              <option value="LISTING">Listing</option>
              <option value="ENUMERATION">Enumeration</option>
            </select>
          </Field>
          <Field label="Day number"><input type="number" min={1} className="input" disabled={ro} value={form.day_number} onChange={(e) => upd({ day_number: Number(e.target.value) || 1 })} /></Field>
        </div>
      </Card>

      <Card title="1. Executive data-quality summary (cumulative)" className="mb-4">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
          <Field label="Number of SAs reviewed"><input type="number" min={0} className="input" disabled={ro} value={form.teams_reviewed ?? ""} onChange={(e) => upd({ teams_reviewed: num(e.target.value) })} /></Field>
          <Field label="Number of SAs certified"><input type="number" min={0} className="input" disabled={ro} value={form.teams_certified ?? ""} onChange={(e) => upd({ teams_certified: num(e.target.value) })} /></Field>
          <Field label="Pending SAs"><input type="number" min={0} className="input" disabled={ro} value={form.teams_pending ?? ""} onChange={(e) => upd({ teams_pending: num(e.target.value) })} /></Field>
          <div className="col-span-2"><Field label="Cumulative assessment / summary"><textarea className="input" rows={2} disabled={ro} value={form.executive_summary ?? ""} onChange={(e) => upd({ executive_summary: e.target.value })} /></Field></div>
        </div>
      </Card>

      <Card title="2. Re-interview and certification" className="mb-4">
        <table className="table">
          <thead><tr><th>Indicator</th><th className="w-32">Final total</th><th className="w-32">Pending</th><th>Affected EAs / remarks</th></tr></thead>
          <tbody>
            <tr>
              <td>Reinterviews received for review</td>
              <td><input type="number" min={0} className={cell} disabled={ro} value={form.reinterviews_received ?? ""} onChange={(e) => upd({ reinterviews_received: num(e.target.value) })} /></td>
              <td><input type="number" min={0} className={cell} disabled={ro} value={form.reinterviews_received_pending ?? ""} onChange={(e) => upd({ reinterviews_received_pending: num(e.target.value) })} /></td>
              <td><input className={cell} disabled={ro} value={form.reinterviews_received_remarks ?? ""} onChange={(e) => upd({ reinterviews_received_remarks: e.target.value })} /></td>
            </tr>
            <tr>
              <td>Reinterviews certified</td>
              <td><input type="number" min={0} className={cell} disabled={ro} value={form.reinterviews_certified ?? ""} onChange={(e) => upd({ reinterviews_certified: num(e.target.value) })} /></td>
              <td><input type="number" min={0} className={cell} disabled={ro} value={form.reinterviews_certified_pending ?? ""} onChange={(e) => upd({ reinterviews_certified_pending: num(e.target.value) })} /></td>
              <td><input className={cell} disabled={ro} value={form.reinterviews_certified_remarks ?? ""} onChange={(e) => upd({ reinterviews_certified_remarks: e.target.value })} /></td>
            </tr>
          </tbody>
        </table>
      </Card>

      <Card title="3. Error and disparity profile" className="mb-4" action={editable && <button className="btn-outline" onClick={() => addRow("error_profile", { band: "LOW", ea_code: "", team: "", likely_cause: "", correction: "", remarks: "" } as ErrorProfileRow)}>Add row</button>}>
        <table className="table">
          <thead><tr><th className="w-64">Error category</th><th>EA code</th><th>Team #</th><th>Likely cause</th><th>Correction / verification</th><th>Remarks</th>{editable && <th />}</tr></thead>
          <tbody>
            {rowsOf("error_profile").map((r, i) => (
              <tr key={i}>
                <td>
                  <select className={cell} disabled={ro} value={r.band} onChange={(e) => setRow("error_profile", i, { band: e.target.value as ErrorProfileRow["band"] })}>
                    {Object.entries(options.data?.error_bands ?? {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </select>
                  <div className="mt-1 text-xs text-slate-500">{BAND_GUIDANCE[r.band]}</div>
                </td>
                <td><input className={cell} disabled={ro} value={r.ea_code} onChange={(e) => setRow("error_profile", i, { ea_code: e.target.value })} /></td>
                <td><input className={cell} disabled={ro} value={r.team} onChange={(e) => setRow("error_profile", i, { team: e.target.value })} /></td>
                <td><input className={cell} disabled={ro} value={r.likely_cause} onChange={(e) => setRow("error_profile", i, { likely_cause: e.target.value })} /></td>
                <td><input className={cell} disabled={ro} value={r.correction} onChange={(e) => setRow("error_profile", i, { correction: e.target.value })} /></td>
                <td><input className={cell} disabled={ro} value={r.remarks} onChange={(e) => setRow("error_profile", i, { remarks: e.target.value })} /></td>
                {editable && <td><button className="text-xs text-red-700" onClick={() => delRow("error_profile", i)}>Remove</button></td>}
              </tr>
            ))}
            {rowsOf("error_profile").length === 0 && <tr><td colSpan={7} className="text-slate-400">No rows. Add one per error found, or leave empty if not applicable.</td></tr>}
          </tbody>
        </table>
      </Card>

      <Card title="4. GIS, CAPI and synchronisation issues" className="mb-4" action={editable && <button className="btn-outline" onClick={() => addRow("system_issues", { issue_type: "OUTLIER", ea_code: "", finding: "", referred_to: "", action_taken: "", resolution_status: "OPEN" } as SystemIssueRow)}>Add row</button>}>
        <table className="table">
          <thead><tr><th className="w-56">Issue type</th><th>EA code</th><th>Finding</th><th>Referred to</th><th>Action taken</th><th className="w-36">Resolution status</th>{editable && <th />}</tr></thead>
          <tbody>
            {rowsOf("system_issues").map((r, i) => (
              <tr key={i}>
                <td><select className={cell} disabled={ro} value={r.issue_type} onChange={(e) => setRow("system_issues", i, { issue_type: e.target.value as SystemIssueRow["issue_type"] })}>{Object.entries(options.data?.issue_types ?? {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></td>
                <td><input className={cell} disabled={ro} value={r.ea_code} onChange={(e) => setRow("system_issues", i, { ea_code: e.target.value })} /></td>
                <td><input className={cell} disabled={ro} value={r.finding} onChange={(e) => setRow("system_issues", i, { finding: e.target.value })} /></td>
                <td><input className={cell} disabled={ro} value={r.referred_to} onChange={(e) => setRow("system_issues", i, { referred_to: e.target.value })} /></td>
                <td><input className={cell} disabled={ro} value={r.action_taken} onChange={(e) => setRow("system_issues", i, { action_taken: e.target.value })} /></td>
                <td><select className={cell} disabled={ro} value={r.resolution_status} onChange={(e) => setRow("system_issues", i, { resolution_status: e.target.value as SystemIssueRow["resolution_status"] })}><option value="OPEN">Open</option><option value="IN_PROGRESS">In progress</option><option value="RESOLVED">Resolved</option></select></td>
                {editable && <td><button className="text-xs text-red-700" onClick={() => delRow("system_issues", i)}>Remove</button></td>}
              </tr>
            ))}
            {rowsOf("system_issues").length === 0 && <tr><td colSpan={7} className="text-slate-400">No rows.</td></tr>}
          </tbody>
        </table>
      </Card>

      <Card title="5. Lessons and recommendations" className="mb-4" action={editable && <button className="btn-outline" onClick={() => addRow("lessons", { quality_area: "GPS", lesson: "", risk: "", control: "" } as LessonRow)}>Add row</button>}>
        <table className="table">
          <thead><tr><th className="w-56">Quality area</th><th>Lesson / evidence</th><th>Risk for enumeration</th><th>Recommended control</th>{editable && <th />}</tr></thead>
          <tbody>
            {rowsOf("lessons").map((r, i) => (
              <tr key={i}>
                <td><select className={cell} disabled={ro} value={r.quality_area} onChange={(e) => setRow("lessons", i, { quality_area: e.target.value as LessonRow["quality_area"] })}>{Object.entries(options.data?.quality_areas ?? {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></td>
                <td><input className={cell} disabled={ro} value={r.lesson} onChange={(e) => setRow("lessons", i, { lesson: e.target.value })} /></td>
                <td><input className={cell} disabled={ro} value={r.risk} onChange={(e) => setRow("lessons", i, { risk: e.target.value })} /></td>
                <td><input className={cell} disabled={ro} value={r.control} onChange={(e) => setRow("lessons", i, { control: e.target.value })} /></td>
                {editable && <td><button className="text-xs text-red-700" onClick={() => delRow("lessons", i)}>Remove</button></td>}
              </tr>
            ))}
            {rowsOf("lessons").length === 0 && <tr><td colSpan={5} className="text-slate-400">No rows.</td></tr>}
          </tbody>
        </table>
      </Card>

      <Card title="6. Overall assessment: daily performance by SA" className="mb-4" action={editable && <button className="btn-outline" onClick={() => addRow("sa_performance", { sa: "", assessment: "" } as SaPerformanceRow)}>Add row</button>}>
        <table className="table">
          <thead><tr><th className="w-12">#</th><th className="w-56">SA</th><th>Daily performance</th>{editable && <th />}</tr></thead>
          <tbody>
            {rowsOf("sa_performance").map((r, i) => (
              <tr key={i}>
                <td>{i + 1}</td>
                <td><input className={cell} disabled={ro} value={r.sa} onChange={(e) => setRow("sa_performance", i, { sa: e.target.value })} /></td>
                <td><input className={cell} disabled={ro} value={r.assessment} onChange={(e) => setRow("sa_performance", i, { assessment: e.target.value })} /></td>
                {editable && <td><button className="text-xs text-red-700" onClick={() => delRow("sa_performance", i)}>Remove</button></td>}
              </tr>
            ))}
            {rowsOf("sa_performance").length === 0 && <tr><td colSpan={4} className="text-slate-400">No rows.</td></tr>}
          </tbody>
        </table>
      </Card>

      <Card title="Certification and submission" className="mb-4">
        <p className="mb-3 text-sm">I certify that this report accurately presents the outcome of the Enumeration Exercise within my assigned area.</p>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <Field label="Prepared by"><input className="input" disabled={ro} value={form.prepared_name ?? user?.full_name ?? ""} onChange={(e) => upd({ prepared_name: e.target.value })} /></Field>
          <div className="text-sm">
            <div><span className="text-slate-500">Submitted:</span> {report?.submitted_at ? fmt(report.submitted_at) : "not yet"}</div>
            <div><span className="text-slate-500">Received by:</span> {report?.received_name ? `${report.received_name}, ${fmt(report.received_at)}` : "not yet"}</div>
            {report?.receiver_comment && <div><span className="text-slate-500">Comment:</span> {report.receiver_comment}</div>}
          </div>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-2">
          {editable && <button className="btn-outline" disabled={save.isPending} onClick={() => save.mutate(false)}>{isNew ? "Save draft" : "Save"}</button>}
          {editable && canSubmit && <button className="btn-primary" disabled={save.isPending} onClick={() => { if (confirm("Submit this report to the National Data Quality Manager?")) save.mutate(true); }}>{report?.status === "SUBMITTED" ? "Save and re-submit" : "Submit to NDQM"}</button>}
          {canReceive && (
            <>
              <input className="input md:w-80" placeholder="Comment (optional)" value={comment} onChange={(e) => setComment(e.target.value)} />
              <button className="btn-primary" disabled={receive.isPending} onClick={() => receive.mutate()}>Mark as received</button>
            </>
          )}
          {report?.status === "RECEIVED" && <span className="text-sm text-green-700">Received by National DQM; this report is now read-only.</span>}
          {!editable && !canReceive && !locked && <span className="text-sm text-slate-500">Read-only view.</span>}
        </div>
      </Card>
      {!isNew && options.data?.can_delete && !deleted && (
        <Card title="Delete this report" className="mb-4">
          <p className="mb-2 text-sm text-slate-600">The report is hidden from lists, summaries and analytics but kept for the audit trail and can be restored. A new report for the same district and day can then be entered.</p>
          <div className="flex flex-wrap gap-2">
            <input className="input md:w-96" placeholder="Reason (required)" value={reason} onChange={(e) => setReason(e.target.value)} />
            <button className="btn-outline text-red-700" disabled={!reason.trim() || del.isPending} onClick={() => { if (confirm("Delete this daily report?")) del.mutate(); }}>Delete</button>
          </div>
        </Card>
      )}
    </div>
  );
}
