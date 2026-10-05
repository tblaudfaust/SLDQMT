import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { District, PickList, Team } from "../api/types";
import { useFilters } from "../hooks/useFilters";
import { Field } from "./ui";

export function useReference() {
  const districts = useQuery({ queryKey: ["ref", "districts"], queryFn: () => api.get<District[]>("/admin/reference/districts"), staleTime: 300_000 });
  const teams = useQuery({ queryKey: ["ref", "teams"], queryFn: () => api.get<Team[]>("/admin/reference/teams"), staleTime: 300_000 });
  const categories = useQuery({ queryKey: ["ref", "categories"], queryFn: () => api.get<PickList[]>("/admin/reference/categories"), staleTime: 300_000 });
  return { districts: districts.data ?? [], teams: teams.data ?? [], categories: categories.data ?? [] };
}

export default function FiltersBar({ compact = false }: { compact?: boolean }) {
  const [f, update, clear] = useFilters();
  const { districts, teams, categories } = useReference();
  // Nearly 5,000 teams nationally: only list them once a district is chosen.
  const visibleTeams = f.district_id?.length ? teams.filter((t) => f.district_id!.includes(t.district_id)) : [];
  return (
    <div className="card mb-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
        <Field label="District">
          <select className="input" value={f.district_id?.[0] ?? ""} onChange={(e) => update({ district_id: e.target.value ? [Number(e.target.value)] : [], team_id: undefined })}>
            <option value="">All</option>
            {districts.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </Field>
        <Field label="Team">
          <select className="input" value={f.team_id ?? ""} disabled={!f.district_id?.length} onChange={(e) => update({ team_id: e.target.value ? Number(e.target.value) : undefined })}>
            <option value="">{f.district_id?.length ? "All" : "Choose a district first"}</option>
            {visibleTeams.map((t) => <option key={t.id} value={t.id}>{t.code} {t.name}</option>)}
          </select>
        </Field>
        <Field label="Category">
          <select className="input" value={f.category_id ?? ""} onChange={(e) => update({ category_id: e.target.value ? Number(e.target.value) : undefined })}>
            <option value="">All</option>
            {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </Field>
        <Field label="Status">
          <select className="input" value={f.overdue_only ? "OVERDUE" : f.status ?? ""} onChange={(e) => {
            const v = e.target.value;
            update({ status: v === "OVERDUE" ? "UNRESOLVED" : v || undefined, overdue_only: v === "OVERDUE" });
          }}>
            <option value="">All</option>
            <option value="UNRESOLVED">Unresolved</option>
            <option value="OVERDUE">Overdue</option>
            <option value="RESOLVED">Resolved</option>
          </select>
        </Field>
        <Field label="Received from DQM"><input type="date" className="input" title="Errors the Field Monitor received from the DQM team on this day" value={f.received_on ?? ""} onChange={(e) => update({ received_on: e.target.value })} /></Field>
        <Field label="Date Resolved"><input type="date" className="input" title="Errors the Field Monitor resolved on this day" value={f.resolved_on ?? ""} onChange={(e) => update({ resolved_on: e.target.value })} /></Field>
        {!compact && (
          <>
            <Field label="Supervisor"><input className="input" placeholder="name contains" value={f.supervisor ?? ""} onChange={(e) => update({ supervisor: e.target.value })} /></Field>
            <Field label="Enumerator"><input className="input" placeholder="name contains" value={f.enumerator ?? ""} onChange={(e) => update({ enumerator: e.target.value })} /></Field>
          </>
        )}
      </div>
      <div className="mt-3 flex items-center gap-3">
        <Field label="Support">
          <select className="input" value={f.support_method ?? ""} onChange={(e) => update({ support_method: e.target.value || undefined })}>
            <option value="">Any</option>
            <option value="REMOTE">Remote</option>
            <option value="ONSITE">Onsite</option>
          </select>
        </Field>
        <button className="btn-outline mt-5" onClick={clear}>Clear filters</button>
      </div>
    </div>
  );
}
