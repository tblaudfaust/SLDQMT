import { Link } from "react-router-dom";
import { Globe2, Map, MapPin } from "lucide-react";
import { useGeoScope } from "../../components/AnalyticsMenu";
import { Spinner } from "../../components/ui";

function Tile({ to, icon, title, sub }: { to: string; icon: React.ReactNode; title: string; sub?: string }) {
  return (
    <Link to={to} className="card flex items-center gap-3 hover:shadow transition">
      <span className="rounded-md bg-navy-light p-2 text-navy">{icon}</span>
      <span>
        <span className="block font-medium">{title}</span>
        {sub && <span className="block text-xs text-slate-500">{sub}</span>}
      </span>
    </Link>
  );
}

export default function DqmAnalyticsIndexPage() {
  const { regions, districts, isNational, isRegional, loading } = useGeoScope();
  if (loading) return <Spinner />;
  return (
    <div>
      <h1 className="text-2xl font-bold">DQM analytics</h1>
      <p className="mb-4 text-sm text-slate-500">Pick a level. Every page uses the same charts: teams, re-interviews, discrepancy bands, system issues over time, and reporting compliance; regional and national pages add comparisons by district or region.</p>
      {isNational && (
        <section className="mb-6">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">National</h2>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            <Tile to="/dqm/analytics/national" icon={<Globe2 size={18} />} title="National" sub={`${regions.length} regions · ${districts.length} districts`} />
          </div>
        </section>
      )}
      {(isNational || isRegional) && (
        <section className="mb-6">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">Regional</h2>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3 xl:grid-cols-5">
            {regions.map((r) => <Tile key={r.id} to={`/dqm/analytics/region?region_id=${r.id}`} icon={<Map size={18} />} title={`${r.name} region`} sub={`${districts.filter((d) => d.region_id === r.id).length} districts`} />)}
          </div>
        </section>
      )}
      {regions.map((r) => {
        const rd = districts.filter((d) => d.region_id === r.id);
        if (!rd.length) return null;
        return (
          <section key={r.id} className="mb-6">
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">Districts · {r.name}</h2>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3 xl:grid-cols-4">
              {rd.map((d) => <Tile key={d.id} to={`/dqm/analytics/district?district_id=${d.id}`} icon={<MapPin size={18} />} title={d.name} sub={`${r.name} region`} />)}
            </div>
          </section>
        );
      })}
    </div>
  );
}
