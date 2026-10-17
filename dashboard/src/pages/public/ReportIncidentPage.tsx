import { useEffect, useState } from "react";
import clsx from "clsx";
import { CheckCircle2, Search, Siren } from "lucide-react";
import { ApiError, api } from "../../api/client";
import type { IncidentSpec } from "../../api/types";
import SiteFooter from "../../components/SiteFooter";
import { IncidentFields, emptyIncident, incidentPayload, validateIncident, type IncidentValues } from "../incidents/IncidentForm";
import { PageWatermark } from "./EvaluatePage";

/* ------------------------------------------------------------------------------------------------
 * The public incident reporting page: /report-incident. No sign-in. A supervisor enters the SA code,
 * sees the district and SA it resolves to, describes the incident and gets an incident number with a
 * tracking code to follow it. Also: check the status of an incident by number and tracking code.
 * ---------------------------------------------------------------------------------------------- */

type Sa = { sa_code: string; recognised: boolean; district: string | null; sa_name: string | null; team_code: string | null; supervisor_name: string | null };
type Sent = { number: string; track_token: string; district: string | null; title: string; sent_at: string };
type Track = { number: string; title: string; status: string; status_label: string; severity: string; district: string | null; reported_at: string; acknowledged_at: string | null; resolved_at: string | null; resolution: string | null; updates: { id: number; at: string; author: string | null; type_label: string; text: string | null; old_value: string | null; new_value: string | null }[] };

const KEY = "incident-reports";
const fmt = (iso: string | null) => (iso ? new Date(iso).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "");

