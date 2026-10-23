import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import type { District, PickList, Team } from "../api/types";
import { useAuth } from "../auth/AuthContext";
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
  const { user, can } = useAuth();
  const { districts, teams, categories } = useReference();
  const assigned = user?.assigned_sas ?? 0;
  const myDistricts = user?.assigned_district_ids ?? [];
  // "My SAs only" with a district that holds none of them would show nothing: say so and offer the right district
  const offMyDistrict = assigned > 0 && (f.own_sas !== false || !can("dashboard.whole_district")) && !!f.district_id?.length && !f.district_id.some((d) => myDistricts.includes(d));
  const myDistrictNames = districts.filter((d) => myDistricts.includes(d.id)).map((d) => d.name).join(", ");
  // Nearly 5,000 teams nationally: only list them once a district is chosen.
  const visibleTeams = f.district_id?.length ? teams.filter((t) => f.district_id!.includes(t.district_id)) : teams;
  return (
    <div className="card mb-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
        <Field label="District">
          <select className="input" value={f.district_id?.[0] ?? ""} onChange={(e) => update({ district_id: e.target.value ? [Number(e.target.value)] : [], team_id: undefined })}>
            <option value="">All</option>
            {districts.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </Field>
        <Field label="SA">
          <SaSearch teams={visibleTeams} value={f.team_id} onChange={(id) => update({ team_id: id, district_id: id ? [teams.find((t) => t.id === id)?.district_id ?? 0].filter(Boolean) : f.district_id })} placeholder={f.district_id?.length ? "Type the SA code or name" : "Type the SA code or name (any district)"} />
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
        {assigned > 0 && !can("dashboard.whole_district") && <div className="mt-5 text-sm text-slate-600" title="Your workload from the frame: the SAs that carry your staff code">Your {assigned} SAs</div>}
        {assigned > 0 && can("dashboard.whole_district") && (
          <label className="mt-5 flex items-center gap-2 text-sm text-slate-700" title="Your workload from the frame: the SAs that carry your staff code">
            <input type="checkbox" checked={f.own_sas !== false} onChange={(e) => update({ own_sas: e.target.checked ? undefined : false })} /> My {assigned} SAs only
          </label>
        )}
        <button className="btn-outline mt-5" onClick={clear}>Clear filters</button>
      </div>
      {offMyDistrict && (
        <div className="mt-3 flex flex-wrap items-center gap-2 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-900">
          Your {assigned} SAs are in {myDistrictNames || "another district"}, not in the district selected, so nothing matches.
          <button className="font-semibold underline" onClick={() => update({ district_id: myDistricts, team_id: undefined })}>Show my SAs</button>
          {can("dashboard.whole_district") && <span>or untick "My {assigned} SAs only" to see the whole district.</span>}
        </div>
      )}
    </div>
  );
}


/** SA picker with a search box: type part of the code or name; the list shows the first 50 matches. */
function SaSearch({ teams, value, onChange, placeholder }: { teams: Team[]; value: number | undefined; onChange: (id: number | undefined) => void; placeholder: string }) {
  const selected = teams.find((t) => t.id === value);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const q = query.trim().toLowerCase();
  const matches = q ? teams.filter((t) => t.code.toLowerCase().includes(q) || t.name.toLowerCase().includes(q)).slice(0, 50) : teams.slice(0, 50);
  return (
    <div className="relative">
      <input
        className="input"
        value={open ? query : selected ? `${selected.code} ${selected.name}` : ""}
        placeholder={placeholder}
        onFocus={() => { setOpen(true); setQuery(""); }}
        onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={(e) => { if (e.key === "Escape") setOpen(false); if (e.key === "Enter" && matches.length === 1) { onChange(matches[0].id); setOpen(false); } }}
      />
      {selected && !open && <button type="button" className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-slate-400 hover:text-slate-700" title="Clear" onMouseDown={(e) => { e.preventDefault(); onChange(undefined); }}>✕</button>}
      {open && (
        <ul className="absolute z-30 mt-1 max-h-72 w-[28rem] max-w-[90vw] overflow-auto rounded-md border border-slate-200 bg-white py-1 text-sm shadow-lg">
          <li className="cursor-pointer px-3 py-1.5 text-slate-500 hover:bg-slate-50" onMouseDown={(e) => { e.preventDefault(); onChange(undefined); setOpen(false); }}>All SAs</li>
          {matches.map((t) => <li key={t.id} className="cursor-pointer px-3 py-1.5 hover:bg-sky-50" onMouseDown={(e) => { e.preventDefault(); onChange(t.id); setOpen(false); }}><b>{t.code}</b> {t.name}</li>)}
          {matches.length === 0 && <li className="px-3 py-1.5 text-slate-400">No SA matches "{query}"</li>}
          {teams.length > matches.length && !q && <li className="px-3 py-1.5 text-xs text-slate-400">{teams.length - matches.length} more: type to search</li>}
        </ul>
      )}
    </div>
  );
}
