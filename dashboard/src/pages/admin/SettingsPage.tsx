import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { api } from "../../api/client";
import { Card, ErrorBox, Field, Spinner } from "../../components/ui";

export default function SettingsPage() {
  const qc = useQueryClient();
  const settings = useQuery({ queryKey: ["admin", "settings"], queryFn: () => api.get<Record<string, string>>("/admin/settings") });
  const [form, setForm] = useState({ follow_up_interval_hours: "4", quiet_hours_start: "20:00", quiet_hours_end: "07:00", offline_days: "14" });
  useEffect(() => { if (settings.data) setForm((f) => ({ ...f, ...settings.data })); }, [settings.data]);
  const save = useMutation({
    mutationFn: () => api.put("/admin/settings", { follow_up_interval_hours: Number(form.follow_up_interval_hours), quiet_hours_start: form.quiet_hours_start, quiet_hours_end: form.quiet_hours_end, offline_days: Number(form.offline_days) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "settings"] }),
  });
  const submit = (e: FormEvent) => { e.preventDefault(); save.mutate(); };
  return (
    <div className="max-w-2xl">
      <h1 className="mb-4 text-2xl font-bold">Settings</h1>
      <Card title="Follow-up rule (applied on the server and sent to every tablet at the next sync)">
        {settings.isLoading ? <Spinner /> : (
          <form onSubmit={submit} className="grid grid-cols-2 gap-3">
            <Field label="Reminder interval (hours)"><input className="input" type="number" min={0.5} step={0.5} value={form.follow_up_interval_hours} onChange={(e) => setForm({ ...form, follow_up_interval_hours: e.target.value })} /></Field>
            <Field label="Offline session (days before an online login is required)"><input className="input" type="number" min={1} max={90} value={form.offline_days} onChange={(e) => setForm({ ...form, offline_days: e.target.value })} /></Field>
            <Field label="Quiet hours start (UTC)"><input className="input" type="time" value={form.quiet_hours_start} onChange={(e) => setForm({ ...form, quiet_hours_start: e.target.value })} /></Field>
            <Field label="Quiet hours end (UTC)"><input className="input" type="time" value={form.quiet_hours_end} onChange={(e) => setForm({ ...form, quiet_hours_end: e.target.value })} /></Field>
            <div className="col-span-2"><button className="btn-primary" disabled={save.isPending}>Save</button> {save.isSuccess && <span className="ml-2 text-sm text-green-700">Saved</span>}</div>
            <div className="col-span-2"><ErrorBox error={save.error} /></div>
          </form>
        )}
      </Card>
    </div>
  );
}
