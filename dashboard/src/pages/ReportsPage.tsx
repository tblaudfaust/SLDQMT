import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, download, qs } from "../api/client";
import FiltersBar from "../components/FiltersBar";
import { Card, ErrorBox } from "../components/ui";
import { filtersToQuery, useFilters } from "../hooks/useFilters";

const DESCRIPTIONS: Record<string, string> = {
  daily_summary: "Headline figures, by district, and the daily trend. For the morning briefing.",
  district_register: "Every error in the filtered set with all fields. For district review.",
  overdue: "Unresolved errors past their follow-up time, by monitor and team. The chasing list.",
  category_analysis: "Counts and resolution rate per category, plus a category-by-district matrix.",
  team_performance: "Per team: errors, resolved, unresolved, overdue.",
  monitor_activity: "Per Field Monitor: errors logged, overdue, last sync, app version.",
  full_export: "All errors, follow-ups and activity history as one workbook, for analysis.",
};

export default function ReportsPage() {
  const [f] = useFilters();
  const kinds = useQuery({ queryKey: ["report-kinds"], queryFn: () => api.get<{ kind: string; title: string }[]>("/reports") });
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const run = async (kind: string, format: "xlsx" | "pdf") => {
    setBusy(`${kind}:${format}`);
    setError(null);
    try {
      await download(`/reports/${kind}${qs({ ...filtersToQuery(f), format })}`, `${kind}.${format}`);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(null);
    }
  };
  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold">Reports</h1>
      <p className="mb-4 text-sm text-slate-500">Every report uses the filters below and your access scope, so its totals match the dashboard.</p>
      <FiltersBar />
      <ErrorBox error={error} />
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {(kinds.data ?? []).filter((k) => k.kind !== "error_detail").map((k) => (
          <Card key={k.kind} title={k.title}>
            <p className="mb-3 text-sm text-slate-600">{DESCRIPTIONS[k.kind]}</p>
            <div className="flex gap-2">
              <button className="btn-primary" disabled={!!busy} onClick={() => run(k.kind, "xlsx")}>{busy === `${k.kind}:xlsx` ? "Generating…" : "Excel"}</button>
              <button className="btn-outline" disabled={!!busy} onClick={() => run(k.kind, "pdf")}>{busy === `${k.kind}:pdf` ? "Generating…" : "PDF"}</button>
            </div>
          </Card>
        ))}
      </div>
      <p className="mt-4 text-xs text-slate-400">The error detail sheet is generated from an error's page.</p>
    </div>
  );
}
