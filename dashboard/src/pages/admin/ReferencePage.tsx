import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { api, fmt } from "../../api/client";
import type { District, FrameVersion, ImportResult, PickList, Team } from "../../api/types";
import { Card, ErrorBox, Field, Spinner } from "../../components/ui";

function PickListEditor({ kind, title }: { kind: "categories" | "sources"; title: string }) {
  const qc = useQueryClient();
  const list = useQuery({ queryKey: ["ref", kind], queryFn: () => api.get<PickList[]>(`/admin/reference/${kind}`) });
  const [editing, setEditing] = useState<Partial<PickList> | null>(null);
  const save = useMutation({
    mutationFn: (p: Partial<PickList>) => p.id ? api.put(`/admin/reference/${kind}/${p.id}`, p) : api.post(`/admin/reference/${kind}`, p),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["ref", kind] }); setEditing(null); },
  });
  const submit = (e: FormEvent) => { e.preventDefault(); if (editing) save.mutate({ active: true, sort_order: 0, ...editing }); };
  return (
    <Card title={title} action={<button className="btn-outline" onClick={() => setEditing({ active: true, sort_order: (list.data?.length ?? 0) + 1 })}>Add</button>}>
      {editing && (
        <form onSubmit={submit} className="mb-3 grid grid-cols-2 gap-2 md:grid-cols-5">
          <Field label="Code"><input className="input" required value={editing.code ?? ""} onChange={(e) => setEditing({ ...editing, code: e.target.value.toUpperCase() })} /></Field>
          <Field label="Name"><input className="input" required value={editing.name ?? ""} onChange={(e) => setEditing({ ...editing, name: e.target.value })} /></Field>
          <Field label="Order"><input className="input" type="number" value={editing.sort_order ?? 0} onChange={(e) => setEditing({ ...editing, sort_order: Number(e.target.value) })} /></Field>
          <Field label="Active"><select className="input" value={editing.active ? "1" : "0"} onChange={(e) => setEditing({ ...editing, active: e.target.value === "1" })}><option value="1">Yes</option><option value="0">No</option></select></Field>
          <div className="flex items-end gap-2"><button className="btn-primary">Save</button><button type="button" className="btn-outline" onClick={() => setEditing(null)}>Cancel</button></div>
          <div className="col-span-full"><ErrorBox error={save.error} /></div>
        </form>
      )}
      {list.isLoading ? <Spinner /> : (
        <table className="table">
          <thead><tr><th>Code</th><th>Name</th><th>Order</th><th>Active</th><th></th></tr></thead>
          <tbody>{list.data?.map((p) => <tr key={p.id}><td>{p.code}</td><td>{p.name}</td><td>{p.sort_order}</td><td>{p.active ? "Yes" : "No"}</td><td><button className="text-sm text-navy" onClick={() => setEditing(p)}>Edit</button></td></tr>)}</tbody>
        </table>
      )}
    </Card>
  );
}

type PracticeStatus = { loaded: boolean; dqm_accounts: number; fm_accounts: number; sas_assigned: number; logged_in: number; workbook: string | null };
type PracticeLoadOut = { sas_assigned: number; rows: number; warnings: string[]; accounts_created: number; accounts_updated: number; dqm_accounts: number; fm_accounts: number; unknown_districts: string[]; passwords_reset: boolean };
type PracticeRemoveOut = { accounts: number; devices: number; sas_cleared: number; accounts_kept_with_other_records: number };

