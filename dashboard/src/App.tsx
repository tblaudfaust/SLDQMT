import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import Layout from "./components/Layout";
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
  if (can("mefm.view")) return <Navigate to="/mefm" replace />;
  if (can("daily_reports.view")) return <Navigate to="/dqm/reports" replace />;
  return <Navigate to="/resources" replace />;
}

/** Pages that are not for Monitoring & Evaluation accounts (they work only with training evaluations). */
function NotForMe() {
  const { user } = useAuth();
  if (user?.role === "ME") return <Navigate to="/me/evaluations" replace />;
  if (user?.role === "ME_DISTRICT" || user?.role === "ME_REGIONAL") return <Navigate to="/mefm" replace />;
  return <Outlet />;
}

function RequirePerm({ code }: { code: string }) {
  const { can } = useAuth();
  if (!can(code)) return <Navigate to="/" replace />;
  return <Outlet />;
}

export default function App() {
  return (
    <QueryClientProvider client={client}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/evaluate/:token" element={<EvaluatePage />} />
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
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}
