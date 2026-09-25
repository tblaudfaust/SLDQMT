import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { BarChart3, ChevronDown, ChevronRight } from "lucide-react";
import clsx from "clsx";
import { api } from "../api/client";
import type { District, Named } from "../api/types";
import { useAuth } from "../auth/AuthContext";

/** Regions and districts the signed-in user may see, for menus. */
export function useGeoScope() {
  const { user } = useAuth();
  const regions = useQuery({ queryKey: ["ref", "regions"], queryFn: () => api.get<Named[]>("/admin/reference/regions"), staleTime: 300_000, enabled: !!user });
  const districts = useQuery({ queryKey: ["ref", "districts"], queryFn: () => api.get<District[]>("/admin/reference/districts"), staleTime: 300_000, enabled: !!user });
  const all = !user?.district_ids;
  const visibleDistricts = (districts.data ?? []).filter((d) => all || user!.district_ids!.includes(d.id));
  const visibleRegions = (regions.data ?? []).filter((r) => all || visibleDistricts.some((d) => d.region_id === r.id));
  return {
    regions: visibleRegions,
    districts: visibleDistricts,
    isNational: user?.role === "NATIONAL_DQM" || user?.role === "ADMIN",
    isRegional: user?.role === "REGIONAL",
    isDistrict: user?.role === "DISTRICT_DQM",
    loading: regions.isLoading || districts.isLoading,
  };
}

const KEY = "fm_analytics_menu";

export default function AnalyticsMenu() {
  const { regions, districts, isNational, isRegional } = useGeoScope();
  const loc = useLocation();
  const params = new URLSearchParams(loc.search);
  const onAnalytics = loc.pathname.startsWith("/dqm/analytics");
  const level = onAnalytics ? loc.pathname.split("/")[3] : "";
  const activeRegion = level === "region" ? Number(params.get("region_id")) : level === "district" ? districts.find((d) => d.id === Number(params.get("district_id")))?.region_id : undefined;
  const activeDistrict = level === "district" ? Number(params.get("district_id")) : undefined;

  const [open, setOpen] = useState<boolean>(() => { try { return localStorage.getItem(KEY) !== "closed"; } catch { return true; } });
  const [expanded, setExpanded] = useState<Record<number, boolean>>(() => { try { return JSON.parse(localStorage.getItem(KEY + "_regions") || "{}"); } catch { return {}; } });
  useEffect(() => { try { localStorage.setItem(KEY, open ? "open" : "closed"); } catch { /* ignore */ } }, [open]);
  useEffect(() => { try { localStorage.setItem(KEY + "_regions", JSON.stringify(expanded)); } catch { /* ignore */ } }, [expanded]);
  useEffect(() => { if (activeRegion) setExpanded((e) => (e[activeRegion] ? e : { ...e, [activeRegion]: true })); }, [activeRegion]);

  const item = (active: boolean, extra?: string) => clsx("flex items-center gap-2 rounded-md px-3 py-1.5 text-sm", active ? "bg-white/15 text-white" : "text-slate-200 hover:bg-white/10", extra);

  return (
    <div>
      <button onClick={() => setOpen(!open)} className={item(onAnalytics && !level, "w-full")}>
        <BarChart3 size={16} /> <span className="flex-1 text-left">DQM analytics</span> {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
      </button>
      {open && (
        <div className="ml-3 mt-1 space-y-0.5 border-l border-white/10 pl-2">
          <Link to="/dqm/analytics" className={item(onAnalytics && !level)}>Overview</Link>
          {isNational && <Link to="/dqm/analytics/national" className={item(level === "national")}>National</Link>}
          {regions.map((r) => {
            const rd = districts.filter((d) => d.region_id === r.id);
            const isOpen = !!expanded[r.id];
            return (
              <div key={r.id}>
                <div className="flex items-center">
                  {isNational || isRegional ? (
                    <Link to={`/dqm/analytics/region?region_id=${r.id}`} className={item(level === "region" && activeRegion === r.id, "flex-1")}>{r.name} region</Link>
                  ) : (
                    <span className="flex-1 px-3 py-1.5 text-sm text-slate-300">{r.name} region</span>
                  )}
                  {rd.length > 0 && (
                    <button aria-label={`${isOpen ? "Collapse" : "Expand"} ${r.name} districts`} className="rounded p-1 text-slate-300 hover:bg-white/10" onClick={() => setExpanded({ ...expanded, [r.id]: !isOpen })}>
                      {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    </button>
                  )}
                </div>
                {isOpen && (
                  <div className="ml-3 space-y-0.5 border-l border-white/10 pl-2">
                    {rd.map((d) => (
                      <Link key={d.id} to={`/dqm/analytics/district?district_id=${d.id}`} className={item(activeDistrict === d.id)}>{d.name}</Link>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
