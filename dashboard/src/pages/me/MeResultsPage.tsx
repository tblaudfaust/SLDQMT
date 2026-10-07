import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Fragment, useState } from "react";
import { Link, useParams } from "react-router-dom";
import clsx from "clsx";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Copy, Download, ExternalLink } from "lucide-react";
import { ApiError, api, download, fmt, fmtDate, qs } from "../../api/client";
import type { MeBreakdown, MeDistrictRow, MeDomain, MeItem, MeRespondent, MeResults } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { Card, Empty, ErrorBox, KpiTile, Spinner } from "../../components/ui";
import { evaluationLink } from "./MeEvaluationsPage";

const C = { navy: "#1F4E79", green: "#15803d", amber: "#d97706", red: "#b91c1c", sky: "#38bdf8" };
const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${v}%`);
const num = (v: number | null | undefined) => (v === null || v === undefined ? "—" : v.toFixed(2));

/** Results of one training evaluation: profile, domain scores, readiness, needs and open feedback. */
export default function MeResultsPage() {
  const { id } = useParams();
  const { can } = useAuth();
  const qc = useQueryClient();
  const [district, setDistrict] = useState("");
  const res = useQuery({ queryKey: ["me", "results", id, district], queryFn: () => api.get<MeResults>(`/me/evaluations/${id}/results${qs({ district: district || undefined })}`) });
  const people = useQuery({ queryKey: ["me", "respondents", id], queryFn: () => api.get<MeRespondent[]>(`/me/evaluations/${id}/respondents`) });
  const [tab, setTab] = useState<"overview" | "districts" | "items" | "feedback" | "respondents">("overview");
  const [error, setError] = useState<unknown>(null);
  const remove = useMutation({
    mutationFn: (responseId: number) => api.delete(`/me/evaluations/${id}/responses/${responseId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["me"] }),
    onError: setError,
  });
  if (res.isLoading) return <Spinner />;
  if (res.error || !res.data) return <ErrorBox error={res.error} />;
  const d = res.data;
  const e = d.evaluation;
  const domainRows = d.domains.filter((x) => x.n_respondents > 0).map((x) => ({ name: x.label, fav: x.pct_favourable ?? 0, mean: x.mean ?? 0, flag: x.flag }));
  const exportFile = async (format: "xlsx" | "pdf") => {
    setError(null);
    try { await download(`/me/evaluations/${id}/export?format=${format}`, `evaluation-${id}.${format}`); } catch (err) { setError(err); }
  };

  return (
    <div className="max-w-6xl">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link to="/me/evaluations" className="text-sm text-navy">← Training evaluations</Link>
          <h1 className="text-2xl font-bold">{e.title}</h1>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
            <span className={clsx("rounded-full px-2 py-0.5 font-semibold", e.training_mode === "ONLINE" ? "bg-sky-100 text-sky-800" : "bg-emerald-100 text-emerald-800")}>{e.training_mode === "ONLINE" ? "Online / self-paced" : "In-person"}</span>
            <span className={clsx("rounded-full px-2 py-0.5 font-semibold", e.status === "OPEN" ? "bg-green-100 text-green-800" : "bg-slate-200 text-slate-700")}>{e.status === "OPEN" ? "Open" : "Closed"}</span>
            {(e.period_start || e.period_end) && <span className="text-slate-500">{fmtDate(e.period_start)}{e.period_end ? ` – ${fmtDate(e.period_end)}` : ""}</span>}
            <button className="text-navy" onClick={() => navigator.clipboard.writeText(evaluationLink(e))}><Copy size={12} className="mr-1 inline" />Copy link</button>
            <a className="text-navy" href={evaluationLink(e)} target="_blank" rel="noreferrer"><ExternalLink size={12} className="mr-1 inline" />Open form</a>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select className="input w-56" value={district} onChange={(e) => setDistrict(e.target.value)} title="Limit every figure on this page to one district">
            <option value="">All districts</option>
            {(d.by_district ?? []).map((x) => <option key={x.district} value={x.district}>{x.district} ({x.trainees + x.trainers})</option>)}
          </select>
          <button className="btn-outline" onClick={() => exportFile("xlsx")}><Download size={16} /> Excel</button>
          <button className="btn-outline" onClick={() => exportFile("pdf")}><Download size={16} /> PDF</button>
        </div>
      </div>
      <ErrorBox error={error instanceof ApiError ? error.message : error} />

      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <KpiTile label="Responses" value={d.submitted} sub={`${d.registered} registered · ${pct(d.response_rate)} completed`} />
        <KpiTile label="Trainees" value={d.trainees} />
        <KpiTile label="Trainers" value={d.trainers} tone="amber" />
        <KpiTile label="Knowledge gain" value={d.knowledge.gain === null ? "—" : `+${d.knowledge.gain}`} tone="green" sub={d.knowledge.before === null ? undefined : `${d.knowledge.before} → ${d.knowledge.after} (1–5); ${pct(d.knowledge.pct_positive)} improved`} />
        <KpiTile label="Overall quality" value={d.overall.H03_mean?.[0] ? d.overall.H03_mean[0].pct.toFixed(2) : "—"} tone={d.overall.H03_mean?.[0] && d.overall.H03_mean[0].pct < 4 ? "red" : "navy"} sub="mean of 1–5 (flag < 4.0)" />
        <KpiTile label="Ready for their role" value={pct(d.overall.H07.find((b) => b.label.startsWith("Yes"))?.pct ?? (d.trainees ? 0 : null))} tone="green" sub={`${d.overall.H07.find((b) => b.label.startsWith("Not"))?.count ?? 0} not yet ready`} />
      </div>

      {district && <div className="mb-3 rounded-md bg-sky-50 px-3 py-2 text-sm text-sky-900">Showing <b>{district}</b> only. The By district tab always compares all districts.</div>}
      <div className="mb-4 flex gap-1 border-b border-slate-200">
        {(["overview", "districts", "items", "feedback", "respondents"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)} className={clsx("-mb-px border-b-2 px-3 py-2 text-sm font-medium capitalize", tab === t ? "border-navy text-navy" : "border-transparent text-slate-500 hover:text-slate-700")}>{t === "items" ? "Item scores" : t === "feedback" ? "Open feedback" : t === "districts" ? "By district" : t}</button>
        ))}
      </div>

      {tab === "districts" && <DistrictTable rows={d.by_district ?? []} onPick={(name) => { setDistrict(name); setTab("overview"); }} />}

      {tab === "overview" && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card title="Domain scores · % favourable (rating 4 or 5)" className="lg:col-span-2">
            {domainRows.length ? (
              <div style={{ height: 60 + 36 * domainRows.length }}>
                <ResponsiveContainer>
                  <BarChart data={domainRows} layout="vertical" margin={{ left: 10, right: 40 }}>
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                    <XAxis type="number" domain={[0, 100]} unit="%" />
                    <YAxis type="category" dataKey="name" width={210} tick={{ fontSize: 12 }} />
                    <Tooltip formatter={(v: number, _n, p) => [`${v}% favourable · mean ${(p.payload as { mean: number }).mean.toFixed(2)}`, ""]} />
                    <Bar dataKey="fav" radius={[0, 4, 4, 0]} label={{ position: "right", formatter: (v: number) => `${v}%`, fontSize: 12 }} isAnimationActive={false}>
                      {domainRows.map((r) => <Cell key={r.name} fill={r.flag ? C.red : C.navy} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : <Empty text="No rated responses yet" />}
            <p className="mt-2 text-xs text-slate-500">Red bars are below the provisional flag (70%, trainers 75%). Means use valid 1–5 ratings only; N/A and skipped items are excluded, and a respondent's domain score counts only when at most 20% of its items are missing.</p>
          </Card>
          <Card title="Strongest items"><ItemList items={d.strengths} /></Card>
          <Card title="Weakest items (reinforce first)"><ItemList items={d.weaknesses} /></Card>
          <BreakdownCard title="Respondents by district" rows={d.profile.district} />
          <BreakdownCard title="Trainees by position" rows={d.profile.role} />
          <div className="grid gap-4 sm:grid-cols-2"><BreakdownCard title="Attendance mode" rows={d.profile.mode ?? []} /><BreakdownCard title="Training hall (in-person)" rows={d.profile.hall ?? []} /></div>
          <BreakdownCard title="By institution" rows={d.profile.institution} />
          <div className="grid gap-4 sm:grid-cols-2"><BreakdownCard title="Sex" rows={d.profile.sex} /><BreakdownCard title="Age group" rows={d.profile.age} /></div>
          <BreakdownCard title={e.training_mode === "ONLINE" ? "Completed all modules (A06)" : "Attended all sessions (A06)"} rows={d.completion.A06} />
          <BreakdownCard title="Live / interactive sessions attended (A07)" rows={d.completion.A07} />
          <BreakdownCard title="Took all assessments (A08)" rows={d.completion.A08} />
          {d.completion.B07.length > 0 && <BreakdownCard title="Main reason for not completing (B07)" rows={d.completion.B07} />}
          {d.completion.A09.length > 0 && <BreakdownCard title="Main device used (A09)" rows={d.completion.A09} />}
          <BreakdownCard title="Overall quality of the training (H03)" rows={d.overall.H03} />
          <BreakdownCard title="Training duration (H04)" rows={d.overall.H04} />
          <BreakdownCard title="Recommended approach for future training (H05)" rows={d.overall.H05} />
          <BreakdownCard title="Keep materials accessible during fieldwork (H06)" rows={d.overall.H06} />
          <BreakdownCard title="Ready to perform the role (H07)" rows={d.overall.H07} />
          <BreakdownCard title="Areas needing more practice · trainees (H08)" rows={d.reinforcement.trainees} note="share of trainees who ticked the topic (up to three each)" />
          <BreakdownCard title="Trainees ready for the next stage · trainer view (J10)" rows={d.overall.J10} />
          <BreakdownCard title="Trainees needing individual follow-up (J11)" rows={d.overall.J11} />
          <BreakdownCard title="Reinforcement needs · trainer view (J13)" rows={d.reinforcement.trainers} note="share of trainers who ticked the topic" />
        </div>
      )}

      {tab === "items" && (
        <div className="space-y-4">
          {d.domains.map((dom) => <DomainTable key={dom.code} dom={dom} />)}
        </div>
      )}

      {tab === "feedback" && (
        <Card title={`${d.open_feedback.length} open answers`}>
          {d.open_feedback.length ? (
            <div className="space-y-4">
              {(["I01", "I02", "I03", "I04", "J14", "J12_names"] as const).map((code) => {
                const rows = d.open_feedback.filter((f) => f.code === code);
                if (!rows.length) return null;
                const titles: Record<string, string> = { I01: "Most useful aspect", I02: "Biggest challenge", I03: "One thing to improve before the next stage", I04: "Other comments", J14: "Trainers' recommendations", J12_names: "Trainees needing follow-up (names / IDs)" };
                return (
                  <div key={code}>
                    <h3 className="mb-1 font-semibold">{titles[code]} <span className="text-xs font-normal text-slate-500">({rows.length})</span></h3>
                    <ul className="space-y-1">
                      {rows.map((f, i) => <li key={i} className="rounded-md bg-slate-50 px-3 py-2 text-sm"><span className="text-slate-800">{f.text}</span> <span className="text-xs text-slate-400">· {f.role === "TRAINER" ? "trainer" : "trainee"}{f.district ? `, ${f.district}` : ""}</span></li>)}
                    </ul>
                  </div>
                );
              })}
            </div>
          ) : <Empty text="No open answers yet" />}
        </Card>
      )}

      {tab === "respondents" && (
        <Card title={`${people.data?.length ?? 0} registered`}>
          {people.isLoading ? <Spinner /> : people.data?.length ? (
            <div className="overflow-x-auto">
              <table className="table">
                <thead><tr><th>Respondent</th><th>Role</th><th>District</th><th>Mode</th><th>Hall</th><th>Registered</th><th>Submitted</th>{can("me.manage") && <th />}</tr></thead>
                <tbody>
                  {people.data.map((p) => (
                    <tr key={p.id}>
                      <td className="font-medium">{p.email ?? <span className="text-slate-400">anonymous #{p.id}</span>}</td>
                      <td>{p.role === "TRAINER" ? "Trainer" : p.role === "TRAINEE" ? "Trainee" : p.role === "NEITHER" ? "Neither" : <span className="text-slate-400">not yet</span>}</td>
                      <td>{p.district ?? ""}</td><td>{p.attendance_mode === "IN_PERSON" ? "In-person" : p.attendance_mode === "ONLINE" ? "Online" : ""}</td><td>{p.hall ?? ""}</td><td className="whitespace-nowrap">{fmt(p.registered_at)}</td>
                      <td className="whitespace-nowrap">{p.submitted_at ? fmt(p.submitted_at) : <span className="text-amber-700">pending</span>}</td>
                      {can("me.manage") && <td>{p.response_id && <button className="text-xs text-red-700" onClick={() => { if (confirm(`Remove the response of ${p.email ?? `anonymous respondent #${p.id}`} from the results? They can submit again.`)) remove.mutate(p.response_id!); }}>Remove response</button>}</td>}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <Empty text="Nobody has registered yet. Share the link." />}
        </Card>
      )}
    </div>
  );
}

function ItemList({ items }: { items: MeItem[] }) {
  if (!items.length) return <Empty text="No rated items yet" />;
  return (
    <ul className="space-y-2">
      {items.map((it) => (
        <li key={it.code} className="flex items-center gap-3 text-sm">
          <span className="w-10 shrink-0 font-mono text-xs text-slate-500">{it.code}</span>
          <span className="flex-1">{it.text}</span>
          <span className={clsx("w-14 shrink-0 text-right font-semibold", it.flag ? "text-red-700" : "text-green-700")}>{pct(it.pct_favourable)}</span>
          <span className="w-10 shrink-0 text-right text-xs text-slate-500">{num(it.mean)}</span>
        </li>
      ))}
    </ul>
  );
}

function BreakdownCard({ title, rows, note }: { title: string; rows: MeBreakdown[]; note?: string }) {
  const max = Math.max(1, ...rows.map((r) => r.count));
  return (
    <Card title={title}>
      {rows.length ? (
        <div className="space-y-1.5">
          {rows.map((r) => (
            <div key={r.label} className="flex items-center gap-2 text-sm">
              <span className="w-44 shrink-0 truncate" title={r.label}>{r.label}</span>
              <div className="h-4 flex-1 overflow-hidden rounded bg-slate-100"><div className="h-full rounded bg-navy/80" style={{ width: `${(100 * r.count) / max}%` }} /></div>
              <span className="w-20 shrink-0 text-right text-xs text-slate-600">{r.count} · {r.pct}%</span>
            </div>
          ))}
          {note && <p className="pt-1 text-xs text-slate-400">{note}</p>}
        </div>
      ) : <Empty text="No answers yet" />}
    </Card>
  );
}

function DomainTable({ dom }: { dom: MeDomain }) {
  return (
    <Card title={`${dom.code} · ${dom.label}`} action={<span className={clsx("text-sm font-semibold", dom.flag ? "text-red-700" : "text-green-700")}>{dom.n_respondents ? `${pct(dom.pct_favourable)} favourable · mean ${num(dom.mean)} · n=${dom.n_respondents}` : "no responses"}</span>}>
      <table className="table">
        <thead><tr><th className="w-16">Code</th><th>Statement</th><th className="w-14 text-right">n</th><th className="w-14 text-right">N/A</th><th className="w-16 text-right">Mean</th><th className="w-24 text-right">% favourable</th></tr></thead>
        <tbody>
          {dom.items.map((it) => (
            <tr key={it.code} className={it.flag ? "bg-red-50" : ""}>
              <td className="font-mono text-xs">{it.code}</td><td>{it.text}</td>
              <td className="text-right">{it.n}</td><td className="text-right">{it.na}</td><td className="text-right">{num(it.mean)}</td>
              <td className={clsx("text-right font-semibold", it.flag ? "text-red-700" : "")}>{pct(it.pct_favourable)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

const DOMAIN_COLS: { code: string; label: string; flag: number }[] = [
  { code: "B", label: "Digital access", flag: 70 }, { code: "C", label: "Organisation", flag: 70 }, { code: "D", label: "Census content", flag: 70 },
  { code: "E", label: "CAPI / data quality", flag: 70 }, { code: "F", label: "Trainers", flag: 75 }, { code: "G", label: "Readiness", flag: 70 }, { code: "J", label: "Trainer view", flag: 70 },
];

function DistrictTable({ rows, onPick }: { rows: MeDistrictRow[]; onPick: (district: string) => void }) {
  const cellPct = (v: number | null, flag: number) => (
    <td className={clsx("text-right font-semibold", v === null ? "text-slate-300" : v < flag ? "text-red-700" : "text-green-700")}>{v === null ? "—" : `${v}%`}</td>
  );
  const totals = rows.reduce((t, r) => ({ trainees: t.trainees + r.trainees, trainers: t.trainers + r.trainers, not_ready: t.not_ready + r.not_ready }), { trainees: 0, trainers: 0, not_ready: 0 });
  return (
    <Card title={`${rows.length} districts reporting`} className="mb-4">
      {rows.length ? (
        <div className="overflow-x-auto">
          <table className="table">
            <thead>
              <tr>
                <th>District</th><th className="text-right">Trainees</th><th className="text-right">Trainers</th><th className="text-right">Completed modules</th>
                {DOMAIN_COLS.map((c) => <th key={c.code} className="text-right" title={`% favourable (rating 4 or 5); flag below ${c.flag}%`}>{c.label}</th>)}
                <th className="text-right">Knowledge gain</th><th className="text-right">Fully ready</th><th className="text-right">Not ready</th><th className="text-right">Quality (1–5)</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.district} className="cursor-pointer hover:bg-slate-50" title="Show this district only" onClick={() => onPick(r.district)}>
                  <td className="font-medium text-navy">{r.district}</td>
                  <td className="text-right">{r.trainees}</td><td className="text-right">{r.trainers}</td>
                  <td className="text-right">{r.completion_pct === null ? "—" : `${r.completion_pct}%`}</td>
                  {DOMAIN_COLS.map((c) => <Fragment key={c.code}>{cellPct(r.domains[c.code] ?? null, c.flag)}</Fragment>)}
                  <td className="text-right">{r.gain === null ? "—" : `${r.gain > 0 ? "+" : ""}${r.gain}`}</td>
                  <td className="text-right">{r.ready_pct === null ? "—" : `${r.ready_pct}%`}</td>
                  <td className={clsx("text-right", r.not_ready ? "font-semibold text-red-700" : "")}>{r.not_ready}</td>
                  <td className={clsx("text-right", r.quality_mean !== null && r.quality_mean < 4 ? "text-red-700" : "")}>{r.quality_mean === null ? "—" : r.quality_mean.toFixed(2)}</td>
                </tr>
              ))}
              <tr className="font-semibold"><td>All districts</td><td className="text-right">{totals.trainees}</td><td className="text-right">{totals.trainers}</td><td colSpan={10} /><td className="text-right">{totals.not_ready}</td><td /></tr>
            </tbody>
          </table>
          <p className="mt-2 text-xs text-slate-500">Domain columns show the % favourable per district (red when below the flag). Click a district to limit the whole page to it. The Excel export has the same table on its By district sheet.</p>
        </div>
      ) : <Empty text="No district has reported yet" />}
    </Card>
  );
}
