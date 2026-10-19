import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import Layout from "./components/Layout";
import FieldLayout from "./components/FieldLayout";
import { isAppMode } from "./brand";
import { Spinner } from "./components/ui";
import DashboardPage from "./pages/DashboardPage";
import ErrorDetailPage from "./pages/ErrorDetailPage";
import ErrorsPage from "./pages/ErrorsPage";
import LoginPage from "./pages/LoginPage";
import MonitorsPage from "./pages/MonitorsPage";
import ReportsPage from "./pages/ReportsPage";
import ResourcesPage from "./pages/ResourcesPage";
import TeamsPage from "./pages/TeamsPage";
import WorkloadPage from "./pages/WorkloadPage";
import AuditPage from "./pages/admin/AuditPage";
import DevicesPage from "./pages/admin/DevicesPage";
import ReferencePage from "./pages/admin/ReferencePage";
import RolesPage from "./pages/admin/RolesPage";
import SettingsPage from "./pages/admin/SettingsPage";
import UsersPage from "./pages/admin/UsersPage";
import DqmAnalyticsIndexPage from "./pages/dqm/DqmAnalyticsIndexPage";
import DqmAnalyticsPage from "./pages/dqm/DqmAnalyticsPage";
import DqmReportFormPage from "./pages/dqm/DqmReportFormPage";
import DqmReportsPage from "./pages/dqm/DqmReportsPage";
import DqmSummaryPage from "./pages/dqm/DqmSummaryPage";
import ExitCheckoutFormPage from "./pages/exit/ExitCheckoutFormPage";
import ExitCheckoutsPage from "./pages/exit/ExitCheckoutsPage";
import ExitSummaryPage from "./pages/exit/ExitSummaryPage";
import MeEvaluationsPage from "./pages/me/MeEvaluationsPage";
import MeResultsPage from "./pages/me/MeResultsPage";
import MeDailyPage from "./pages/me/MeDailyPage";
import MeDailyResultsPage from "./pages/me/MeDailyResultsPage";
import DailyPage from "./pages/public/DailyPage";
import MeFacPage from "./pages/me/MeFacPage";
import MeFacResultsPage from "./pages/me/MeFacResultsPage";
import AssessPage from "./pages/public/AssessPage";
import KpiHomePage from "./pages/me/kpi/KpiHomePage";
import KpiFormPage from "./pages/me/kpi/KpiFormPage";
import KpiDashboardPage from "./pages/me/kpi/KpiDashboardPage";
import KpiReportsPage from "./pages/me/kpi/KpiReportsPage";
import IncidentsDashboardPage from "./pages/incidents/IncidentsDashboardPage";
import IncidentsRegisterPage from "./pages/incidents/IncidentsRegisterPage";
import IncidentSaCodesPage from "./pages/incidents/IncidentSaCodesPage";
import ReportIncidentPage from "./pages/public/ReportIncidentPage";
import EvaluatePage from "./pages/public/EvaluatePage";
import MefmHomePage from "./pages/mefm/MefmHomePage";

const client = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 30_000 } } });

function RequireAuth() {
  const { user, loading } = useAuth();
  if (loading) return <Spinner />;
  if (!user) return <Navigate to="/login" replace />;
  return <Outlet />;
}

/** The first page after sign-in: the error dashboard for most roles, the M&E pages for M&E staff. */
function Home() {
  const { can } = useAuth();
  if (can("dashboard.view")) return <DashboardPage />;
  if (can("me.view")) return <Navigate to="/me/evaluations" replace />;
  if (can("me_daily.view")) return <Navigate to="/me/daily" replace />;
  if (can("me_fac.view")) return <Navigate to="/me/facilitators" replace />;
  if (can("me_kpi.view")) return <Navigate to="/me/kpi" replace />;
  if (can("incidents.view")) return <Navigate to="/incidents" replace />;
  if (can("mefm.view")) return <Navigate to="/mefm" replace />;
  if (can("daily_reports.view")) return <Navigate to="/dqm/reports" replace />;
  return <Navigate to="/resources" replace />;
}

/** Pages that are not for Monitoring & Evaluation accounts (they work only with training evaluations). */
function NotForMe() {
  const { user } = useAuth();
  if (user?.role === "ME") return <Navigate to="/me/evaluations" replace />;
  if (user?.role === "ME_DAILY") return <Navigate to="/me/daily" replace />;
  if (user?.role === "DISTRICT_STATISTICIAN" || user?.role === "INCIDENT_VIEWER" || user?.role === "INCIDENT_ADMIN") return <Navigate to="/incidents" replace />;
  if (user?.role === "ME_DISTRICT" || user?.role === "ME_REGIONAL") return <Navigate to="/me/kpi" replace />;
  return <Outlet />;
}

function RequirePerm({ code }: { code: string }) {
  const { can } = useAuth();
  if (!can(code)) return <Navigate to="/" replace />;
  return <Outlet />;
}

