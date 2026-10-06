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

const client = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 30_000 } } });

function RequireAuth() {
  const { user, loading } = useAuth();
  if (loading) return <Spinner />;
  if (!user) return <Navigate to="/login" replace />;
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
            <Route element={<RequireAuth />}>
              <Route element={<Layout />}>
                <Route index element={<DashboardPage />} />
                <Route path="errors" element={<ErrorsPage />} />
                <Route path="errors/:id" element={<ErrorDetailPage />} />
                <Route path="monitors" element={<MonitorsPage />} />
                <Route path="teams" element={<TeamsPage />} />
                <Route element={<RequirePerm code="workload.assign" />}><Route path="workload" element={<WorkloadPage />} /></Route>
                <Route path="reports" element={<ReportsPage />} />
                <Route path="resources" element={<ResourcesPage />} />
                <Route path="dqm/reports" element={<DqmReportsPage />} />
                <Route path="dqm/reports/:id" element={<DqmReportFormPage />} />
                <Route path="dqm/summary/:level" element={<DqmSummaryPage />} />
                <Route path="dqm/analytics" element={<DqmAnalyticsIndexPage />} />
                <Route path="dqm/analytics/:level" element={<DqmAnalyticsPage />} />
                <Route path="dqm/exit" element={<ExitCheckoutsPage />} />
                <Route path="dqm/exit/summary/:level" element={<ExitSummaryPage />} />
                <Route path="dqm/exit/:id" element={<ExitCheckoutFormPage />} />
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
