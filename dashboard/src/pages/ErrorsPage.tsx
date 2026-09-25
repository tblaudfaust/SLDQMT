import { useQuery } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, fmt, fmtDate, qs } from "../api/client";
import type { ErrorListRow, Page } from "../api/types";
import FiltersBar from "../components/FiltersBar";
import { Badge, Card, Empty, ErrorBox, Spinner } from "../components/ui";
import { filtersToQuery, useFilters } from "../hooks/useFilters";
import { useAuth } from "../auth/AuthContext";

export default function ErrorsPage() {
  const [f, update] = useFilters();
  const [params, setParams] = useSearchParams();
  const { can } = useAuth();
  const page = Number(params.get("page") || 1);
  const pageSize = 50;
  const deleted = params.get("deleted") === "true";
  const q = qs({ ...filtersToQuery(f), page, page_size: pageSize, deleted });
  const nav = useNavigate();
  const list = useQuery({ queryKey: ["errors", q], queryFn: () => api.get<Page<ErrorListRow>>(`/errors${q}`), placeholderData: (prev) => prev });
  const pages = list.data ? Math.max(1, Math.ceil(list.data.total / pageSize)) : 1;
  const setPage = (p: number) => { const next = new URLSearchParams(params); next.set("page", String(p)); setParams(next); };

  return (
    <div>
      <h1 className="mb-4 text-2xl font-bold">Errors</h1>
      <FiltersBar />
      <Card
        title={`${list.data?.total ?? 0} ${deleted ? "deleted " : ""}errors`}
        action={
          <div className="flex items-center gap-3">
            {can("errors.delete") && (
              <label className="flex items-center gap-1 text-sm text-slate-600"><input type="checkbox" checked={deleted} onChange={(e) => { const n = new URLSearchParams(params); if (e.target.checked) n.set("deleted", "true"); else n.delete("deleted"); n.delete("page"); setParams(n); }} /> Show deleted</label>
            )}
            <input className="input w-72" placeholder="Search ID, description, supervisor, enumerator" defaultValue={f.search ?? ""} onKeyDown={(e) => { if (e.key === "Enter") update({ search: (e.target as HTMLInputElement).value }); }} />
          </div>
        }
      >
        <ErrorBox error={list.error} />
        {list.isLoading ? <Spinner /> : list.data?.items.length ? (
          <div className="overflow-x-auto">
            <table className="table">
              <thead><tr><th>Error</th><th>Status</th><th>District / Team / EA</th><th>Category</th><th>Description</th><th>Supervisor</th><th>Enumerator</th><th>Received</th><th>Support</th><th>Next follow-up</th><th>Follow-ups</th><th>Field Monitor</th></tr></thead>
              <tbody>
                {list.data.items.map((r) => (
                  <tr key={r.id} className="cursor-pointer hover:bg-slate-50" onClick={() => nav(`/errors/${r.id}`)}>
                    <td className="font-medium whitespace-nowrap">{r.display_id}</td>
                    <td><Badge status={r.status} overdue={r.overdue} /></td>
                    <td className="text-xs">{r.district}<br />{r.team}{r.ea ? ` · EA ${r.ea}` : ""}</td>
                    <td>{r.category}</td>
                    <td className="max-w-xs truncate" title={r.description}>{r.description}</td>
                    <td>{r.supervisor_name}</td>
                    <td>{r.enumerator_name}</td>
                    <td className="whitespace-nowrap">{fmtDate(r.date_received)}</td>
                    <td>{r.support_method === "ONSITE" ? "Onsite" : "Remote"}</td>
                    <td className="whitespace-nowrap">{r.status === "UNRESOLVED" ? fmt(r.next_follow_up_at) : ""}</td>
                    <td className="text-center">{r.follow_up_count}</td>
                    <td>{r.monitor}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <Empty />}
        {pages > 1 && (
          <div className="mt-3 flex items-center justify-end gap-2 text-sm">
            <button className="btn-outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button>
            <span>Page {page} of {pages}</span>
            <button className="btn-outline" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</button>
          </div>
        )}
      </Card>
    </div>
  );
}
