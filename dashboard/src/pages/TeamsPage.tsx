import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api, qs } from "../api/client";
import type { TeamRow } from "../api/types";
import FiltersBar from "../components/FiltersBar";
import { Card, Empty, ErrorBox, Spinner } from "../components/ui";
import { filtersToQuery, useFilters } from "../hooks/useFilters";

export default function TeamsPage() {
  const [f] = useFilters();
  const q = qs(filtersToQuery(f));
  const nav = useNavigate();
  const rows = useQuery({ queryKey: ["by-team", q], queryFn: () => api.get<TeamRow[]>(`/dashboard/by-team${q}`) });
  return (
    <div>
      <h1 className="mb-4 text-2xl font-bold">Teams (supervisory areas)</h1>
      <FiltersBar compact />
      <Card title="Teams, most overdue first">
        <ErrorBox error={rows.error} />
        {rows.isLoading ? <Spinner /> : rows.data?.length ? (
          <table className="table">
            <thead><tr><th>Team</th><th>District</th><th>Supervisor</th><th>Total</th><th>Resolved</th><th>Unresolved</th><th>Overdue</th><th>Resolution rate</th></tr></thead>
            <tbody>
              {rows.data.map((r) => (
                <tr key={r.team_id ?? "none"} className="cursor-pointer hover:bg-slate-50" onClick={() => r.team_id && nav(`/errors${qs({ ...filtersToQuery(f), team_id: r.team_id })}`)}>
                  <td className="font-medium">{r.team}</td><td>{r.district}</td><td>{r.supervisor}</td><td>{r.total}</td><td>{r.resolved}</td><td>{r.unresolved}</td>
                  <td className={r.overdue ? "font-semibold text-red-700" : ""}>{r.overdue}</td>
                  <td>{r.total ? Math.round((r.resolved / r.total) * 100) : 0}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : <Empty />}
      </Card>
    </div>
  );
}
