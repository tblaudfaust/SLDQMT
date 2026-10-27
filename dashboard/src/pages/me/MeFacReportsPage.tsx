import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import clsx from "clsx";
import { BarChart3, Copy, ExternalLink, QrCode } from "lucide-react";
import { api, fmtDate } from "../../api/client";
import type { MeFacReportRound } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { Card, Empty, Spinner } from "../../components/ui";
import QrDialog from "../../components/QrDialog";
import { CountCard } from "./kpi/kpiUi";
import { PHASE_LABEL } from "./MeFacPage";

/** The link the Lead Facilitators use: the configured public address (censusme.statistics.sl) or this dashboard's own. */
export const reportLink = (r: MeFacReportRound) => r.report_url ?? `${window.location.origin}/report/${r.round.token}`;

/** Daily Facilitator's Report: one entry per training (shared with the facilitator assessment), the public link and QR code, and the feedback dashboard. */
export default function MeFacReportsPage() {
  const { can } = useAuth();
  const list = useQuery({ queryKey: ["me-facrep", "rounds"], queryFn: () => api.get<MeFacReportRound[]>("/me/facreports/rounds") });
  const [copied, setCopied] = useState<number | null>(null);
  const [qr, setQr] = useState<MeFacReportRound | null>(null);
  const data = list.data ?? [];
  const totals = data.reduce((t, r) => ({ reports: t.reports + r.reports, halls: t.halls + r.halls, attention: t.attention + r.attention }), { reports: 0, halls: 0, attention: 0 });
  const copy = async (r: MeFacReportRound) => { try { await navigator.clipboard.writeText(reportLink(r)); setCopied(r.round.id); setTimeout(() => setCopied(null), 2000); } catch { prompt("Copy this link", reportLink(r)); } };

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Facilitator daily report</h1>
          <p className="text-sm text-slate-500">Daily Facilitator's Report, Training of Trainers (in-person): one report per hall per day by the Lead Facilitator, for the Training Coordinator and the CTA. Share the link or QR code of the training with the Lead Facilitators; the trainings and their chapters per day are the ones of the Facilitator assessment.</p>
        </div>
        {can("me_fac.manage") && <Link to="/me/facilitators" className="btn-outline">Manage trainings and chapters</Link>}
      </div>
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <CountCard label="Trainings" value={data.length} sub={`${data.filter((r) => r.round.status === "OPEN").length} open`} />
        <CountCard label="Reports received" value={totals.reports} sub={`${totals.halls} halls`} tone="green" />
        <CountCard label="Need attention" value={totals.attention} sub="low ratings, sessions not delivered, poor attendance, power or internet" tone={totals.attention ? "amber" : "navy"} />
        <CountCard label="Attendance" value={data.length && data.some((r) => r.attendance_pct !== null) ? `${Math.round(data.filter((r) => r.attendance_pct !== null).reduce((s, r) => s + (r.attendance_pct ?? 0), 0) / data.filter((r) => r.attendance_pct !== null).length)}%` : "—"} sub="mean of the trainings" />
      </div>
      {list.isLoading ? <Spinner /> : data.length === 0 ? (
        <Card><Empty text="No training yet. Create one under Facilitator assessment (with its chapters per day); its link then serves both the trainer ratings and the daily facilitator reports." /></Card>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {data.map((r) => (
            <Card key={r.round.id}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <Link to={`/me/facreports/${r.round.id}`} className="text-lg font-semibold text-navy hover:underline">{r.round.title}</Link>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
                    <span className="rounded-full bg-violet-100 px-2 py-0.5 font-semibold text-violet-800">{PHASE_LABEL[r.round.phase] ?? r.round.phase}</span>
                    <span className={clsx("rounded-full px-2 py-0.5 font-semibold", r.round.status === "OPEN" ? "bg-green-100 text-green-800" : "bg-slate-200 text-slate-700")}>{r.round.status === "OPEN" ? "Open" : "Closed"}</span>
                    {(r.round.period_start || r.round.period_end) && <span className="text-slate-500">{fmtDate(r.round.period_start)}{r.round.period_end ? ` – ${fmtDate(r.round.period_end)}` : ""}</span>}
                    <span className="text-slate-500">{r.round.agenda_items} chapters, {r.round.agenda_days} days</span>
                  </div>
                </div>
                <Link to={`/me/facreports/${r.round.id}`} className="btn-primary shrink-0"><BarChart3 size={16} /> Dashboard</Link>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2 text-center sm:grid-cols-4">
                {[["Reports", r.reports], ["Halls", r.halls], ["Attendance", r.attendance_pct === null ? "—" : `${Math.round(r.attendance_pct)}%`], ["Class rating", r.mean_rating === null ? "—" : `${r.mean_rating.toFixed(1)} / 5`]].map(([l, v]) => <div key={String(l)} className="rounded-lg bg-slate-50 px-2 py-2"><div className="text-xl font-bold text-navy">{v}</div><div className="text-[11px] uppercase tracking-wide text-slate-500">{l}</div></div>)}
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
                <span className="text-xs text-slate-500">{r.venues} venue{r.venues === 1 ? "" : "s"} · {r.days} day{r.days === 1 ? "" : "s"}{r.last_date ? ` · last report ${fmtDate(r.last_date)}` : ""}{r.attention ? ` · ${r.attention} need attention` : ""}</span>
                <span className="flex-1" />
                <button className="btn-outline py-1" onClick={() => copy(r)}><Copy size={14} /> {copied === r.round.id ? "Copied" : "Copy link"}</button>
                <a className="btn-outline py-1" href={reportLink(r)} target="_blank" rel="noreferrer"><ExternalLink size={14} /> Open the form</a>
                <button className="btn-outline py-1" onClick={() => setQr(r)}><QrCode size={14} /> QR code</button>
              </div>
            </Card>
          ))}
        </div>
      )}
      {qr && <QrDialog url={reportLink(qr)} title={qr.round.title} subtitle="Daily Facilitator's Report · the Lead Facilitator of each hall sends one report per day" onClose={() => setQr(null)} />}
    </div>
  );
}
