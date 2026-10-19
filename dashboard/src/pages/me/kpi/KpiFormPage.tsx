import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import clsx from "clsx";
import { ArrowLeft, ArrowRight, Check, Crosshair, Save, Send, WifiOff } from "lucide-react";
import { useAuth } from "../../../auth/AuthContext";
import type { MeKpiAnswers, MeKpiGeo, MeKpiItem, MeKpiReportIn, MeKpiSection, MeKpiSpec } from "../../../api/types";
import { ErrorBox, Spinner } from "../../../components/ui";
import { getLocal, queueReport, refreshReference, saveDraft, syncNow, useOnline, uuid } from "./kpiStore";

/* ------------------------------------------------------------------------------------------------
 * The field form: one screen per section, big tap targets, saved on the device at every change.
 * Section A (where and who) is pre-filled from the GIS data: pick the SA and the chiefdom, EAs,
 * enumerators and supervisor follow. Works offline; "Finish and send" queues the report.
 * ---------------------------------------------------------------------------------------------- */

const today = () => new Date().toISOString().slice(0, 10);
const applies = (x: { phases?: string[] }, phase: string) => !x.phases || x.phases.includes(phase);

export function emptyReport(): MeKpiReportIn {
  return { client_id: uuid(), phase: "E", report_date: today(), week: null, district_id: null, chiefdom: null, section: null, team_id: null, sa_code: null, practice_team: null, respondent_name: null, respondent_role: "SUPERVISOR", eas_urban: null, eas_rural: null, enumerators: null, capi_version: null, lat: null, lng: null, answers: {} };
}

function validate(d: MeKpiReportIn, spec: MeKpiSpec): string[] {
  const e: string[] = [];
  if (!d.report_date) e.push("Enter the date");
  else if (d.report_date > today()) e.push("The date cannot be in the future");
  if (!d.district_id) e.push("Choose the district");
  if (d.lat === null || d.lng === null) e.push("Capture the GPS position (section A)");
  if ((d.phase === "L" || d.phase === "E") && !d.team_id && !d.sa_code) e.push("Choose the SA");
  if ((d.phase === "MT" || d.phase === "TOT") && !d.practice_team && !d.team_id) e.push("Enter the practice team or hall");
  for (const s of spec.sections) {
    if (!applies(s, d.phase)) continue;
    for (const it of s.items) {
      if (!applies(it, d.phase) || !it.required) continue;
      const v = d.answers[it.code];
      const missing = v === undefined || v === "" || (typeof v === "object" && !Array.isArray(v) && Object.keys(v).length === 0);
      if (missing) e.push(`${s.title.replace(/^.*· /, "")}: ${it.text}`);
    }
  }
  return e;
}