/** The Android field app: sign in, then only the KPI form and the reports on the device. */
function FieldApp() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<FieldLayout />}>
          <Route element={<RequireFieldAccess />}>
            <Route path="/me/kpi" element={<KpiHomePage />} />
            <Route path="/me/kpi/new" element={<KpiFormPage />} />
            <Route path="/me/kpi/report/:clientId" element={<KpiFormPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/me/kpi" replace />} />
        </Route>
      </Route>
    </Routes>
  );
}

function RequireFieldAccess() {
  const { user, can, logout } = useAuth();
  if (can("me_kpi.collect")) return <Outlet />;
  return (
    <div className="mx-auto max-w-md rounded-2xl bg-white p-6 text-center shadow">
      <h1 className="text-lg font-bold text-navy">No field tool access</h1>
      <p className="mt-2 text-sm text-slate-600">The account <b>{user?.username}</b> ({user?.role}) is not allowed to collect KPI reports. Ask the M&amp;E lead to give it the District, Regional or national M&amp;E role.</p>
      <button className="btn-primary mt-4" onClick={logout}>Sign in with another account</button>
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={client}>
      <AuthProvider>
        <BrowserRouter>
          {isAppMode ? <FieldApp /> : (
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/evaluate/:token" element={<EvaluatePage />} />
            <Route path="/daily/:token" element={<DailyPage />} />
            <Route path="/assess/:token" element={<AssessPage />} />
            <Route path="/report-incident" element={<ReportIncidentPage />} />
            <Route element={<RequireAuth />}>
              <Route element={<Layout />}>
                <Route index element={<Home />} />
                <Route path="errors" element={<ErrorsPage />} />
                <Route path="errors/:id" element={<ErrorDetailPage />} />
                <Route path="monitors" element={<MonitorsPage />} />
                <Route path="teams" element={<TeamsPage />} />
                <Route element={<RequirePerm code="workload.assign" />}><Route path="workload" element={<WorkloadPage />} /></Route>
                <Route path="reports" element={<ReportsPage />} />
                <Route element={<NotForMe />}><Route path="resources" element={<ResourcesPage />} /></Route>
                <Route path="dqm/reports" element={<DqmReportsPage />} />
                <Route path="dqm/reports/:id" element={<DqmReportFormPage />} />
                <Route path="dqm/summary/:level" element={<DqmSummaryPage />} />
                <Route path="dqm/analytics" element={<DqmAnalyticsIndexPage />} />
                <Route path="dqm/analytics/:level" element={<DqmAnalyticsPage />} />
                <Route path="dqm/exit" element={<ExitCheckoutsPage />} />
                <Route path="dqm/exit/summary/:level" element={<ExitSummaryPage />} />
                <Route path="dqm/exit/:id" element={<ExitCheckoutFormPage />} />
                <Route element={<RequirePerm code="mefm.view" />}><Route path="mefm" element={<MefmHomePage />} /></Route>
                <Route element={<RequirePerm code="me.view" />}>
                  <Route path="me/evaluations" element={<MeEvaluationsPage />} />
                  <Route path="me/evaluations/:id" element={<MeResultsPage />} />
                </Route>
                <Route element={<RequirePerm code="incidents.view" />}>
                  <Route path="incidents" element={<IncidentsDashboardPage />} />
                  <Route path="incidents/register" element={<IncidentsRegisterPage />} />
                </Route>
                <Route element={<RequirePerm code="incidents.settings" />}><Route path="incidents/sa-codes" element={<IncidentSaCodesPage />} /></Route>
                <Route element={<RequirePerm code="me_daily.view" />}>
                  <Route path="me/daily" element={<MeDailyPage />} />
                  <Route path="me/daily/:id" element={<MeDailyResultsPage />} />
                </Route>
                <Route element={<RequirePerm code="me_fac.view" />}>
                  <Route path="me/facilitators" element={<MeFacPage />} />
                  <Route path="me/facilitators/:id" element={<MeFacResultsPage />} />
                </Route>
                <Route element={<RequirePerm code="me_kpi.view" />}>
                  <Route path="me/kpi" element={<KpiHomePage />} />
                  <Route path="me/kpi/new" element={<KpiFormPage />} />
                  <Route path="me/kpi/report/:clientId" element={<KpiFormPage />} />
                  <Route path="me/kpi/dashboard" element={<KpiDashboardPage />} />
                  <Route path="me/kpi/reports" element={<KpiReportsPage />} />
                </Route>
                <Route element={<RequirePerm code="users.manage" />}><Route path="admin/users" element={<UsersPage />} /></Route>
                <Route element={<RequirePerm code="roles.manage" />}><Route path="admin/roles" element={<RolesPage />} /></Route>
                <Route element={<RequirePerm code="devices.manage" />}><Route path="admin/devices" element={<DevicesPage />} /></Route>
                <Route element={<RequirePerm code="reference.manage" />}><Route path="admin/reference" element={<ReferencePage />} /></Route>
                <Route element={<RequirePerm code="settings.manage" />}><Route path="admin/settings" element={<SettingsPage />} /></Route>
                <Route element={<RequirePerm code="audit.view" />}><Route path="admin/audit" element={<AuditPage />} /></Route>
              </Route>
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
          )}
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}