function PracticeSet() {
  const qc = useQueryClient();
  const status = useQuery({ queryKey: ["ref", "practice"], queryFn: () => api.get<PracticeStatus>("/admin/reference/practice") });
  const [dqmPw, setDqmPw] = useState("");
  const [fmPw, setFmPw] = useState("");
  const [resetPw, setResetPw] = useState(false);
  const [out, setOut] = useState<PracticeLoadOut | null>(null);
  const [removed, setRemoved] = useState<PracticeRemoveOut | null>(null);
  const done = () => { qc.invalidateQueries({ queryKey: ["ref"] }); qc.invalidateQueries({ queryKey: ["users"] }); qc.invalidateQueries({ queryKey: ["mefm"] }); };
  const load = useMutation({
    mutationFn: () => api.post<PracticeLoadOut>("/admin/reference/practice", { dqm_password: dqmPw, fm_password: fmPw, reset_passwords: resetPw }),
    onSuccess: (r) => { setOut(r); setRemoved(null); done(); },
  });
  const remove = useMutation({
    mutationFn: () => api.delete<PracticeRemoveOut>("/admin/reference/practice"),
    onSuccess: (r) => { setRemoved(r); setOut(null); done(); },
  });
  const s = status.data;
  return (
    <Card title="ToT class practice set (DQM and Field Monitor practice accounts)">
      <p className="mb-3 text-sm text-slate-600">
        The practice workload shipped with the server ({s?.workbook ?? "tot_practice_workload.xlsx"}) gives every hall seat of the regional ToT its own
        officer code (<code>DQM-WAU-H1-01</code> with its pair <code>FM-WAU-H1-01</code>) and 6–8 SAs. Loading assigns those SAs and creates one account per code:
        username and staff code = the code, district scope from its SAs, the shared password of its role, no forced password change. Loading again is safe
        (existing practice accounts are kept; tick the box to set their passwords again). After the training, <b>Remove</b> deletes the practice accounts and clears their SAs.
      </p>
      {s && (
        <p className="mb-3 text-sm">
          {s.loaded ? <>Loaded: <b>{s.dqm_accounts}</b> DQM and <b>{s.fm_accounts}</b> Field Monitor practice accounts, <b>{s.sas_assigned}</b> SAs assigned, <b>{s.logged_in}</b> accounts have signed in.</> : <>Not loaded yet.</>}
        </p>
      )}
      <div className="flex flex-wrap items-end gap-3">
        <Field label="DQM practice password"><input className="input" type="text" autoComplete="off" value={dqmPw} onChange={(e) => setDqmPw(e.target.value)} placeholder="at least 8 characters" /></Field>
        <Field label="Field Monitor practice password"><input className="input" type="text" autoComplete="off" value={fmPw} onChange={(e) => setFmPw(e.target.value)} placeholder="at least 8 characters" /></Field>
        <label className="flex items-center gap-2 pb-2 text-sm"><input type="checkbox" checked={resetPw} onChange={(e) => setResetPw(e.target.checked)} /> Reset passwords of existing practice accounts</label>
        <button className="btn-primary" disabled={dqmPw.length < 8 || fmPw.length < 8 || load.isPending} onClick={() => { if (confirm("Assign the practice workload to the SAs and create the practice accounts?")) load.mutate(); }}>{load.isPending ? "Loading…" : s?.loaded ? "Load again" : "Load practice set"}</button>
        {s?.loaded && <button className="btn-outline" disabled={remove.isPending} onClick={() => { if (confirm("Delete every practice account and clear the practice codes from the SAs?")) remove.mutate(); }}>{remove.isPending ? "Removing…" : "Remove practice set"}</button>}
      </div>
      <ErrorBox error={load.error} /><ErrorBox error={remove.error} />
      {out && (
        <div className="mt-3 text-sm">
          <p className="font-semibold text-green-800">Loaded. {out.sas_assigned} SAs assigned from {out.rows} rows; {out.accounts_created} accounts created, {out.accounts_updated} already existed{out.passwords_reset ? " (passwords reset)" : ""}; {out.dqm_accounts} DQM and {out.fm_accounts} Field Monitor codes in the workbook.</p>
          {out.unknown_districts.length > 0 && <p className="text-amber-800">District codes not in the system (no scope given): {out.unknown_districts.join(", ")}</p>}
          {out.warnings.length > 0 && <ul className="mt-2 list-disc pl-5 text-amber-800">{out.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>}
        </div>
      )}
      {removed && <p className="mt-3 text-sm font-semibold text-green-800">Removed {removed.accounts} practice accounts ({removed.devices} tablets) and cleared {removed.sas_cleared} SAs.{removed.accounts_kept_with_other_records ? ` ${removed.accounts_kept_with_other_records} accounts were kept because other records still need them.` : ""}</p>}
    </Card>
  );
}

export default function ReferencePage() {
  const qc = useQueryClient();
  const districts = useQuery({ queryKey: ["ref", "districts"], queryFn: () => api.get<District[]>("/admin/reference/districts") });
  const teams = useQuery({ queryKey: ["ref", "teams"], queryFn: () => api.get<Team[]>("/admin/reference/teams") });
  const [file, setFile] = useState<File | null>(null);
  const [region, setRegion] = useState("");
  const [result, setResult] = useState<ImportResult | null>(null);
  const versions = useQuery({ queryKey: ["ref", "frame-versions"], queryFn: () => api.get<FrameVersion[]>("/admin/reference/frame-versions") });
  const importMut = useMutation({
    mutationFn: async (dryRun: boolean) => {
      const fd = new FormData();
      fd.append("file", file!);
      const params = new URLSearchParams();
      if (region) params.set("region", region);
      if (dryRun) params.set("dry_run", "true");
      const qsText = params.toString();
      return api.post<ImportResult>(`/admin/reference/import${qsText ? `?${qsText}` : ""}`, fd);
    },
    onSuccess: (r) => { setResult(r); if (!r.dry_run) { qc.invalidateQueries({ queryKey: ["ref"] }); qc.invalidateQueries({ queryKey: ["mefm"] }); } },
  });
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Reference lists</h1>
      <Card title="Import a district EA-frame workbook or a names file">
        <p className="mb-3 text-sm text-slate-600">
          Upload a census GIS district workbook (<code>DISTRICT_EA_FRAME_date.xlsx</code>): its SUPERVISORY_AREA and ENUMERATION_AREA sheets give the teams, EAs, supervisor and enumerator IDs.
          To add supervisor and enumerator names and phones afterwards, upload a CSV with columns District Code, SA Code, Supervisor Code, Supervisor, Supervisor Phone, Enumerator Code, Enumerator, Enumerator Phone.
          Re-importing updates names and keeps ids. Large workbooks can take a minute or two.
          The workload frame (<code>FIELD_MONITOR-NATIONAL_MASTER_FRAME.xlsx</code>, or the national master frame that carries the FIELD_MONITOR sheet) assigns each SA to its Field Monitor and DQM by staff code (the frame's FM-41-001 becomes FM-Bo-001); accounts with the same staff code then get exactly those SAs.
        </p>
        <div className="flex flex-wrap items-end gap-3">
          <Field label="File"><input type="file" accept=".csv,.xlsx" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></Field>
          <Field label="Region (if the file has no region column)"><input className="input" value={region} onChange={(e) => setRegion(e.target.value)} placeholder="e.g. Northern" /></Field>
          <button className="btn-outline" disabled={!file || importMut.isPending} onClick={() => importMut.mutate(true)} title="Read the file and report what it would change, without saving">{importMut.isPending ? "Working…" : "Preview changes"}</button>
          <button className="btn-primary" disabled={!file || importMut.isPending || !result?.dry_run} onClick={() => importMut.mutate(false)} title={result?.dry_run ? "Apply the previewed file" : "Preview the file first"}>Apply import</button>
        </div>
        <ErrorBox error={importMut.error} />
        {result && (
          <div className="mt-3 text-sm">
            <p className={result.dry_run ? "font-semibold text-amber-800" : "font-semibold text-green-800"}>{result.dry_run ? "Preview only, nothing saved yet." : "Applied."} Rows read: {result.rows}.</p>
            <p>New: {result.regions} regions, {result.districts} districts, {result.chiefdoms} chiefdoms, {result.sections} sections, {result.teams} SAs, {result.supervisors} supervisors, {result.enumerators} enumerators, {result.eas} EAs. Names or attributes updated on existing rows: {result.updated}. SAs assigned to a Field Monitor / DQM: {result.assigned}.</p>
            {(result.removed?.teams || result.removed?.eas) ? <p className="text-amber-800">In the districts this file covers, {result.removed.teams} SAs and {result.removed.eas} EAs already in the system are not in the file. They are kept, not deleted. {result.removed.ea_codes?.length ? `First EA codes: ${result.removed.ea_codes.join(", ")}.` : ""}</p> : null}
            {result.warnings.length > 0 && <ul className="mt-2 list-disc pl-5 text-amber-800">{result.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>}
          </div>
        )}
      </Card>
      <PracticeSet />
      <Card title="Frame versions">
        {versions.data?.length ? (
          <table className="table">
            <thead><tr><th>#</th><th>File</th><th>Applied</th><th>By</th><th className="text-right">Rows</th><th>New</th><th>Updated</th></tr></thead>
            <tbody>
              {versions.data.map((v) => (
                <tr key={v.id}>
                  <td>{v.id}</td><td className="font-medium">{v.filename}</td><td className="whitespace-nowrap">{fmt(v.applied_at)}</td><td>{v.applied_by ?? ""}</td><td className="text-right">{v.rows}</td>
                  <td className="text-xs">{Object.entries(v.counts).filter(([, n]) => n).map(([k, n]) => `${n} ${k}`).join(", ") || "none"}</td>
                  <td className="text-xs">{String((v.changes as { updated?: number }).updated ?? 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : <p className="text-sm text-slate-500">No upload recorded yet.</p>}
      </Card>
      <Card title={`Districts (${districts.data?.length ?? 0}) and teams (${teams.data?.length ?? 0})`}>
        {districts.isLoading ? <Spinner /> : (
          <table className="table">
            <thead><tr><th>District</th><th>Code</th><th>Teams (SAs)</th><th>EAs</th></tr></thead>
            <tbody>{districts.data?.map((d) => {
              const dt = teams.data?.filter((t) => t.district_id === d.id) ?? [];
              return <tr key={d.id}><td>{d.name}</td><td>{d.code}</td><td>{dt.length}</td><td>{dt.reduce((n, t) => n + (t.ea_count ?? 0), 0)}</td></tr>;
            })}</tbody>
          </table>
        )}
      </Card>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <PickListEditor kind="categories" title="Error categories" />
        <PickListEditor kind="sources" title="Error sources" />
      </div>
    </div>
  );
}
