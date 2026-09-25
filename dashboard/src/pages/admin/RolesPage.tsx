import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import clsx from "clsx";
import { api } from "../../api/client";
import type { RoleMatrix } from "../../api/types";
import { Card, ErrorBox, Spinner } from "../../components/ui";

const ROLES: { key: string; label: string; level: string }[] = [
  { key: "DISTRICT_DQM", label: "District DQM", level: "District" },
  { key: "REGIONAL", label: "Regional staff", level: "Region" },
  { key: "NATIONAL_DQM", label: "National DQM", level: "National" },
  { key: "ADMIN", label: "Administrator", level: "National" },
  { key: "FIELD_MONITOR", label: "Field Monitor", level: "District (tablet)" },
];

export default function RolesPage() {
  const qc = useQueryClient();
  const matrix = useQuery({ queryKey: ["admin", "roles"], queryFn: () => api.get<RoleMatrix>("/admin/roles") });
  const [draft, setDraft] = useState<Record<string, Set<string>>>({});
  const [dirty, setDirty] = useState<Set<string>>(new Set());
  useEffect(() => {
    if (matrix.data) {
      setDraft(Object.fromEntries(Object.entries(matrix.data.roles).map(([r, codes]) => [r, new Set(codes)])));
      setDirty(new Set());
    }
  }, [matrix.data]);
  const save = useMutation({
    mutationFn: async (role: string) => api.put<RoleMatrix>(`/admin/roles/${role}`, { codes: [...(draft[role] ?? [])] }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "roles"] }),
  });
  if (matrix.isLoading || !matrix.data) return <Spinner />;
  const groups = [...new Set(matrix.data.permissions.map((p) => p.group))];
  const toggle = (role: string, code: string) => {
    setDraft((d) => { const s = new Set(d[role] ?? []); if (s.has(code)) s.delete(code); else s.add(code); return { ...d, [role]: s }; });
    setDirty((s) => new Set(s).add(role));
  };
  const reset = (role: string) => { setDraft((d) => ({ ...d, [role]: new Set(matrix.data!.defaults[role] ?? []) })); setDirty((s) => new Set(s).add(role)); };

  return (
    <div>
      <h1 className="text-2xl font-bold">Roles and rights</h1>
      <p className="mb-4 text-sm text-slate-500">
        Each role's rights by level. Tick or untick, then save the column. Geographic scope (a user's district or region) always applies on top of these rights.
        Individual users can be given extra rights or have rights removed on the Users page. Every change here is recorded in the audit log.
      </p>
      <ErrorBox error={save.error} />
      <Card>
        <div className="overflow-x-auto">
          <table className="table">
            <thead>
              <tr>
                <th className="w-96">Right</th>
                {ROLES.map((r) => (
                  <th key={r.key} className="text-center">
                    {r.label}<div className="text-[10px] font-normal normal-case text-slate-500">{r.level}</div>
                    <div className="mt-1 flex justify-center gap-1">
                      <button className={clsx("rounded px-2 py-0.5 text-[11px]", dirty.has(r.key) ? "bg-navy text-white" : "bg-slate-200 text-slate-500")} disabled={!dirty.has(r.key) || save.isPending} onClick={() => save.mutate(r.key)}>Save</button>
                      <button className="rounded bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600" onClick={() => reset(r.key)}>Defaults</button>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {groups.map((g) => (
                <>
                  <tr key={g} className="bg-slate-50"><td colSpan={ROLES.length + 1} className="font-semibold text-slate-700">{g}</td></tr>
                  {matrix.data!.permissions.filter((p) => p.group === g).map((p) => (
                    <tr key={p.code}>
                      <td><div className="font-medium">{p.description}</div><div className="text-xs text-slate-400">{p.code}</div></td>
                      {ROLES.map((r) => (
                        <td key={r.key} className="text-center">
                          <input type="checkbox" className="h-4 w-4" checked={draft[r.key]?.has(p.code) ?? false} onChange={() => toggle(r.key, p.code)} />
                        </td>
                      ))}
                    </tr>
                  ))}
                </>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
