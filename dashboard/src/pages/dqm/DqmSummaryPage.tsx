import { useQuery } from "@tanstack/react-query";
import { Link, useParams, useSearchParams } from "react-router-dom";
import clsx from "clsx";
import { api, download, fmtDate, qs } from "../../api/client";
import type { DqmSummary, Named, SummaryRow } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { Card, ErrorBox, Field, KpiTile, Spinner } from "../../components/ui";

export default function DqmSummaryPage() {
  const { level = "region" } = useParams();
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const set = (k: string, v: string) => { const n = new URLSearchParams(params); if (v) n.set(k, v); else n.delete(k); setParams(n, { replace: true }); };
  const regions = useQuery({ queryKey: ["ref", "regions"], queryFn: () => api.get<Named[]>("/admin/reference/regions"), staleTime: 300_000 });
  const filters = { level, region_id: params.get("region_id") || undefined, date_from: params.get("date_from") || undefined, date_to: params.get("date_to") || undefined };
  const q = qs(filters);
  const needsRegion = level === "region" && user?.role !== "REGIONAL" && !filters.region_id;
  const s = useQuery({ queryKey: ["dqm-summary", q], queryFn: () => api.get<DqmSummary>(`/dqm-reports/summary${q}`), enabled: !needsRegion });
  const d = s.data;
  const title = level === "national" ? "National DQM summary" : `Regional DQM summary${d?.region ? ` · ${d.region}` : ""}`;
  const unit = level === "national" ? "Region" : "District";

  const Row = ({ r, bold }: { r: SummaryRow; bold?: boolean }) => (
    <tr className={clsx(bold && "bg-slate-100 font-semibold")}>
      <td>{level === "region" && !bold ? <Link className="text-navy" to={`/dqm/reports${qs({ district_id: r.key, date_from: filters.date_from, date_to: filters.date_to })}`}>{r.label}</Link> : level === "national" && !bold ? <Link className="text-navy" to={`/dqm/summary/region?region_id=${r.key}${filters.date_from ? `&date_from=${filters.date_from}` : ""}${filters.date_to ? `&date_to=${filters.date_to}` : ""}`}>{r.label}</Link> : r.label}</td>
      <td>{r.reports}</td><td>{r.submitted}</td><td>{r.received}</td><td>{r.days_covered}</td><td className="whitespace-nowrap">{fmtDate(r.latest_date)}</td>
      <td>{r.teams_reviewed ?? ""}</td><td>{r.teams_certified ?? ""}</td>
      <td>{r.reinterviews_received}</td><td>{r.reinterviews_received_pending}</td><td>{r.reinterviews_certified}</td><td>{r.reinterviews_certified_pending}</td>
      <td>{r.errors_low}</td><td>{r.errors_medium}</td><td className={r.errors_high ? "text-red-700 font-semibold" : ""}>{r.errors_high}</td>
      <td>{r.issues_outlier}</td><td>{r.issues_gps}</td><td>{r.issues_sync}</td><td className={r.issues_open ? "text-amber-800 font-semibold" : ""}>{r.issues_open}</td><td>{r.lessons}</td>
    </tr>
  );

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <Link to="/dqm/reports" className="text-sm text-navy">← DQM reports</Link>
          <h1 className="text-2xl font-bold">{title}</h1>
          <p className="text-sm text-slate-500">Roll-up of the daily DQM reports {level === "national" ? "by region" : "by district"}. SAs reviewed and certified are cumulative, so the latest report per district is used; everything else is summed over the period.</p>
        </div>
        {d && (
          <div className="flex gap-2">
            <button className="btn-outline" onClick={() => download(`/dqm-reports/summary/export${qs({ ...filters, format: "xlsx" })}`, "summary.xlsx")}>Excel</button>
            <button className="btn-outline" onClick={() => download(`/dqm-reports/summary/export${qs({ ...filters, format: "pdf" })}`, "summary.pdf")}>PDF</button>
          </div>
        )}
      </div>
      <div className="card mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        {level === "region" && user?.role !== "REGIONAL" && (
          <Field label="Region">
            <select className="input" value={filters.region_id ?? ""} onChange={(e) => set("region_id", e.target.value)}>
              <option value="">Select a region…</option>
              {regions.data?.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
            </select>
          </Field>
        )}
        <Field label="From"><input type="date" className="input" value={filters.date_from ?? ""} onChange={(e) => set("date_from", e.target.value)} /></Field>
        <Field label="To"><input type="date" className="input" value={filters.date_to ?? ""} onChange={(e) => set("date_to", e.target.value)} /></Field>
      </div>
      <ErrorBox error={s.error} />
      {needsRegion ? <p className="text-sm text-slate-500">Choose a region to see its summary.</p> : s.isLoading ? <Spinner /> : d && (
        <>
          <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6">
            <KpiTile label={`Districts reported today (${fmtDate(d.today)})`} value={`${d.reported_today} / ${d.expected_units}`} tone={d.reported_today === d.expected_units ? "green" : "amber"} />
            <KpiTile label="Reports in period" value={d.totals.reports} />
            <KpiTile label="SAs certified (cumulative)" value={d.totals.teams_certified ?? "—"} tone="green" sub={d.totals.teams_reviewed != null ? `of ${d.totals.teams_reviewed} reviewed` : undefined} />
            <KpiTile label="Reinterviews certified" value={d.totals.reinterviews_certified} tone="green" sub={`${d.totals.reinterviews_certified_pending} pending`} />
            <KpiTile label="High-discrepancy cases" value={d.totals.errors_high} tone="red" />
            <KpiTile label="Open system issues" value={d.totals.issues_open} tone="amber" />
          </div>
          {d.missing_today.length > 0 && (
            <div className="mb-4 rounded-md border border-amber/60 bg-amber/10 p-3 text-sm text-amber-900">
              <strong>No report submitted today from:</strong> {d.missing_today.join(", ")}
            </div>
          )}
          <Card title={`By ${unit.toLowerCase()}`}>
            <div className="overflow-x-auto">
              <table className="table">
                <thead>
                  <tr>
                    <th rowSpan={2}>{unit}</th><th colSpan={5}>Reporting</th><th colSpan={2}>SAs (cumulative)</th><th colSpan={4}>Re-interviews</th><th colSpan={3}>Discrepancy bands</th><th colSpan={4}>GIS / CAPI / sync issues</th><th rowSpan={2}>Lessons</th>
                  </tr>
                  <tr>
                    <th>Reports</th><th>Submitted</th><th>Received</th><th>Days</th><th>Latest</th>
                    <th>Reviewed</th><th>Certified</th>
                    <th>Received</th><th>Pending</th><th>Certified</th><th>Pending</th>
                    <th>Low</th><th>Medium</th><th>High</th>
                    <th>Outliers</th><th>GPS</th><th>Sync</th><th>Open</th>
                  </tr>
                </thead>
                <tbody>
                  {d.rows.map((r) => <Row key={r.key} r={r} />)}
                  <Row r={d.totals} bold />
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
