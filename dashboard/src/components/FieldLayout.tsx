import { Outlet } from "react-router-dom";
import { LogOut, Wifi, WifiOff } from "lucide-react";
import clsx from "clsx";
import { useAuth } from "../auth/AuthContext";
import { useOnline } from "../pages/me/kpi/kpiStore";

/** The frame of the Android field app: no menu, just the tool. Sign-out and the network state at the top. */
export default function FieldLayout() {
  const { user, logout } = useAuth();
  const online = useOnline();
  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      <header className="sticky top-0 z-30 flex items-center gap-3 bg-navy px-3 py-2 text-white shadow">
        <img src="/statsl-logo.png" alt="" className="h-8 w-8 rounded-full bg-white p-0.5" />
        <div className="min-w-0 flex-1 leading-tight">
          <div className="truncate text-sm font-bold">M&amp;E Field Tool</div>
          <div className="truncate text-[11px] text-sky-100/80">{user?.full_name}</div>
        </div>
        <span className={clsx("flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold", online ? "bg-emerald-500/30" : "bg-amber-400/40")}>{online ? <Wifi size={12} /> : <WifiOff size={12} />}{online ? "Online" : "Offline"}</span>
        <button onClick={() => { if (confirm("Sign out? Reports waiting to be sent stay on this device until you sign in again.")) logout(); }} className="rounded-md p-1.5 hover:bg-white/10" title="Sign out"><LogOut size={18} /></button>
      </header>
      <main className="flex-1 px-3 py-3 sm:px-4">
        <Outlet />
      </main>
    </div>
  );
}
