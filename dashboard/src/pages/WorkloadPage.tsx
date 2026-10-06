import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, api, qs } from "../api/client";
import type { Officer, WorkloadRow } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { useReference } from "../components/FiltersBar";
import { Card, Empty, ErrorBox, Field, Spinner } from "../components/ui";

const KEEP = "__keep__";
const NONE = "__none__";

/** The workload frame: every supervisory area with the Field Monitor and the DQM officer responsible for it,
 *  and, for users with the right, reassignment of SAs between officers of the same district. */
export default function WorkloadPage() {
  const { user, can } = useAuth();
  const qc = useQueryClient();
  const { districts } = useReference();
  const canAssign = can("workload.assign");
  const [districtId, setDistrictId] = useState<string>("");
  const [search, setSearch] = useState("");
  const [mine, setMine] = useState(true);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [dialog, setDialog] = useState(false);
  const q = qs({ district_id: districtId || undefined, search: search || undefined });
  const rows = useQuery({ queryKey: ["workload", q], queryFn: () => api.get<WorkloadRow[]>(`/admin/reference/workload${q}`) });

  const data = useMemo(() => {
    const all = rows.data ?? [];
    if (mine && user?.staff_code) return all.filter((r) => r.monitor_code === user.staff_code || r.dqm_code === user.staff_code);
    return all;
  }, [rows.data, mine, user?.staff_code]);

  useEffect(() => { setSelected(new Set()); }, [q, mine]);

  const byOfficer = useMemo(() => {
    const m = new Map<string, { fm: string | null; dqm: string | null; fmName: string | null; dqmName: string | null; district: string; sas: number; eas: number }>();
    for (const r of data) {
      const key = `${r.monitor_code ?? "?"}|${r.dqm_code ?? "?"}`;
      const e = m.get(key) ?? { fm: r.monitor_code, dqm: r.dqm_code, fmName: r.monitor_name, dqmName: r.dqm_name, district: r.district, sas: 0, eas: 0 };
      e.sas += 1;
      e.eas += r.ea_count ?? 0;
      m.set(key, e);
    }
    return Array.from(m.values());
  }, [data]);

  const unassigned = data.filter((r) => !r.monitor_code).length;
  const noAccount = byOfficer.filter((o) => (o.fm && !o.fmName) || (o.dqm && !o.dqmName)).length;
  const selectedRows = data.filter((r) => selected.has(r.team_id));
  const selectedDistricts = new Set(selectedRows.map((r) => r.district_id));
  const allShownSelected = data.length > 0 && data.every((r) => selected.has(r.team_id));

  const toggle = (id: number) => setSelected((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const toggleAll = () => setSelected(allShownSelected ? new Set() : new Set(data.map((r) => r.team_id)));

  return (
    <div>
      <div className="mb-4">
        <h1 className="text-2xl font-bold">Workload (supervisory areas)</h1>
        <p className="text-sm text-slate-500">
          Each SA is assigned to one Field Monitor and one DQM officer of its district; the pair shares the same SAs. Loaded from the workload frame on the <Link to="/admin/reference" className="text-navy underline">Reference lists</Link> page.
          {canAssign && " Tick SAs and use Reassign to move them to another officer of the same district, for example to share a heavy workload."}
        </p>
      </div>
      <div className="card mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Field label="District">
          <select className="input" value={districtId} onChange={(e) => setDistrictId(e.target.value)}>
            <option value="">All in my scope</option>
            {districts.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </Field>
        <Field label="Search"><input className="input" placeholder="SA code, SA name, chiefdom, FM-11-001, DQM-11-001" value={search} onChange={(e) => setSearch(e.target.value)} /></Field>
        {user?.staff_code && (
          <label className="flex items-end gap-2 pb-2 text-sm text-slate-700"><input type="checkbox" checked={mine} onChange={(e) => setMine(e.target.checked)} /> My SAs only ({user.staff_code})</label>
        )}
        {canAssign && (
          <div className="flex items-end gap-2">
            <button className="btn-primary" disabled={selected.size === 0 || selectedDistricts.size !== 1} onClick={() => setDialog(true)} title={selectedDistricts.size > 1 ? "Choose SAs of one district at a time" : undefined}>
              Reassign {selected.size || ""} selected
            </button>
            {selected.size > 0 && <button className="btn-outline" onClick={() => setSelected(new Set())}>Clear</button>}
          </div>
        )}
      </div>
      <ErrorBox error={rows.error} />
      {rows.isLoading ? <Spinner /> : (
        <>
          <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
            <div className="card"><div className="text-xs uppercase text-slate-500">SAs</div><div className="text-2xl font-bold">{data.length}</div></div>
            <div className="card"><div className="text-xs uppercase text-slate-500">Field Monitor / DQM pairs</div><div className="text-2xl font-bold">{byOfficer.filter((o) => o.fm).length}</div></div>
            <div className="card"><div className="text-xs uppercase text-slate-500">SAs without an assignment</div><div className={`text-2xl font-bold ${unassigned ? "text-amber-700" : ""}`}>{unassigned}</div></div>
            <div className="card"><div className="text-xs uppercase text-slate-500">Pairs without an account</div><div className={`text-2xl font-bold ${noAccount ? "text-amber-700" : ""}`}>{noAccount}</div></div>
          </div>
          <Card title={`${byOfficer.filter((o) => o.fm).length} officer pairs`} className="mb-4">
            {byOfficer.length ? (
              <div className="overflow-x-auto">
                <table className="table">
                  <thead><tr><th>District</th><th>Field Monitor</th><th>Account</th><th>DQM</th><th>Account</th><th>SAs</th><th>EAs</th></tr></thead>
                  <tbody>
                    {byOfficer.filter((o) => o.fm).sort((a, b) => (a.fm ?? "").localeCompare(b.fm ?? "")).map((o) => (
                      <tr key={`${o.fm}|${o.dqm}`} className="cursor-pointer hover:bg-slate-50" title="Show this pair's SAs" onClick={() => setSearch(o.fm ?? "")}>
                        <td>{o.district}</td>
                        <td className="font-medium">{o.fm}</td><td className={o.fmName ? "" : "text-amber-700"}>{o.fmName ?? "no account yet"}</td>
                        <td className="font-medium">{o.dqm}</td><td className={o.dqmName ? "" : "text-amber-700"}>{o.dqmName ?? "no account yet"}</td>
                        <td className={o.sas > 10 ? "font-semibold text-amber-800" : ""}>{o.sas}</td><td>{o.eas}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : <Empty text="No assignments yet. Import the workload frame on the Reference lists page." />}
          </Card>
          <Card title={`${data.length} supervisory areas`}>
            {data.length ? (
              <div className="overflow-x-auto">
                <table className="table">
                  <thead><tr>{canAssign && <th><input type="checkbox" checked={allShownSelected} onChange={toggleAll} title="Select all shown" /></th>}<th>SA code</th><th>SA name</th><th>District</th><th>Chiefdom</th><th>EAs</th><th>Field Monitor</th><th>DQM</th></tr></thead>
                  <tbody>
                    {data.map((r) => (
                      <tr key={r.team_id} className={selected.has(r.team_id) ? "bg-navy-light/40" : ""}>
                        {canAssign && <td><input type="checkbox" checked={selected.has(r.team_id)} onChange={() => toggle(r.team_id)} /></td>}
                        <td className="font-medium">{r.code}</td><td>{r.name}</td><td>{r.district}</td><td>{r.chiefdom}</td><td>{r.ea_count ?? ""}</td>
                        <td>{r.monitor_code ?? <span className="text-amber-700">unassigned</span>}{r.monitor_name && <div className="text-xs text-slate-500">{r.monitor_name}</div>}</td>
                        <td>{r.dqm_code ?? <span className="text-amber-700">unassigned</span>}{r.dqm_name && <div className="text-xs text-slate-500">{r.dqm_name}</div>}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : <Empty text="No SAs" />}
          </Card>
        </>
      )}
      {dialog && selectedRows.length > 0 && (
        <ReassignDialog
          rows={selectedRows}
          onClose={() => setDialog(false)}
          onDone={() => { setDialog(false); setSelected(new Set()); qc.invalidateQueries({ queryKey: ["workload"] }); }}
        />
      )}
    </div>
  );
}

function ReassignDialog({ rows, onClose, onDone }: { rows: WorkloadRow[]; onClose: () => void; onDone: () => void }) {
  const districtId = rows[0].district_id;
  const officers = useQuery({ queryKey: ["officers", districtId], queryFn: () => api.get<Officer[]>(`/admin/reference/officers${qs({ district_id: districtId })}`) });
  const [fm, setFm] = useState(KEEP);
  const [dqm, setDqm] = useState(KEEP);
  const [error, setError] = useState<unknown>(null);
  const currentFms = new Set(rows.map((r) => r.monitor_code));
  const currentDqms = new Set(rows.map((r) => r.dqm_code));
  const save = useMutation({
    mutationFn: () => api.patch<WorkloadRow[]>("/admin/reference/workload/assign", {
      team_ids: rows.map((r) => r.team_id),
      monitor_code: fm === KEEP ? null : fm === NONE ? "" : fm,
      dqm_code: dqm === KEEP ? null : dqm === NONE ? "" : dqm,
    }),
    onSuccess: onDone,
    onError: setError,
  });
  const label = (o: Officer) => `${o.staff_code} · ${o.full_name ?? "no account yet"} · ${o.sa_count} SA${o.sa_count === 1 ? "" : "s"}`;
  const pick = (role: Officer["role"], value: string, set: (v: string) => void, current: Set<string | null>) => (
    <select className="input" value={value} onChange={(e) => set(e.target.value)}>
      <option value={KEEP}>Keep current ({Array.from(current).map((c) => c ?? "none").join(", ")})</option>
      {(officers.data ?? []).filter((o) => o.role === role).map((o) => <option key={o.staff_code} value={o.staff_code}>{label(o)}</option>)}
      <option value={NONE}>No one (unassign)</option>
    </select>
  );
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div className="w-full max-w-xl rounded-lg bg-white p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <h2 className="mb-1 text-lg font-semibold">Reassign {rows.length} SA{rows.length === 1 ? "" : "s"} in {rows[0].district}</h2>
        <p className="mb-3 text-sm text-slate-500">
          {rows.slice(0, 6).map((r) => r.code).join(", ")}{rows.length > 6 ? ` and ${rows.length - 6} more` : ""}. Only officers of {rows[0].district} can be chosen; the Field Monitor's tablet picks up the change at its next sync.
        </p>
        {officers.isLoading ? <Spinner /> : (
          <div className="grid gap-3">
            <Field label="Field Monitor">{pick("FIELD_MONITOR", fm, setFm, currentFms)}</Field>
            <Field label="DQM officer">{pick("DISTRICT_DQM", dqm, setDqm, currentDqms)}</Field>
          </div>
        )}
        <ErrorBox error={error instanceof ApiError ? error.message : error} />
        <div className="mt-4 flex justify-end gap-2">
          <button className="btn-outline" onClick={onClose}>Cancel</button>
          <button className="btn-primary" disabled={save.isPending || (fm === KEEP && dqm === KEEP)} onClick={() => save.mutate()}>{save.isPending ? "Saving…" : "Reassign"}</button>
        </div>
      </div>
    </div>
  );
}
