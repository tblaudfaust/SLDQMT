import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, fmt } from "../../api/client";
import type { MefmOverview } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { Card, Empty, ErrorBox, KpiTile, Spinner } from "../../components/ui";

/** M&E Field Monitoring, stage 1: the frame in the signed-in user's scope. Forms and dashboards follow in later stages. */
export default function MefmHomePage() {
  const { user, can } = useAuth();
  const q = useQuery({ queryKey: ["mefm", "overview"], queryFn: () => api.get<MefmOverview>("/mefm/overview") });
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
      <Card title="What is ready, and what comes next">
        <ol className="list-decimal space-y-1 pl-5 text-sm text-slate-700">
          <li><b>Stage 1 (this page):</b> the frame with chiefdoms, sections and the 10-digit EA code, uploads previewed before they are applied and kept as versions{can("mefm.manage") ? <> (see <Link to="/admin/reference" className="text-navy underline">Reference lists</Link>)</> : ""}; the District and Regional M&E roles, each seeing only their geography; active dates and a password change on first sign-in.</li>
          <li><b>Stage 2:</b> the offline Android form with every skip pattern, automatic GPS and sync.</li>
          <li><b>Stage 3:</b> the district dashboard, map, officer table, indicators and issues log.</li>
          <li><b>Stage 4:</b> regional and national dashboards.</li>
          <li><b>Stage 5:</b> exports, the daily brief and the audit trail.</li>
        </ol>
        {user?.role === "ME_DISTRICT" && <p className="mt-3 text-sm text-slate-500">As a District M&E Officer you will fill the visit forms on the Android app and follow your district here.</p>}
      </Card>
    </div>
  );
}