export default function ReportIncidentPage() {
  const [spec, setSpec] = useState<IncidentSpec | null>(null);
  const [saCode, setSaCode] = useState("");
  const [sa, setSa] = useState<Sa | null>(null);
  const [saError, setSaError] = useState<string | null>(null);
  const [reporter, setReporter] = useState({ name: "", role: "SUPERVISOR", phone: "", code: "" });
  const [district, setDistrict] = useState("");
  const [values, setValues] = useState<IncidentValues>(emptyIncident());
  const [busy, setBusy] = useState(false);
  const [serverErrors, setServerErrors] = useState<string[]>([]);
  const [touched, setTouched] = useState(false);
  const [done, setDone] = useState<Sent | null>(null);
  const [sent, setSent] = useState<Sent[]>(() => { try { return JSON.parse(localStorage.getItem(KEY) ?? "[]"); } catch { return []; } });
  const [track, setTrack] = useState<{ number: string; token: string }>({ number: "", token: "" });
  const [tracked, setTracked] = useState<Track | null>(null);
  const [trackError, setTrackError] = useState<string | null>(null);

  useEffect(() => { api.get<IncidentSpec>("/public/incidents/spec").then(setSpec).catch(() => setSpec(null)); }, []);
  useEffect(() => { try { localStorage.setItem(KEY, JSON.stringify(sent.slice(0, 20))); } catch { /* private mode */ } }, [sent]);
  useEffect(() => {
    if (saCode.length !== 12) { setSa(null); return; }
    api.get<Sa>(`/public/incidents/sa/${saCode}`).then((r) => { setSa(r); setSaError(null); if (r.supervisor_name && !reporter.name) setReporter((p) => ({ ...p, name: r.supervisor_name ?? "" })); }).catch((e) => { setSa(null); setSaError(e instanceof ApiError ? e.message : "Could not check the SA code"); });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [saCode]);

  const fields = spec?.role_fields?.[reporter.role] ?? ["code", "sa"];
  const required = spec?.role_required?.[reporter.role] ?? ["code", "sa"];
  const errors = [
    ...(required.includes("code") && !reporter.code.trim() ? ["Enter your application code"] : []),
    ...(required.includes("sa") && saCode.length !== 12 ? ["Enter your 12-digit SA code"] : []),
    ...(saCode && saCode.length !== 12 ? ["The SA code has 12 digits"] : []),
    ...(required.includes("district") && !district && saCode.length !== 12 ? ["Choose your district"] : []),
    ...(reporter.name.trim().length < 2 ? ["Enter your name"] : []), ...(reporter.phone.replace(/\D/g, "").length < 8 ? ["Enter your phone number"] : []), ...validateIncident(values)];

  const submit = async () => {
    setTouched(true);
    if (errors.length) return;
    setBusy(true); setServerErrors([]);
    try {
      const r = await api.post<{ number: string; track_token: string; district: string | null }>("/public/incidents", { ...incidentPayload(values), sa_code: saCode || null, district: district || null, reporter_code: reporter.code.trim() || null, reporter_name: reporter.name.trim(), reporter_role: reporter.role, reporter_phone: reporter.phone.trim() });
      const s: Sent = { number: r.number, track_token: r.track_token, district: r.district, title: values.title, sent_at: new Date().toISOString() };
      setSent((p) => [s, ...p]); setDone(s); setValues(emptyIncident()); setTouched(false);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      const detail = err instanceof ApiError ? (err.body as { detail?: { errors?: string[] } | string } | undefined)?.detail : undefined;
      setServerErrors(detail && typeof detail === "object" && Array.isArray(detail.errors) ? detail.errors : [err instanceof ApiError ? err.message : "Could not send the report. Check your connection and try again."]);
    } finally { setBusy(false); }
  };

  const lookup = async (number: string, token: string) => {
    setTrackError(null); setTracked(null);
    try { setTracked(await api.get<Track>(`/public/incidents/${encodeURIComponent(number.trim().toUpperCase())}?token=${encodeURIComponent(token.trim())}`)); } catch (e) { setTrackError(e instanceof ApiError ? e.message : "Not found"); }
  };

  return (
    <div className="relative min-h-screen overflow-hidden bg-[radial-gradient(ellipse_at_top_left,_#2a6aa6_0%,_#1F4E79_45%,_#3b0d0d_100%)] px-3 py-6 text-slate-800 sm:px-6 sm:py-10">
      <PageWatermark />
      <div className="relative mx-auto max-w-3xl">
        <header className="mb-5 flex items-center gap-3 text-white">
          <img src="/statsl-logo.png" alt="Statistics Sierra Leone" className="h-12 w-12 rounded-full bg-white p-0.5 shadow" />
          <div><div className="text-xs uppercase tracking-[0.25em] text-sky-200">Statistics Sierra Leone · 2026 PHC</div><div className="text-lg font-bold leading-tight">Census Incident Log</div></div>
        </header>
        {done && (
          <Card className="mb-4 border-l-4 border-emerald-500">
            <div className="flex items-start gap-3">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-emerald-700"><CheckCircle2 size={26} /></div>
              <div>
                <h2 className="text-lg font-bold text-navy">Incident {done.number} recorded</h2>
                <p className="text-sm text-slate-600">{done.district ? `It is with the District Statistician of ${done.district}.` : "The SA code was not recognised: HQ will assign the district."} Keep this tracking code to follow it: <span className="rounded bg-slate-100 px-1 font-mono">{done.track_token}</span>. Urgent danger to people: call the coordinator now, do not wait for the log.</p>
              </div>
            </div>
          </Card>
        )}
        <Card className="overflow-hidden p-0 sm:p-0">
          <div className="bg-gradient-to-br from-navy via-[#245a8c] to-[#7f1d1d] px-5 py-6 text-white sm:px-8">
            <h1 className="flex items-center gap-2 text-2xl font-bold"><Siren size={26} /> Report an incident</h1>
            <p className="mt-2 max-w-2xl text-sm text-sky-50/90">For field supervisors, enumerators and census staff. Say who you are, give your codes, and describe what happened. The District Statistician is told immediately and management sees every open incident every day.</p>
          </div>
          <div className="space-y-5 px-5 py-6 sm:px-8">
            {!spec ? <div className="animate-pulse text-slate-500">Loading…</div> : (
              <>
                <section className="space-y-3">
                  <h2 className="border-b border-slate-200 pb-2 text-base font-bold text-navy">1. Who you are</h2>
                  <label className="block"><span className="mb-1 block text-sm font-medium text-slate-700">Your role *</span>
                    <select className="pub-input" value={reporter.role} onChange={(e) => { setReporter({ ...reporter, role: e.target.value }); setSaCode(""); setDistrict(""); }}>{spec.reporter_roles.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}</select>
                  </label>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {fields.includes("code") && <label className="block"><span className="mb-1 block text-sm font-medium text-slate-700">Your application code{required.includes("code") ? " *" : ""}</span><input className="pub-input font-mono" value={reporter.code} onChange={(e) => setReporter({ ...reporter, code: e.target.value })} placeholder="As on your appointment letter / ID" /></label>}
                    {fields.includes("district") && <label className="block"><span className="mb-1 block text-sm font-medium text-slate-700">Your district{required.includes("district") ? " *" : ""}</span><select className="pub-input" value={district} onChange={(e) => setDistrict(e.target.value)}><option value="">Choose…</option>{spec.districts.map((d) => <option key={d} value={d}>{d}</option>)}</select></label>}
                    {fields.includes("sa") && <label className="block"><span className="mb-1 block text-sm font-medium text-slate-700">SA code (12 digits){required.includes("sa") ? " *" : ""}</span>
                      <input className={clsx("pub-input font-mono text-lg tracking-widest", saCode.length === 12 && !sa && saError && "border-red-400")} inputMode="numeric" value={saCode} onChange={(e) => setSaCode(e.target.value.replace(/\D/g, "").slice(0, 12))} placeholder="000000000100" />
                    </label>}
                    {fields.includes("ea") && <label className="block"><span className="mb-1 block text-sm font-medium text-slate-700">EA code</span><input className="pub-input font-mono" inputMode="numeric" value={values.ea_code} onChange={(e) => setValues({ ...values, ea_code: e.target.value.replace(/\D/g, "").slice(0, 10) })} placeholder="10-digit EA code" /></label>}
                  </div>
                  {sa && sa.recognised && <div className="rounded-xl bg-emerald-50 px-3 py-2 text-sm text-emerald-900"><b>{sa.district}</b>{sa.sa_name ? ` · ${sa.sa_name}` : ""}{sa.team_code ? ` · ${sa.team_code}` : ""}{sa.supervisor_name ? ` · supervisor ${sa.supervisor_name}` : ""}</div>}
                  {sa && !sa.recognised && <div className="rounded-xl bg-amber-50 px-3 py-2 text-sm text-amber-900">This SA code is not on the list yet. You can still report; HQ will set the district.</div>}
                  {saError && <div className="text-sm text-red-700">{saError}</div>}
                  <div className="grid gap-3 sm:grid-cols-2">
                    <label className="block"><span className="mb-1 block text-sm font-medium text-slate-700">Your name *</span><input className="pub-input" value={reporter.name} onChange={(e) => setReporter({ ...reporter, name: e.target.value })} autoComplete="name" /></label>
                    <label className="block"><span className="mb-1 block text-sm font-medium text-slate-700">Your phone *</span><input className="pub-input" type="tel" value={reporter.phone} onChange={(e) => setReporter({ ...reporter, phone: e.target.value })} placeholder="076 123 456" autoComplete="tel" /></label>
                  </div>
                </section>
                <section className="space-y-3">
                  <h2 className="border-b border-slate-200 pb-2 text-base font-bold text-navy">2. The incident</h2>
                  <IncidentFields spec={spec} values={values} onChange={setValues} publicStyle hideEa={fields.includes("ea")} />
                </section>
                {(serverErrors.length > 0 || (touched && errors.length > 0)) && (
                  <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"><div className="font-semibold">Please complete before sending</div><ul className="mt-1 list-disc pl-5">{[...serverErrors, ...errors].map((e) => <li key={e}>{e}</li>)}</ul></div>
                )}
                <button className="pub-btn w-full" disabled={busy} onClick={submit}>{busy ? "Sending…" : "Send the incident report"}</button>
                <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm font-medium text-amber-900">Urgent danger to people, a serious accident or a stolen tablet with unsynced data: call the District Coordinator immediately as well.</p>
              </>
            )}
          </div>
        </Card>
        <Card className="mt-4">
          <h2 className="flex items-center gap-2 text-base font-bold text-navy"><Search size={18} /> Follow an incident</h2>
          {sent.length > 0 && (
            <ul className="mt-2 divide-y divide-slate-100 text-sm">
              {sent.map((s) => <li key={s.number} className="flex items-center justify-between gap-3 py-2"><span><span className="font-mono font-semibold">{s.number}</span> · {s.title} <span className="text-slate-400">· {fmt(s.sent_at)}</span></span><button type="button" className="pub-btn-ghost py-1.5 text-sm" onClick={() => lookup(s.number, s.track_token)}>Status</button></li>)}
            </ul>
          )}
          <div className="mt-3 grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
            <input className="pub-input font-mono" placeholder="Incident number, e.g. INC-Bo-202611-0042" value={track.number} onChange={(e) => setTrack({ ...track, number: e.target.value })} />
            <input className="pub-input font-mono" placeholder="Tracking code" value={track.token} onChange={(e) => setTrack({ ...track, token: e.target.value })} />
            <button type="button" className="pub-btn" onClick={() => lookup(track.number, track.token)} disabled={!track.number || !track.token}>Check</button>
          </div>
          {trackError && <div className="mt-2 text-sm text-red-700">{trackError}</div>}
          {tracked && (
            <div className="mt-3 rounded-xl border border-slate-200 p-3 text-sm">
              <div className="flex flex-wrap items-center gap-2"><span className="font-mono font-bold text-navy">{tracked.number}</span><span className={clsx("rounded-full px-2 py-0.5 text-xs font-semibold text-white", tracked.status === "RESOLVED" || tracked.status === "CLOSED" ? "bg-emerald-600" : tracked.status === "REJECTED" ? "bg-slate-400" : "bg-navy")}>{tracked.status_label}</span><span className="text-slate-500">{tracked.district ?? ""}</span></div>
              <div className="mt-1 font-medium">{tracked.title}</div>
              <div className="text-xs text-slate-500">Reported {fmt(tracked.reported_at)}{tracked.acknowledged_at ? ` · acknowledged ${fmt(tracked.acknowledged_at)}` : " · not yet acknowledged"}{tracked.resolved_at ? ` · resolved ${fmt(tracked.resolved_at)}` : ""}</div>
              {tracked.resolution && <div className="mt-1"><b>Resolution:</b> {tracked.resolution}</div>}
            </div>
          )}
        </Card>
        <SiteFooter tone="dark" className="mt-8" />
      </div>
    </div>
  );
}

function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={clsx("rounded-2xl bg-white p-5 shadow-xl shadow-black/20 sm:p-8", className)}>{children}</div>;
}
