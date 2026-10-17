import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { FileSpreadsheet, Plus } from "lucide-react";
import { ApiError, api } from "../../api/client";
import type { District, IncidentSaCode } from "../../api/types";
import { Card, Empty, ErrorBox, Field, Spinner } from "../../components/ui";

/** The supervisory-area codes supervisors type on the public reporting page, with their district. */
export default function IncidentSaCodesPage() {
  const qc = useQueryClient();
  const list = useQuery({ queryKey: ["incidents", "sa-codes"], queryFn: () => api.get<IncidentSaCode[]>("/incidents/sa-codes") });
  const districts = useQuery({ queryKey: ["districts"], queryFn: () => api.get<District[]>("/admin/reference/districts") });
  const [row, setRow] = useState({ sa_code: "", district: "", team_code: "", sa_name: "", supervisor_name: "", supervisor_phone: "" });
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [search, setSearch] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const done = (r: { created: number; updated: number; unknown_district: number; errors: string[] }) => { qc.invalidateQueries({ queryKey: ["incidents", "sa-codes"] }); setResult(`${r.created} added, ${r.updated} updated${r.unknown_district ? `, ${r.unknown_district} without a known district` : ""}.${r.errors.length ? " " + r.errors.join("; ") : ""}`); setError(null); };
  const add = useMutation({ mutationFn: () => api.put("/incidents/sa-codes", [{ ...row, sa_code: row.sa_code.padStart(12, "0") }]), onSuccess: (r) => { done(r as never); setRow({ sa_code: "", district: "", team_code: "", sa_name: "", supervisor_name: "", supervisor_phone: "" }); }, onError: setError });
  const upload = useMutation({ mutationFn: (f: File) => { const fd = new FormData(); fd.append("file", f); return api.post("/incidents/sa-codes/import", fd); }, onSuccess: (r) => done(r as never), onError: setError });
  const rows = (list.data ?? []).filter((x) => !search || x.sa_code.includes(search) || (x.district ?? "").toLowerCase().includes(search.toLowerCase()) || (x.supervisor_name ?? "").toLowerCase().includes(search.toLowerCase()));
  return (
    <div className="max-w-6xl">
      <div className="mb-4"><h1 className="text-2xl font-bold">SA codes for incident reporting</h1><p className="text-sm text-slate-500">Supervisors report on the public page with their 12-digit SA code. Upload the list once; a code that is not here is still accepted but the district has to be set by hand.</p></div>
      <ErrorBox error={error instanceof ApiError ? error.message : error} />
      {result && <div className="mb-3 rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-900">{result}</div>}
      <Card className="mb-4" title="Upload the list (Excel or CSV)">
        <p className="mb-2 text-sm text-slate-600">Columns, with a header row: <code>sa_code</code> (12 digits), <code>district</code> (name or code), optional <code>team_code</code> (the SA code of the frame, e.g. 41101001), <code>sa_name</code>, <code>supervisor_name</code>, <code>supervisor_phone</code>. Codes shorter than 12 digits are padded with zeros.</p>
        <button className="btn-primary" onClick={() => fileRef.current?.click()} disabled={upload.isPending}><FileSpreadsheet size={16} /> {upload.isPending ? "Uploading…" : "Upload file"}</button>
        <input ref={fileRef} type="file" accept=".xlsx,.xlsm,.csv" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) upload.mutate(f); e.target.value = ""; }} />
      </Card>
      <Card className="mb-4" title="Add one code">
        <div className="grid gap-2 sm:grid-cols-6">
          <Field label="SA code"><input className="input" value={row.sa_code} onChange={(e) => setRow({ ...row, sa_code: e.target.value.replace(/\D/g, "").slice(0, 12) })} placeholder="000000000100" /></Field>
          <Field label="District"><select className="input" value={row.district} onChange={(e) => setRow({ ...row, district: e.target.value })}><option value="">Choose…</option>{(districts.data ?? []).map((d) => <option key={d.id} value={d.name}>{d.name}</option>)}</select></Field>
          <Field label="Frame SA code"><input className="input" value={row.team_code} onChange={(e) => setRow({ ...row, team_code: e.target.value })} placeholder="41101001" /></Field>
          <Field label="SA name"><input className="input" value={row.sa_name} onChange={(e) => setRow({ ...row, sa_name: e.target.value })} /></Field>
          <Field label="Supervisor"><input className="input" value={row.supervisor_name} onChange={(e) => setRow({ ...row, supervisor_name: e.target.value })} /></Field>
          <Field label="Phone"><input className="input" value={row.supervisor_phone} onChange={(e) => setRow({ ...row, supervisor_phone: e.target.value })} /></Field>
        </div>
        <button className="btn-outline mt-2" disabled={row.sa_code.length === 0 || !row.district || add.isPending} onClick={() => add.mutate()}><Plus size={16} /> Add</button>
      </Card>
      <Card title={`${rows.length} SA codes`} action={<input className="input w-64" placeholder="Search code, district, supervisor" value={search} onChange={(e) => setSearch(e.target.value)} />}>
        {list.isLoading ? <Spinner /> : rows.length === 0 ? <Empty text="No SA code uploaded yet" /> : (
          <div className="max-h-[60vh] overflow-auto"><table className="table">
            <thead><tr><th>SA code</th><th>District</th><th>Frame SA</th><th>SA name</th><th>Supervisor</th><th>Phone</th></tr></thead>
            <tbody>{rows.map((x) => <tr key={x.id}><td className="font-mono">{x.sa_code}</td><td className={x.district ? "" : "text-amber-700"}>{x.district ?? "unknown"}</td><td>{x.team_code ?? ""}</td><td>{x.sa_name ?? ""}</td><td>{x.supervisor_name ?? ""}</td><td>{x.supervisor_phone ?? ""}</td></tr>)}</tbody>
          </table></div>
        )}
      </Card>
    </div>
  );
}
