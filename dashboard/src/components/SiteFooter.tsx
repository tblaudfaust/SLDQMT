import clsx from "clsx";

/**
 * The footer shown on every page: who built the system, the 2026 census, the Stats SL address and the
 * year. `tone="dark"` sits on the navy public pages and the login page; `tone="light"` closes the
 * signed-in pages below their content.
 */
export default function SiteFooter({ tone = "light", className }: { tone?: "light" | "dark"; className?: string }) {
  const year = new Date().getFullYear();
  const dark = tone === "dark";
  return (
    <footer className={clsx("text-xs leading-relaxed", dark ? "border-t border-white/15 text-sky-100/80" : "border-t border-slate-200 text-slate-500", className)}>
      <div className={clsx("mx-auto flex max-w-6xl flex-col items-center gap-3 px-4 py-5 text-center sm:flex-row sm:items-start sm:justify-between sm:text-left")}>
        <div className="flex items-center gap-3">
          <img src="/statsl-logo.png" alt="" className={clsx("h-10 w-10 rounded-full", dark ? "bg-white p-0.5" : "")} />
          <div>
            <div className={clsx("font-semibold", dark ? "text-white" : "text-slate-700")}>Developed by Statistics Sierra Leone (Stats SL)</div>
            <div>2026 Population and Housing Census · Data Quality Management, Monitoring &amp; Evaluation</div>
          </div>
        </div>
        <div>
          <div className={clsx("font-semibold", dark ? "text-white" : "text-slate-700")}>Statistics Sierra Leone</div>
          <div>A.J. Momoh Street / Tower Hill</div>
          <div>P.M.B. 595, Freetown / Sierra Leone</div>
        </div>
        <div className="sm:text-right">
          <div><a href="https://www.statistics.sl" target="_blank" rel="noreferrer" className={clsx("underline-offset-2 hover:underline", dark ? "text-white" : "text-navy")}>www.statistics.sl</a></div>
          <div>© {year} Statistics Sierra Leone. All rights reserved.</div>
          <div className={dark ? "text-sky-100/60" : "text-slate-400"}>Leh den kont you oh!</div>
        </div>
      </div>
    </footer>
  );
}
