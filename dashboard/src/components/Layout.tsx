import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { BarChart3, BookOpen, ClipboardCheck, ClipboardList, Download, FileText, FolderDown, KeyRound, Lock, LogOut, Settings, Smartphone, Tablet, Users, UsersRound, ScrollText, Database } from "lucide-react";
import { openResourceByKey } from "../api/resources";
import clsx from "clsx";
import { useAuth } from "../auth/AuthContext";
import AnalyticsMenu from "./AnalyticsMenu";
import ChangePasswordDialog from "./ChangePasswordDialog";

const roleLabel: Record<string, string> = {
  DISTRICT_DQM: "District DQM",
  REGIONAL: "Regional staff",
  NATIONAL_DQM: "National DQM",
  ADMIN: "Administrator",
};

export default function Layout() {
  const { user, logout, can } = useAuth();
  const [changePw, setChangePw] = useState(false);
  const isNational = user?.role === "NATIONAL_DQM" || user?.role === "ADMIN";
  const isRegionalUp = isNational || user?.role === "REGIONAL";
  const showAdmin = can("users.manage") || can("roles.manage") || can("devices.manage") || can("reference.manage") || can("settings.manage") || can("audit.view");
  const link = ({ isActive }: { isActive: boolean }) =>
    clsx("flex items-center gap-2 rounded-md px-3 py-2 text-sm", isActive ? "bg-white/15 text-white" : "text-slate-200 hover:bg-white/10");
  return (
    <div className="flex min-h-screen">
      <aside className="w-60 shrink-0 bg-navy text-white flex flex-col">
        <div className="px-4 py-5">
          <div className="flex items-center gap-3">
            <img src="/statsl-logo.png" alt="Statistics Sierra Leone" className="h-12 w-12 shrink-0 rounded-full bg-white" />
            <div className="text-sm font-semibold leading-tight">Statistics Sierra Leone</div>
          </div>
          <div className="mt-3 text-xs uppercase tracking-wider text-slate-300">SLPHC 2026</div>
          <div className="text-xl font-bold leading-tight">Field Monitor Errors</div>
        </div>
        <nav className="flex-1 space-y-1 px-2">
          {can("dashboard.view") && (
            <>
              <NavLink to="/" end className={link}><BarChart3 size={16} /> Dashboard</NavLink>
              <NavLink to="/errors" className={link}><ClipboardList size={16} /> Errors</NavLink>
              <NavLink to="/monitors" className={link}><Tablet size={16} /> Field Monitors</NavLink>
              <NavLink to="/teams" className={link}><UsersRound size={16} /> Teams</NavLink>
            </>
          )}
          {can("reports.export") && <NavLink to="/reports" className={link}><FileText size={16} /> Reports</NavLink>}
          {(can("daily_reports.view") || can("analytics.view")) && (
            <>
              <div className="px-3 pt-5 pb-1 text-base font-bold text-white">Daily DQM reporting</div>
              {can("daily_reports.view") && <NavLink to="/dqm/reports" className={link}><ClipboardCheck size={16} /> Daily reports</NavLink>}
              {can("analytics.view") && <AnalyticsMenu />}
            </>
          )}
          {can("exit_checkouts.view") && (
            <>
              <div className="px-3 pt-5 pb-1 text-base font-bold text-white">Field exit protocol</div>
              <NavLink to="/dqm/exit" end className={link}><ClipboardCheck size={16} /> Check-outs</NavLink>
              <NavLink to={isNational ? "/dqm/exit/summary/national" : isRegionalUp ? "/dqm/exit/summary/region" : "/dqm/exit/summary/district"} className={link}><BarChart3 size={16} /> Exit summary</NavLink>
            </>
          )}
          <div className="px-3 pt-5 pb-1 text-base font-bold text-white">User's manuals &amp; App</div>
          <button type="button" className={`${link({ isActive: false })} w-full text-left`} onClick={() => void openResourceByKey("manual-pdf").catch((e) => alert(e.message))}><BookOpen size={16} /> User manual (opens in a new tab)</button>
          <button type="button" className={`${link({ isActive: false })} w-full text-left`} onClick={() => void openResourceByKey("app-apk").catch((e) => alert(e.message))}><Download size={16} /> Tablet app (APK)</button>
          <NavLink to="/resources" className={link}><FolderDown size={16} /> All manuals &amp; app</NavLink>
          {showAdmin && (
            <>
              <div className="px-3 pt-5 pb-1 text-base font-bold text-white">Administration</div>
              {can("users.manage") && <NavLink to="/admin/users" className={link}><Users size={16} /> User management</NavLink>}
              {can("roles.manage") && <NavLink to="/admin/roles" className={link}><KeyRound size={16} /> Roles and rights</NavLink>}
              {can("devices.manage") && <NavLink to="/admin/devices" className={link}><Smartphone size={16} /> Devices</NavLink>}
              {can("reference.manage") && <NavLink to="/admin/reference" className={link}><Database size={16} /> Reference lists</NavLink>}
              {can("settings.manage") && <NavLink to="/admin/settings" className={link}><Settings size={16} /> Settings</NavLink>}
              {can("audit.view") && <NavLink to="/admin/audit" className={link}><ScrollText size={16} /> Audit log</NavLink>}
            </>
          )}
        </nav>
        <div className="border-t border-white/10 px-4 py-3 text-sm">
          <div className="font-medium">{user?.full_name}</div>
          <div className="text-xs text-slate-300">{user ? roleLabel[user.role] ?? user.role : ""}</div>
          <div className="mt-2 flex gap-3">
            <button onClick={() => setChangePw(true)} className="flex items-center gap-1 text-xs text-slate-300 hover:text-white"><Lock size={14} /> Password</button>
            <button onClick={logout} className="flex items-center gap-1 text-xs text-slate-300 hover:text-white"><LogOut size={14} /> Sign out</button>
          </div>
        </div>
      </aside>
      <main className="flex-1 p-6">
        <Outlet />
      </main>
      {changePw && <ChangePasswordDialog onClose={() => setChangePw(false)} />}
    </div>
  );
}
