import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, qs } from "../api/client";
import type { WorkloadRow } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { useReference } from "../components/FiltersBar";
import { Card, Empty, ErrorBox, Field, Spinner } from "../components/ui";

/** The workload frame: every supervisory area with the Field Monitor and the DQM officer responsible for it. */
export default function WorkloadPage() {
  const { user } = useAuth();
  const { districts } = useReference();
  const [districtId, setDistrictId] = useState<string>("");
  const [search, setSearch] = useState("");
  const [mine, setMine] = useState(true);
  const q = qs({ district_id: districtId || undefined, search: search || undefined });
  const rows = useQuery({ queryKey: ["workload", q], queryFn: () => api.get<WorkloadRow[]>(`/admin/reference/workload${q}`) });

  const data = useMemo(() => {
    const all = rows.data ?? [];
    if (mine && user?.staff_code) return all.filter((r) => r.monitor_code === user.staff_code || r.dqm_code === user.staff_code);
    return all;
  }, [rows.data, mine, user?.staff_code]);

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

  return (
    <div>
      <div className="mb-4">
        <h1 className="text-2xl font-bold">Workload (supervisory areas)</h1>
        <p className="text-sm text-slate-500">Each SA is assigned to one Field Monitor and one DQM officer; the pair shares the same SAs. Loaded from the workload frame on the <Link to="/admin/reference" className="text-navy underline">Reference lists</Link> page.</p>
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
                      <tr key={`${o.fm}|${o.dqm}`}>
                        <td>{o.district}</td>
                        <td className="font-medium">{o.fm}</td><td className={o.fmName ? "" : "text-amber-700"}>{o.fmName ?? "no account yet"}</td>
                        <td className="font-medium">{o.dqm}</td><td className={o.dqmName ? "" : "text-amber-700"}>{o.dqmName ?? "no account yet"}</td>
                        <td>{o.sas}</td><td>{o.eas}</td>
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
                  <thead><tr><th>SA code</th><th>SA name</th><th>District</th><th>Chiefdom</th><th>EAs</th><th>Field Monitor</th><th>DQM</th></tr></thead>
                  <tbody>
                    {data.map((r) => (
                      <tr key={r.team_id}>
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
    </div>
  );
}
