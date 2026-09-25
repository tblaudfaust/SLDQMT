import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import clsx from "clsx";
import { api, fmt, qs } from "../api/client";
import type { MonitorRow } from "../api/types";
import FiltersBar from "../components/FiltersBar";
import { Card, Empty, ErrorBox, Spinner } from "../components/ui";
import { filtersToQuery, useFilters } from "../hooks/useFilters";

const STALE_HOURS = 48;

export default function MonitorsPage() {
  const [f] = useFilters();
  const q = qs(filtersToQuery(f));
  const nav = useNavigate();
  const rows = useQuery({ queryKey: ["by-monitor", q], queryFn: () => api.get<MonitorRow[]>(`/dashboard/by-monitor${q}`) });
  const stale = (iso: string | null) => !iso || Date.now() - new Date(iso).getTime() > STALE_HOURS * 3_600_000;
  return (
    <div>
      <h1 className="mb-4 text-2xl font-bold">Field Monitors</h1>
      <FiltersBar compact />
      <Card title="Monitors, most overdue first. Red rows have not synced in 48 hours.">
        <ErrorBox error={rows.error} />
        {rows.isLoading ? <Spinner /> : rows.data?.length ? (
          <table className="table">
            <thead><tr><th>Field Monitor</th><th>Districts</th><th>Total</th><th>Unresolved</th><th>Overdue</th><th>Last sync</th><th>Last activity</th><th>App</th><th>Pending on tablet</th></tr></thead>
            <tbody>
              {rows.data.map((r) => (
                <tr key={r.user_id} className={clsx("cursor-pointer hover:bg-slate-50", stale(r.last_sync_at) && "bg-red-50")} onClick={() => nav(`/errors${qs({ user_id: r.user_id })}`)}>
                  <td className="font-medium">{r.full_name}</td><td>{r.districts}</td><td>{r.total}</td><td>{r.unresolved}</td>
                  <td className={r.overdue ? "font-semibold text-red-700" : ""}>{r.overdue}</td>
                  <td className={stale(r.last_sync_at) ? "text-red-700" : ""}>{r.last_sync_at ? fmt(r.last_sync_at) : "never"}</td>
                  <td>{fmt(r.last_activity_at)}</td><td>{r.app_version}</td><td>{r.pending_reported}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : <Empty />}
      </Card>
    </div>
  );
}
