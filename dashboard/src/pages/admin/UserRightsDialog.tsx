import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import clsx from "clsx";
import { api } from "../../api/client";
import type { PermissionInfo, User, UserPermissions } from "../../api/types";
import { ErrorBox, Spinner } from "../../components/ui";

/** Per-user rights: the role's rights, with grants (extra) and revokes (removed) for this one person. */
export default function UserRightsDialog({ user, onClose }: { user: User; onClose: () => void }) {
  const qc = useQueryClient();
  const perms = useQuery({ queryKey: ["admin", "permissions"], queryFn: () => api.get<PermissionInfo[]>("/admin/permissions"), staleTime: 300_000 });
  const rights = useQuery({ queryKey: ["admin", "user-permissions", user.id], queryFn: () => api.get<UserPermissions>(`/admin/users/${user.id}/permissions`) });
  const [state, setState] = useState<Record<string, "role" | "grant" | "revoke" | "none">>({});
  useEffect(() => {
    if (rights.data && perms.data) {
      const s: Record<string, "role" | "grant" | "revoke" | "none"> = {};
      for (const p of perms.data) {
        s[p.code] = rights.data.grant.includes(p.code) ? "grant" : rights.data.revoke.includes(p.code) ? "revoke" : rights.data.role_codes.includes(p.code) ? "role" : "none";
      }
      setState(s);
    }
  }, [rights.data, perms.data]);
  const save = useMutation({
    mutationFn: () => api.put<UserPermissions>(`/admin/users/${user.id}/permissions`, {
      grant: Object.entries(state).filter(([, v]) => v === "grant").map(([k]) => k),
      revoke: Object.entries(state).filter(([, v]) => v === "revoke").map(([k]) => k),
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["admin", "user-permissions", user.id] }); onClose(); },
  });
  const cycle = (code: string) => {
    const inRole = rights.data?.role_codes.includes(code);
    setState((s) => ({ ...s, [code]: inRole ? (s[code] === "revoke" ? "role" : "revoke") : (s[code] === "grant" ? "none" : "grant") }));
  };
  const groups = [...new Set((perms.data ?? []).map((p) => p.group))];

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div className="max-h-[90vh] w-full max-w-3xl overflow-auto rounded-lg bg-white p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-bold">Rights for {user.full_name}</h2>
        <p className="mb-3 text-sm text-slate-500">Role {user.role.replace("_", " ").toLowerCase()}. Click a right to grant it (if the role lacks it) or revoke it (if the role has it). Changes are recorded in the audit log and take effect on the user's next request.</p>
        <ErrorBox error={save.error} />
        {rights.isLoading || perms.isLoading ? <Spinner /> : (
          <div className="space-y-3">
            {groups.map((g) => (
              <div key={g}>
                <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">{g}</div>
                <div className="grid grid-cols-1 gap-1 md:grid-cols-2">
                  {perms.data!.filter((p) => p.group === g).map((p) => {
                    const v = state[p.code] ?? "none";
                    return (
                      <button key={p.code} onClick={() => cycle(p.code)} className={clsx("flex items-center justify-between rounded border px-2 py-1 text-left text-sm", v === "role" && "border-slate-300 bg-slate-50", v === "grant" && "border-green-400 bg-green-50", v === "revoke" && "border-red-400 bg-red-50 line-through", v === "none" && "border-slate-200 text-slate-400")}>
                        <span>{p.description}</span>
                        <span className="ml-2 shrink-0 text-[10px] uppercase text-slate-500">{v === "role" ? "from role" : v === "grant" ? "granted" : v === "revoke" ? "revoked" : ""}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        )}
        <div className="mt-4 flex justify-end gap-2">
          <button className="btn-outline" onClick={onClose}>Cancel</button>
          <button className="btn-primary" disabled={save.isPending} onClick={() => save.mutate()}>Save rights</button>
        </div>
      </div>
    </div>
  );
}
