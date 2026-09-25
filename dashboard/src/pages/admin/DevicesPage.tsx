import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, fmt } from "../../api/client";
import type { Device } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { Card, Empty, ErrorBox, Spinner } from "../../components/ui";

export default function DevicesPage() {
  const qc = useQueryClient();
  const { user } = useAuth();
  const devices = useQuery({ queryKey: ["admin", "devices"], queryFn: () => api.get<Device[]>("/admin/devices") });
  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: "ACTIVE" | "BLOCKED" }) => api.patch(`/admin/devices/${id}`, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "devices"] }),
  });
  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold">Devices</h1>
      <p className="mb-4 text-sm text-slate-500">Blocking a tablet makes its next sync fail with a clear message and wipes the data on it. Use it for lost tablets.</p>
      <Card>
        <ErrorBox error={setStatus.error} />
        {devices.isLoading ? <Spinner /> : devices.data?.length ? (
          <table className="table">
            <thead><tr><th>Field Monitor</th><th>Model</th><th>Android</th><th>App</th><th>Registered</th><th>Last login</th><th>Last sync</th><th>Pending on tablet</th><th>Status</th><th></th></tr></thead>
            <tbody>
              {devices.data.map((d) => (
                <tr key={d.id}>
                  <td className="font-medium">{d.full_name}<div className="text-xs text-slate-400">{d.username}</div></td>
                  <td>{d.model}</td><td>{d.android_version}</td><td>{d.app_version}</td><td>{fmt(d.registered_at)}</td><td>{fmt(d.last_login_at)}</td><td>{d.last_sync_at ? fmt(d.last_sync_at) : "never"}</td><td>{d.pending_reported}</td>
                  <td>{d.status === "ACTIVE" ? <span className="text-green-700">Active</span> : <span className="font-semibold text-red-700">Blocked</span>}</td>
                  <td>
                    {user?.role === "ADMIN" && (
                      d.status === "ACTIVE"
                        ? <button className="text-sm text-red-700" onClick={() => confirm(`Block ${d.model ?? "this tablet"} used by ${d.full_name}? Its local data will be wiped at the next sync.`) && setStatus.mutate({ id: d.id, status: "BLOCKED" })}>Block</button>
                        : <button className="text-sm text-navy" onClick={() => setStatus.mutate({ id: d.id, status: "ACTIVE" })}>Unblock</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : <Empty text="No tablets registered yet" />}
      </Card>
    </div>
  );
}
