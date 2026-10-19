import { useEffect, useState } from "react";
import { Outlet } from "react-router-dom";
import { Download, LogOut, Wifi, WifiOff } from "lucide-react";
import clsx from "clsx";
import { useAuth } from "../auth/AuthContext";
import type { MeKpiAppVersion } from "../api/types";
import { useOnline } from "../pages/me/kpi/kpiStore";
import ChangePasswordDialog from "./ChangePasswordDialog";
import { checkForUpdate } from "../appUpdate";

declare global {
  interface Window { SLPHCApp?: { version(): string; versionCode?(): number; openExternal?(url: string): void; reload(): void } }
}

/** Installed app version from the Android bridge: version code when the app exposes it, else parsed from the name. */
function installed(): { code: number | null; name: string | null } {
  const b = window.SLPHCApp;
  if (!b) return { code: null, name: null };
  try {
    const name = b.version();
    const code = typeof b.versionCode === "function" ? Number(b.versionCode()) : null;
    return { code: Number.isFinite(code as number) ? code : null, name };
  } catch { return { code: null, name: null }; }
}
const nameToNumber = (v: string) => v.split(".").slice(0, 3).reduce((n, p) => n * 1000 + (Number(p) || 0), 0);

/** The frame of the Android field app: no menu, just the tool. Sign-out, the network state and the update icon at the top. */
export default function FieldLayout() {
  const { user, logout, refreshUser } = useAuth();
  const online = useOnline();
  const [update, setUpdate] = useState<MeKpiAppVersion | null>(null);
  const [showNote, setShowNote] = useState(false);
  const [checkNote, setCheckNote] = useState<string | null>(null);
  const check = async () => {
    setCheckNote("Checking…");
    const r = await checkForUpdate();
    setCheckNote(r === "updating" ? "New version found: installing, the app refreshes in a moment." : r === "current" ? "You have the latest version." : r === "offline" ? "No network: try again when connected." : "Updates are checked when the app opens.");
    window.setTimeout(() => setCheckNote(null), 6000);
  };
  useEffect(() => {
    const me = installed();
    if (!me.name) return; // in a browser, not the app
    fetch("/api/v1/public/app-version").then((r) => (r.ok ? r.json() : null)).then((v: Record<string, MeKpiAppVersion> | null) => {
      const latest = v?.fieldtool;
      if (!latest || !latest.available) return;
      const newer = me.code !== null ? latest.version_code > me.code : nameToNumber(latest.version_name) > nameToNumber(me.name!);
      if (newer) setUpdate(latest);
    }).catch(() => undefined);
  }, [online]);
  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      <header className="sticky top-0 z-30 flex items-center gap-3 bg-navy px-3 py-2 text-white shadow">
        <img src="/statsl-logo.png" alt="" className="h-8 w-8 rounded-full bg-white p-0.5" />
        <div className="min-w-0 flex-1 leading-tight">
          <div className="truncate text-sm font-bold">M&amp;E Field Tool</div>
          <div className="truncate text-[11px] text-sky-100/80">{user?.full_name} · <button type="button" onClick={() => void check()} className="underline decoration-dotted" title="Check for updates">build {__BUILD__}{window.SLPHCApp ? ` · app ${installed().name}` : ""}</button></div>
        </div>
        {update && (
          <button onClick={() => setShowNote((s) => !s)} className="relative rounded-md bg-amber-400 px-2 py-1 text-[11px] font-bold text-amber-950" title={`Update to version ${update.version_name}`}>
            <Download size={14} className="mr-1 inline" />Update
            <span className="absolute -right-1 -top-1 h-2.5 w-2.5 animate-pulse rounded-full bg-red-500" />
          </button>
        )}
        <span className={clsx("flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold", online ? "bg-emerald-500/30" : "bg-amber-400/40")}>{online ? <Wifi size={12} /> : <WifiOff size={12} />}{online ? "Online" : "Offline"}</span>
        <button onClick={() => { if (confirm("Sign out? Reports waiting to be sent stay on this device until you sign in again.")) logout(); }} className="rounded-md p-1.5 hover:bg-white/10" title="Sign out"><LogOut size={18} /></button>
      </header>
      {checkNote && <div className="border-b border-sky-200 bg-sky-50 px-4 py-2 text-xs text-sky-900">{checkNote}</div>}
      {update && showNote && (
        <div className="border-b border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <div className="font-semibold">Version {update.version_name} of the app is available{update.notes ? `: ${update.notes}` : "."}</div>
          <div className="mt-1 text-xs">Tap Download; when the file has downloaded, open it and allow the installation. Your reports and drafts stay on the device.</div>
          <div className="mt-2 flex gap-2">
            <a href={update.download_url} className="rounded-lg bg-navy px-3 py-1.5 text-xs font-semibold text-white" download onClick={(e) => { const b = window.SLPHCApp; if (b && typeof b.openExternal === "function") { e.preventDefault(); b.openExternal(new URL(update.download_url, window.location.origin).toString()); } }}>Download ({update.size_bytes ? `${Math.round(update.size_bytes / 1024)} KB` : "APK"})</a>
            <button className="rounded-lg border border-amber-300 px-3 py-1.5 text-xs" onClick={() => setShowNote(false)}>Later</button>
          </div>
        </div>
      )}
      <main className="flex-1 px-3 py-3 sm:px-4">
        <Outlet />
      </main>
      {user?.must_change_password && online && <ChangePasswordDialog forced onClose={() => void refreshUser()} />}
      {user?.must_change_password && !online && <div className="border-t border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-900">You still use the temporary password. You will be asked to choose your own password when the network is back; you can work offline meanwhile.</div>}
    </div>
  );
}