export default function KpiFormPage() {
  const { clientId } = useParams();
  const { user } = useAuth();
  const nav = useNavigate();
  const online = useOnline();
  const [spec, setSpec] = useState<MeKpiSpec | null>(null);
  const [geo, setGeo] = useState<MeKpiGeo | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [d, setD] = useState<MeKpiReportIn | null>(null);
  const [step, setStep] = useState(0);
  const [touched, setTouched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [gpsNote, setGpsNote] = useState<string | null>(null);
  const saveTimer = useRef<number | null>(null);

  useEffect(() => {
    if (!user) return;
    refreshReference(user.id).then((r) => {
      if (!r.spec) { setLoadError("The form is not on this device yet. Connect to the network once, then open it again."); return; }
      setSpec(r.spec); setGeo(r.geo);
      const local = clientId ? getLocal(clientId) : null;
      if (clientId && !local) { setLoadError("This report is not on this device."); return; }
      const start = local ? local.data : emptyReport();
      if (!local && r.geo && r.geo.districts.length === 1) start.district_id = r.geo.districts[0].id;
      setD(start);
    });
  }, [user, clientId]);

  // save the draft a moment after each change
  useEffect(() => {
    if (!d || !spec) return;
    if (saveTimer.current) window.clearTimeout(saveTimer.current);
    saveTimer.current = window.setTimeout(() => saveDraft(d, geo), 400);
    return () => { if (saveTimer.current) window.clearTimeout(saveTimer.current); };
  }, [d, geo, spec]);

  const steps = useMemo(() => (spec && d ? [{ code: "A", title: "Where and who", subtitle: "Section A" } as MeKpiSection, ...spec.sections.filter((s) => applies(s, d.phase))] : []), [spec, d]);
  if (loadError) return <div className="max-w-2xl"><ErrorBox error={loadError} /><Link to="/me/kpi" className="btn-outline mt-3">Back</Link></div>;
  if (!spec || !d) return <Spinner />;
  const set = (patch: Partial<MeKpiReportIn>) => setD({ ...d, ...patch });
  const setA = (code: string, v: MeKpiAnswers[string]) => setD({ ...d, answers: { ...d.answers, [code]: v } });
  const errors = validate(d, spec);
  const current = steps[step];
  const last = step === steps.length - 1;

  const finish = async () => {
    setTouched(true);
    if (errors.length) { setStep(0); window.scrollTo({ top: 0 }); return; }
    setBusy(true);
    queueReport({ ...d, submitted_at: new Date().toISOString() }, geo);
    try {
      const out = await syncNow();
      const res = out?.results.find((x) => x.client_id === d.client_id);
      nav("/me/kpi", { state: { notice: res?.status === "error" ? `The server rejected the report: ${res.message}. It is kept on this device; open it, correct and send again.` : res ? "Report sent. Thank you." : "Saved on this device; it will be sent when you are back online." } });
    } catch { nav("/me/kpi", { state: { notice: "Saved on this device; sign in again when online to send it." } }); } finally { setBusy(false); }
  };

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <Link to="/me/kpi" className="text-sm text-navy"><ArrowLeft size={14} className="mr-1 inline" />M&amp;E Field Tool</Link>
        <div className="flex items-center gap-2 text-xs text-slate-500">{!online && <span className="flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 font-semibold text-amber-800"><WifiOff size={12} /> offline</span>}<span className="flex items-center gap-1"><Save size={12} /> saved on this device</span></div>
      </div>
      {/* progress */}
      <div className="mb-4 flex gap-1 overflow-x-auto pb-1">
        {steps.map((s, i) => (
          <button key={s.code} onClick={() => setStep(i)} className={clsx("shrink-0 rounded-full px-3 py-1 text-xs font-semibold", i === step ? "bg-navy text-white" : i < step ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-600")}>{s.code === "A" ? "A" : s.code === "B" ? "B" : s.code.replace("K", "KPI ")}</button>
        ))}
      </div>
      <div className="rounded-2xl bg-white p-4 shadow sm:p-6">
        <div className="mb-1 text-xs uppercase tracking-wide text-slate-400">Step {step + 1} of {steps.length}</div>
        <h1 className="text-xl font-bold text-navy">{current.title}</h1>
        {current.subtitle && <p className="mb-4 text-sm text-slate-500">{current.subtitle}</p>}
        {step === 0 ? <SectionA d={d} set={set} spec={spec} geo={geo} gpsNote={gpsNote} setGpsNote={setGpsNote} /> : (
          <div className="space-y-5">
            {current.items.filter((it) => applies(it, d.phase)).map((it, i) => <ItemField key={it.code} item={it} index={i + 1} answers={d.answers} setA={setA} />)}
          </div>
        )}
        {touched && errors.length > 0 && (
          <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"><div className="font-semibold">Please complete before sending</div><ul className="mt-1 list-disc pl-5">{errors.map((x) => <li key={x}>{x}</li>)}</ul></div>
        )}
        <div className="mt-6 flex items-center justify-between gap-2">
          <button className="btn-outline" onClick={() => { setStep(Math.max(0, step - 1)); window.scrollTo({ top: 0 }); }} disabled={step === 0}><ArrowLeft size={16} /> Back</button>
          {last ? (
            <button className="btn-primary px-5 py-3 text-base" onClick={finish} disabled={busy}><Send size={18} /> {busy ? "Sending…" : online ? "Finish and send" : "Finish (sends later)"}</button>
          ) : (
            <button className="btn-primary px-5 py-3 text-base" onClick={() => { setStep(step + 1); window.scrollTo({ top: 0 }); }}>Next <ArrowRight size={18} /></button>
          )}
        </div>
      </div>
      <p className="mt-3 text-center text-xs text-slate-400">Every change is saved on this device. You can leave and continue later from the front page.</p>
    </div>
  );
}

// ---- Section A -----------------------------------------------------------------------------------

function L({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return <label className="block"><span className="mb-1 block text-sm font-medium text-slate-700">{label}</span>{children}{hint && <span className="mt-1 block text-xs text-slate-400">{hint}</span>}</label>;
}

function SectionA({ d, set, spec, geo, gpsNote, setGpsNote }: { d: MeKpiReportIn; set: (p: Partial<MeKpiReportIn>) => void; spec: MeKpiSpec; geo: MeKpiGeo | null; gpsNote: string | null; setGpsNote: (s: string | null) => void }) {
  const field = d.phase === "L" || d.phase === "E";
  const autoGps = useRef(false);
  useEffect(() => { if (!autoGps.current && d.lat === null) { autoGps.current = true; gps(); } }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const districts = geo?.districts ?? [];
  const chiefdoms = (geo?.chiefdoms ?? []).filter((c) => c.district_id === d.district_id);
  const chiefdomId = chiefdoms.find((c) => c.name === d.chiefdom)?.id;
  const sections = (geo?.sections ?? []).filter((s) => s.district_id === d.district_id && (!chiefdomId || s.chiefdom_id === chiefdomId));
  const teams = (geo?.teams ?? []).filter((t) => t.district_id === d.district_id);
  const [teamQuery, setTeamQuery] = useState("");
  const shown = teamQuery ? teams.filter((t) => `${t.code} ${t.name} ${t.supervisor ?? ""} ${t.chiefdom ?? ""}`.toLowerCase().includes(teamQuery.toLowerCase())).slice(0, 30) : teams.slice(0, 30);
  const team = teams.find((t) => t.id === d.team_id) ?? null;
  const pickTeam = (id: number | null) => {
    const t = teams.find((x) => x.id === id) ?? null;
    set({ team_id: t?.id ?? null, sa_code: t?.code ?? null, chiefdom: t?.chiefdom ?? d.chiefdom, eas_urban: t ? t.eas_urban : d.eas_urban, eas_rural: t ? t.eas_rural : d.eas_rural, enumerators: t ? t.enumerators || d.enumerators : d.enumerators, respondent_name: t?.supervisor && !d.respondent_name ? t.supervisor : d.respondent_name });
  };
  const gps = () => {
    if (!navigator.geolocation) { setGpsNote("No GPS on this device: GPS is required, use a phone with location services"); return; }
    setGpsNote("Getting position…");
    navigator.geolocation.getCurrentPosition((p) => { set({ lat: Math.round(p.coords.latitude * 1e5) / 1e5, lng: Math.round(p.coords.longitude * 1e5) / 1e5 }); setGpsNote(`Position captured (±${Math.round(p.coords.accuracy)} m)`); }, () => setGpsNote("Position not available; you can continue without it"), { enableHighAccuracy: true, timeout: 15000 });
  };
  return (
    <div className="space-y-4">
      <div>
        <span className="mb-1 block text-sm font-medium text-slate-700">Census phase *</span>
        <div className="grid grid-cols-2 gap-2">
          {spec.phases.map((p) => <button type="button" key={p.value} onClick={() => set({ phase: p.value as MeKpiReportIn["phase"], week: p.value === "L" || p.value === "E" ? d.week : null })} className={clsx("rounded-xl border-2 px-3 py-3 text-left text-sm font-semibold", d.phase === p.value ? "border-navy bg-navy text-white" : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50")}>{p.label}</button>)}
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <L label="Date of reporting *"><input className="input py-3 text-base" type="date" max={today()} value={d.report_date} onChange={(e) => set({ report_date: e.target.value })} /></L>
        {field ? <L label="Reporting week" hint="Counted from the first day of the phase"><input className="input py-3 text-base" type="number" min={1} max={60} inputMode="numeric" value={d.week ?? ""} onChange={(e) => set({ week: e.target.value ? Number(e.target.value) : null })} /></L>
          : <L label="Practice team / hall *"><input className="input py-3 text-base" value={d.practice_team ?? ""} onChange={(e) => set({ practice_team: e.target.value || null })} placeholder="e.g. Hall 2, team A" maxLength={120} /></L>}
      </div>
      <L label="District *">
        <select className="input py-3 text-base" value={d.district_id ?? ""} onChange={(e) => { set({ district_id: e.target.value ? Number(e.target.value) : null, chiefdom: null, section: null, team_id: null, sa_code: null }); setTeamQuery(""); }}>
          <option value="">Choose…</option>{districts.map((x) => <option key={x.id} value={x.id}>{x.name} · {x.region}</option>)}
        </select>
      </L>
      {d.district_id && (
        <div>
          <span className="mb-1 block text-sm font-medium text-slate-700">Supervisory area (SA){field ? " *" : ""}</span>
          <input className="input py-3 text-base" placeholder={`Search ${teams.length} SAs by code, name, supervisor or chiefdom…`} value={teamQuery} onChange={(e) => setTeamQuery(e.target.value)} />
          {team && <div className="mt-2 flex items-center justify-between rounded-xl border-2 border-navy bg-sky-50 px-3 py-2 text-sm"><div><b>{team.code}</b> · {team.name}{team.supervisor ? ` · supervisor ${team.supervisor}` : ""}<div className="text-xs text-slate-500">{team.chiefdom ?? ""} · {team.eas} EAs ({team.eas_urban} urban, {team.eas_rural} rural) · {team.enumerators} enumerators{team.expected_households ? ` · ${team.expected_households} households expected` : ""}</div></div><button type="button" className="text-xs text-red-700 underline" onClick={() => pickTeam(null)}>Change</button></div>}
          {!team && (
            <ul className="mt-2 max-h-56 divide-y divide-slate-100 overflow-auto rounded-xl border border-slate-200">
              {shown.map((t) => <li key={t.id}><button type="button" className="w-full px-3 py-2 text-left text-sm hover:bg-sky-50" onClick={() => pickTeam(t.id)}><b>{t.code}</b> · {t.name}<span className="block text-xs text-slate-500">{t.chiefdom ?? ""}{t.supervisor ? ` · ${t.supervisor}` : ""} · {t.eas} EAs</span></button></li>)}
              {shown.length === 0 && <li className="px-3 py-2 text-sm text-slate-400">{teams.length ? "No SA matches" : "No SA loaded for this district"}</li>}
            </ul>
          )}
        </div>
      )}
      <div className="grid gap-3 sm:grid-cols-2">
        <L label="Chiefdom">
          {chiefdoms.length ? <select className="input py-3 text-base" value={d.chiefdom ?? ""} onChange={(e) => set({ chiefdom: e.target.value || null, section: null })}><option value="">Choose…</option>{chiefdoms.map((c) => <option key={c.id} value={c.name}>{c.name}</option>)}{d.chiefdom && !chiefdoms.some((c) => c.name === d.chiefdom) && <option value={d.chiefdom}>{d.chiefdom}</option>}</select>
            : <input className="input py-3 text-base" value={d.chiefdom ?? ""} onChange={(e) => set({ chiefdom: e.target.value || null })} />}
        </L>
        <L label="Section">
          {sections.length ? <select className="input py-3 text-base" value={d.section ?? ""} onChange={(e) => set({ section: e.target.value || null })}><option value="">Choose…</option>{sections.map((s) => <option key={s.id} value={s.name}>{s.name}</option>)}</select>
            : <input className="input py-3 text-base" value={d.section ?? ""} onChange={(e) => set({ section: e.target.value || null })} />}
        </L>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <L label="Name of the respondent"><input className="input py-3 text-base" value={d.respondent_name ?? ""} onChange={(e) => set({ respondent_name: e.target.value || null })} maxLength={160} /></L>
        <div>
          <span className="mb-1 block text-sm font-medium text-slate-700">Role / position</span>
          <div className="flex flex-wrap gap-1.5">{spec.roles.map((r) => <button type="button" key={r.value} onClick={() => set({ respondent_role: r.value })} className={clsx("rounded-full border px-3 py-1.5 text-sm", d.respondent_role === r.value ? "border-navy bg-navy text-white" : "border-slate-300 bg-white text-slate-700")}>{r.label}</button>)}</div>
        </div>
      </div>
      <div className="grid grid-cols-3 gap-3">
        <L label="Urban EAs"><input className="input py-3 text-base" type="number" min={0} inputMode="numeric" value={d.eas_urban ?? ""} onChange={(e) => set({ eas_urban: e.target.value ? Number(e.target.value) : null })} /></L>
        <L label="Rural EAs"><input className="input py-3 text-base" type="number" min={0} inputMode="numeric" value={d.eas_rural ?? ""} onChange={(e) => set({ eas_rural: e.target.value ? Number(e.target.value) : null })} /></L>
        <L label="Enumerators"><input className="input py-3 text-base" type="number" min={0} inputMode="numeric" value={d.enumerators ?? ""} onChange={(e) => set({ enumerators: e.target.value ? Number(e.target.value) : null })} /></L>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <L label="CAPI version used" hint="As shown on the tablet"><input className="input py-3 text-base" value={d.capi_version ?? ""} onChange={(e) => set({ capi_version: e.target.value || null })} placeholder="e.g. 2.3.1" maxLength={40} /></L>
        <div>
          <span className="mb-1 block text-sm font-medium text-slate-700">GPS position *</span>
          <button type="button" className={clsx("w-full py-3", d.lat ? "btn-outline" : "btn-primary")} onClick={gps}><Crosshair size={16} /> {d.lat ? `${d.lat}, ${d.lng}` : "Capture GPS"}</button>
          {gpsNote && <span className="mt-1 block text-xs text-slate-400">{gpsNote}</span>}
        </div>
      </div>
    </div>
  );
}

// ---- one item ------------------------------------------------------------------------------------

function ItemField({ item, index, answers, setA }: { item: MeKpiItem; index: number; answers: MeKpiAnswers; setA: (code: string, v: MeKpiAnswers[string]) => void }) {
  const v = answers[item.code];
  const detailKey = item.code + "_detail";
  const showDetail = !!item.detail && (!item.detail_when || (Array.isArray(v) ? v.includes(item.detail_when) : v === item.detail_when));
  const chip = (on: boolean, extra?: string) => clsx("rounded-xl border-2 px-3 py-2.5 text-sm font-semibold transition", on ? "border-navy bg-navy text-white" : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50", extra);
  return (
    <div className={clsx("rounded-xl border px-3 py-3", item.required && (v === undefined || v === "") ? "border-amber-200 bg-amber-50/40" : "border-slate-200")}>
      <div className="font-medium text-slate-800">{index}. {item.text}{item.required ? " *" : ""}</div>
      {item.help && <div className="text-xs text-slate-500">{item.help}</div>}
      <div className="mt-2">
        {(item.type === "yesno" || item.type === "yesno_na" || item.type === "choice") && (
          <div className="flex flex-wrap gap-2">{item.options!.map((o) => <button type="button" key={o.value} className={chip(v === o.value, "min-w-[5rem]")} onClick={() => setA(item.code, v === o.value ? undefined : o.value)}>{o.label}</button>)}</div>
        )}
        {item.type === "multi" && (
          <div className="flex flex-wrap gap-2">{item.options!.map((o) => { const arr = (v as string[] | undefined) ?? []; const on = arr.includes(o.value); return <button type="button" key={o.value} className={chip(on)} onClick={() => setA(item.code, on ? arr.filter((x) => x !== o.value) : [...arr, o.value])}>{on && <Check size={14} className="mr-1 inline" />}{o.label}</button>; })}</div>
        )}
        {item.type === "number" && <input className="input max-w-[12rem] py-3 text-base" type="number" min={0} inputMode="numeric" value={(v as number | undefined) ?? ""} onChange={(e) => setA(item.code, e.target.value === "" ? undefined : Number(e.target.value))} />}
        {item.type === "numbers" && (
          <div className="grid gap-2 sm:grid-cols-2">{item.fields!.map((f) => { const obj = (v as Record<string, number> | undefined) ?? {}; return <label key={f.key} className="block"><span className="mb-1 block text-xs text-slate-500">{f.label}</span><input className="input py-3 text-base" type="number" min={0} inputMode="numeric" value={obj[f.key] ?? ""} onChange={(e) => { const next = { ...obj }; if (e.target.value === "") delete next[f.key]; else next[f.key] = Number(e.target.value); setA(item.code, Object.keys(next).length ? next : undefined); }} /></label>; })}</div>
        )}
        {item.type === "text" && <textarea className="input py-3 text-base" rows={2} value={(v as string | undefined) ?? ""} onChange={(e) => setA(item.code, e.target.value || undefined)} />}
        {showDetail && <label className="mt-2 block"><span className="mb-1 block text-xs text-slate-500">{item.detail}</span><input className="input py-2.5 text-base" value={(answers[detailKey] as string | undefined) ?? ""} onChange={(e) => setA(detailKey, e.target.value || undefined)} maxLength={500} /></label>}
      </div>
    </div>
  );
}
