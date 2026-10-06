import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";

export interface Filters {
  district_id?: number[];
  team_id?: number;
  ea_id?: number;
  category_id?: number;
  status?: string;
  date_from?: string;
  date_to?: string;
  received_on?: string;
  resolved_on?: string;
  supervisor?: string;
  enumerator?: string;
  user_id?: number;
  support_method?: string;
  overdue_only?: boolean;
  search?: string;
  own_sas?: boolean; // false = a DQM officer with a workload asks for the whole district
}

/** Filters live in the URL so a view can be bookmarked or shared. */
export function useFilters(): [Filters, (patch: Partial<Filters>) => void, () => void] {
  const [params, setParams] = useSearchParams();
  const filters = useMemo<Filters>(() => {
    const num = (k: string) => (params.get(k) ? Number(params.get(k)) : undefined);
    const str = (k: string) => params.get(k) || undefined;
    return {
      district_id: params.getAll("district_id").map(Number).filter(Boolean),
      team_id: num("team_id"),
      ea_id: num("ea_id"),
      category_id: num("category_id"),
      status: str("status"),
      date_from: str("date_from"),
      date_to: str("date_to"),
      received_on: str("received_on"),
      resolved_on: str("resolved_on"),
      supervisor: str("supervisor"),
      enumerator: str("enumerator"),
      user_id: num("user_id"),
      support_method: str("support_method"),
      overdue_only: params.get("overdue_only") === "true",
      search: str("search"),
      own_sas: params.get("own_sas") === "false" ? false : undefined,
    };
  }, [params]);

  const update = useCallback(
    (patch: Partial<Filters>) => {
      const next = new URLSearchParams(params);
      for (const [k, v] of Object.entries(patch)) {
        next.delete(k);
        if (v === undefined || v === null || v === "") continue;
        if (v === false && k !== "own_sas") continue;
        if (Array.isArray(v)) v.forEach((x) => next.append(k, String(x)));
        else next.set(k, String(v));
      }
      next.delete("page");
      setParams(next, { replace: true });
    },
    [params, setParams],
  );

  const clear = useCallback(() => setParams(new URLSearchParams(), { replace: true }), [setParams]);
  return [filters, update, clear];
}

export function filtersToQuery(f: Filters): Record<string, unknown> {
  return { ...f, district_id: f.district_id?.length ? f.district_id : undefined, own_sas: f.own_sas === false ? "false" : undefined };
}
