import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, fmt } from "../../api/client";
import type { MefmOverview, MefmVisitRow } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { Card, Empty, ErrorBox, KpiTile, Spinner } from "../../components/ui";

const PHASES: Record<string, string> = { P: "Pre-field", L: "Listing", E: "Enumeration", M: "Mop-up" };

/** M&E Field Monitoring: the frame in the signed-in user's scope (stage 1) and the visit forms received from the app (stage 2). Dashboards follow in stage 3. */
export default function MefmHomePage() {
  const { user, can } = useAuth();
  const q = useQuery({ queryKey: ["mefm", "overview"], queryFn: () => api.get<MefmOverview>("/mefm/overview") });
  const visits = useQuery({ queryKey: ["mefm", "visits", "recent"], queryFn: () => api.get<MefmVisitRow[]>("/mefm/visits?limit=50") });
  if (q.isLoading) return <Spinner />;
  if (q.error || !q.data) return <ErrorBox error={q.error} />;
  const d = q.data;
  const t = d.totals;
  return (
    <div>
      <div className="mb-4">
        <h1 className="text-2xl font-bold">Field monitoring</h1>
        <p className="text-sm text-slate-500">
          2026 SLPHC M&E Field Monitoring. Your scope: <b>{d.scope}</b>. The pick lists, access rules and dashboard totals of this module come from the national frame below.
        </p>
      </div>
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <KpiTile label="Districts" value={t.districts} />
        <KpiTile label="Chiefdoms" value={t.chiefdoms} />
        <KpiTile label="Sections" value={t.sections} />
        <KpiTile label="Supervisory areas" value={t.sas} />
        <KpiTile label="Enumeration areas" value={t.eas} tone="green" sub={`${t.eas_with_point} with a reference point`} />
        <KpiTile label="Frame version" value={d.frame_version ? `#${d.frame_version.id}` : "—"} tone="amber" sub={d.frame_version ? `${d.frame_version.filename} · ${fmt(d.frame_version.applied_at)}` : "no upload recorded yet"} />
      </div>
      <Card title="Frame by district" className="mb-4">
        {d.districts.length ? (
          <div className="overflow-x-auto">
            <table className="table">
              <thead><tr><th>District</th><th>Region</th><th className="text-right">Chiefdoms</th><th className="text-right">Sections</th><th className="text-right">SAs</th><th className="text-right">EAs</th><th className="text-right">EAs with a point</th></tr></thead>
              <tbody>
                {d.districts.map((r) => (
                  <tr key={r.district_id}>
                    <td className="font-medium">{r.district}</td><td>{r.region}</td>
                    <td className="text-right">{r.chiefdoms}</td><td className="text-right">{r.sections}</td><td className="text-right">{r.sas}</td><td className="text-right">{r.eas}</td>
                    <td className={`text-right ${r.eas_with_point < r.eas ? "text-amber-700" : ""}`}>{r.eas_with_point}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <Empty text="No district in your scope. Ask an administrator to assign your district." />}
      </Card>
      <Card title="Recent visit forms" className="mb-4">
        {visits.isLoading ? <Spinner /> : (visits.data ?? []).length ? (
          <div className="overflow-x-auto">
            <table className="table">
              <thead><tr><th>Date</th><th>Officer</th><th>District</th><th>Chiefdom / section</th><th>EA</th><th>Phase</th><th>Team found</th><th className="text-right">Rating</th><th className="text-right">Critical</th><th className="text-right">Open issues</th><th>GPS checks</th></tr></thead>
              <tbody>
                {(visits.data ?? []).map((v) => (
                  <tr key={v.id}>
                    <td className="whitespace-nowrap">{fmt(v.visit_date)}</td>
                    <td>{v.officer}</td>
                    <td>{v.district}</td>
                    <td>{[v.chiefdom, v.section].filter(Boolean).join(" / ")}</td>
                    <td><span className="font-mono">{v.pop_ea_code}</span>{v.ea_name ? <span className="text-slate-500"> · {v.ea_name}</span> : null}</td>
                    <td>{PHASES[v.phase] ?? v.phase}</td>
                    <td className={v.team_found === false ? "text-red-700" : ""}>{v.team_found == null ? "—" : v.team_found ? "Yes" : "No"}</td>
                    <td className="text-right">{v.overall_rating ?? "—"}</td>
                    <td className={`text-right ${v.critical_count ? "font-semibold text-red-700" : ""}`}>{v.critical_count}</td>
                    <td className="text-right">{v.open_issues}</td>
                    <td className={v.flags.length ? "text-amber-700" : "text-slate-500"}>{v.flags.length ? v.flags.map((f) => f.replace(/_/g, " ")).join(", ") : v.distance_to_ea_m != null ? `${Math.round(v.distance_to_ea_m)} m from the EA point` : "no EA point"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <Empty text="No visit forms received yet. District M&E Officers send them from the Android app." />}
      </Card>
      <Card title="What is ready, and what comes next">
        <ol className="list-decimal space-y-1 pl-5 text-sm text-slate-700">
          <li><b>Stage 1 (this page):</b> the frame with chiefdoms, sections and the 10-digit EA code, uploads previewed before they are applied and kept as versions{can("mefm.manage") ? <> (see <Link to="/admin/reference" className="text-navy underline">Reference lists</Link>)</> : ""}; the District and Regional M&E roles, each seeing only their geography; active dates and a password change on first sign-in.</li>
          <li><b>Stage 2 (live):</b> the offline Android form with every skip pattern, automatic GPS, check-ins and sync; District M&E Officers sign in to the same app as Field Monitors (version 0.4.0 or later, on the <Link to="/resources" className="text-navy underline">manuals and app page</Link>).</li>
          <li><b>Stage 3:</b> the district dashboard, map, officer table, indicators and issues log.</li>
          <li><b>Stage 4:</b> regional and national dashboards.</li>
          <li><b>Stage 5:</b> exports, the daily brief and the audit trail.</li>
        </ol>
        {user?.role === "ME_DISTRICT" && <p className="mt-3 text-sm text-slate-500">As a District M&E Officer you will fill the visit forms on the Android app and follow your district here.</p>}
      </Card>
    </div>
  );
}
